"""
semg_receiver.py

What this does, in plain terms:
1. Opens a UDP "listening ear" on your laptop on the same port the
   ESP32 is sending to.
2. Every time a packet arrives, it pulls out the sample number and
   raw ADC value.
3. Saves every sample to a timestamped CSV file on disk, so you have
   a permanent record (not just a live view that vanishes).
4. Draws a live, scrolling graph of the signal - auto-centered on
   wherever your actual signal sits, with clearer axis markings,
   instead of a fixed 0-4095 range that wastes most of the plot.

BEFORE RUNNING:
- Make sure semg_wifi_transmitter.ino is uploaded and running on the
  ESP32, and that LAPTOP_IP in that file matches this laptop's actual
  IP address on the SAME network the ESP32 is connected to.
- Run this script BEFORE or shortly after powering on the ESP32, so
  it's ready to catch incoming packets.

Run with:  python semg_receiver.py
Stop with: Ctrl+C, or just close the plot window.

Where your data gets saved:
  A new file named semg_log_YYYYMMDD_HHMMSS.csv is created in the
  same folder as this script, every time you run it. Columns are:
  sample_number, raw_adc, voltage, timestamp
"""

import socket
import csv
import os
from datetime import datetime
from collections import deque

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.ticker import MultipleLocator

UDP_PORT = 4210            # must match UDP_PORT in the .ino file
WINDOW_SIZE = 1000         # how many recent samples to show on screen at once
ADC_MAX = 4095             # 12-bit ADC: 0-4095
VREF = 5                # ESP32 ADC reference voltage

# How often (in animation frames) to recompute the y-axis center/zoom.
# Every frame would make the axis jitter distractingly; every ~15
# frames (roughly every 0.3s at the 20ms interval below) keeps it
# responsive without being jumpy.
RESCALE_EVERY_N_FRAMES = 15


def raw_to_voltage(raw):
    return (raw / ADC_MAX) * VREF


# ---------------------------------------------------------------
# CSV LOGGING SETUP
# ---------------------------------------------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
log_filename = f"semg_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
log_path = os.path.join(script_dir, log_filename)

log_file = open(log_path, "w", newline="")
csv_writer = csv.writer(log_file)
csv_writer.writerow(["sample_number", "raw_adc", "voltage", "timestamp"])

print(f"Logging every sample to: {log_path}")


# ---------------------------------------------------------------
# UDP SOCKET SETUP
# ---------------------------------------------------------------
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", UDP_PORT))
sock.setblocking(False)

print(f"Listening for sEMG data on UDP port {UDP_PORT}...")
print("Waiting for the ESP32 to start sending packets.")
print("Close the plot window or press Ctrl+C to stop (this saves the CSV).")

# A deque is just a list that automatically drops old values once full -
# perfect for a scrolling "last N samples" view.
values = deque([0] * WINDOW_SIZE, maxlen=WINDOW_SIZE)

frame_count = 0

fig, ax = plt.subplots()
line, = ax.plot(values)

ax.set_xlabel("Sample (most recent on the right)")
ax.set_ylabel("Voltage (V)")
ax.set_title("Live sEMG Signal (wireless)")

# Start with the full range until we have real data to center on.
ax.set_ylim(0, VREF)

# Finer gridlines: a major tick every 0.2V, with a light grid to
# make it easy to read values off the graph by eye.
ax.yaxis.set_major_locator(MultipleLocator(0.2))
ax.grid(True, which="major", axis="y", alpha=0.3)

# A second y-axis on the right showing the raw 0-4095 ADC number,
# in case you want to cross-check against Serial Monitor output.
ax_raw = ax.twinx()
ax_raw.set_ylabel("Raw ADC value")


def update(frame):
    global frame_count

    # Drain every packet currently waiting in the buffer so we don't
    # fall behind the incoming stream.
    while True:
        try:
            data, addr = sock.recvfrom(1024)
        except BlockingIOError:
            break  # no more packets waiting right now

        try:
            text = data.decode("utf-8").strip()
            counter_str, value_str = text.split(",")
            raw = int(value_str)
            counter = int(counter_str)
        except (ValueError, UnicodeDecodeError):
            continue  # malformed packet - skip rather than crash

        values.append(raw)

        voltage = raw_to_voltage(raw)
        timestamp = datetime.now().isoformat()
        csv_writer.writerow([counter, raw, f"{voltage:.4f}", timestamp])

    # Convert the whole visible window to voltage for plotting.
    voltages = [raw_to_voltage(v) for v in values]
    line.set_ydata(voltages)

    frame_count += 1

    # Periodically re-center the y-axis on wherever the signal
    # actually sits, instead of leaving it fixed at 0-3.3V the
    # whole time (which wastes most of the plot on empty space
    # once you know the baseline).
    if frame_count % RESCALE_EVERY_N_FRAMES == 0:
        v_min, v_max = min(voltages), max(voltages)
        v_center = (v_min + v_max) / 2
        v_span = max(v_max - v_min, 0.1)  # avoid a zero-height range
        padding = v_span * 0.3            # 30% headroom above/below

        new_bottom = max(0, v_center - v_span / 2 - padding)
        new_top = min(VREF, v_center + v_span / 2 + padding)

        ax.set_ylim(new_bottom, new_top)
        ax_raw.set_ylim(new_bottom / VREF * ADC_MAX, new_top / VREF * ADC_MAX)

    return line,


def on_close(event):
    print(f"\nStopped. {log_path} has your logged data.")
    log_file.close()


fig.canvas.mpl_connect("close_event", on_close)

ani = FuncAnimation(fig, update, interval=20, blit=False, cache_frame_data=False)

try:
    plt.show()
finally:
    if not log_file.closed:
        log_file.close()
        print(f"\nStopped. {log_path} has your logged data.")