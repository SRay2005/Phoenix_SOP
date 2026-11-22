"""
semg_fft_analysis.py

What this does, in plain terms:
Takes a CSV file saved by semg_receiver.py (sample_number, raw_adc,
voltage, timestamp) and shows you what frequencies make up your
signal - an FFT (Fast Fourier Transform) turns "signal over time"
into "how much of each frequency is present."

Why this matters for EMG specifically: Patchy's analog front-end
already bandpass-filters to 72-720Hz, since that's roughly where
real muscle signal content lives. This script marks that range on
the plot so you can visually confirm your captured signal's energy
actually falls where it should - a sanity check that your whole
analog + digital chain is behaving.

Run with:
  python semg_fft_analysis.py
  (uses the most recently created semg_log_*.csv in this folder)

  python semg_fft_analysis.py path/to/specific_log.csv
  (analyze a specific file instead)

You'll be asked, interactively, whether to analyze:
  - the WHOLE file, or
  - a specific time window within it (e.g. just one flex event)
"""

import sys
import os
import glob
import csv
from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt


def find_latest_log(script_dir):
    candidates = glob.glob(os.path.join(script_dir, "semg_log_*.csv"))
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def load_csv(path):
    sample_numbers = []
    raw_values = []
    voltages = []
    timestamps = []

    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sample_numbers.append(int(row["sample_number"]))
            raw_values.append(int(row["raw_adc"]))
            voltages.append(float(row["voltage"]))
            timestamps.append(datetime.fromisoformat(row["timestamp"]))

    return sample_numbers, raw_values, voltages, timestamps


def estimate_sample_rate(timestamps):
    """
    Uses the real recorded timestamps (not the nominal 1000Hz target)
    to figure out the ACTUAL average sample rate during capture.
    WiFi/UDP can introduce jitter or dropped packets, so the real
    rate is often a bit different from what the firmware aims for -
    using the true rate here matters for getting correct frequency
    values out of the FFT.
    """
    if len(timestamps) < 2:
        return None
    total_seconds = (timestamps[-1] - timestamps[0]).total_seconds()
    if total_seconds <= 0:
        return None
    return (len(timestamps) - 1) / total_seconds


def pick_window(voltages, timestamps, sample_rate):
    print()
    print(f"Loaded {len(voltages)} samples,")
    print(f"spanning {(timestamps[-1] - timestamps[0]).total_seconds():.2f} seconds.")
    print(f"Estimated actual sample rate: {sample_rate:.1f} Hz")
    print()
    print("Analyze:")
    print("  [1] The whole file")
    print("  [2] A specific time window (e.g. one flex event)")
    choice = input("Choose 1 or 2: ").strip()

    if choice == "2":
        duration = (timestamps[-1] - timestamps[0]).total_seconds()
        start_s = float(input(f"  Start time in seconds (0 to {duration:.2f}): "))
        end_s = float(input(f"  End time in seconds ({start_s} to {duration:.2f}): "))

        start_idx = int(start_s * sample_rate)
        end_idx = int(end_s * sample_rate)
        start_idx = max(0, start_idx)
        end_idx = min(len(voltages), end_idx)

        if end_idx <= start_idx:
            print("Invalid window, using the whole file instead.")
            return voltages, "whole file"

        label = f"{start_s:.2f}s - {end_s:.2f}s"
        return voltages[start_idx:end_idx], label

    return voltages, "whole file"


def run_fft(signal, sample_rate):
    n = len(signal)

    # Remove DC offset (the resting baseline voltage) before the FFT.
    # Without this, a huge spike at 0Hz would dominate the plot and
    # drown out the actual signal content we care about.
    signal = np.array(signal) - np.mean(signal)

    # A Hanning window reduces "spectral leakage" - artifacts that
    # appear because we're analyzing a finite chunk of a continuous
    # signal rather than a perfectly repeating one. Standard practice
    # for FFTs on real-world captured data.
    windowed = signal * np.hanning(n)

    fft_result = np.fft.rfft(windowed)
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate)
    magnitude = np.abs(fft_result)

    return freqs, magnitude


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = find_latest_log(script_dir)
        if csv_path is None:
            print("No semg_log_*.csv file found in this folder.")
            print("Run semg_receiver.py first to capture some data,")
            print("or pass a specific file: python semg_fft_analysis.py yourfile.csv")
            return
        print(f"Using most recent log: {csv_path}")

    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return

    _, _, voltages, timestamps = load_csv(csv_path)

    if len(voltages) < 10:
        print("Not enough samples in this file to run a meaningful FFT.")
        return

    sample_rate = estimate_sample_rate(timestamps)
    if sample_rate is None:
        print("Could not determine sample rate from timestamps.")
        return

    windowed_signal, window_label = pick_window(voltages, timestamps, sample_rate)

    if len(windowed_signal) < 10:
        print("Selected window is too short for a meaningful FFT.")
        return

    freqs, magnitude = run_fft(windowed_signal, sample_rate)

    fig, ax = plt.subplots()
    ax.plot(freqs, magnitude)

    # Shade the 72-720Hz range Patchy's analog filter is designed for,
    # as a visual reference - real muscle signal should mostly live
    # in or near this band if the analog front-end is doing its job.
    ax.axvspan(72, 720, color="green", alpha=0.1, label="Patchy's analog passband (72-720Hz)")

    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Magnitude")
    ax.set_title(f"sEMG Frequency Spectrum ({window_label})")
    ax.set_xlim(0, sample_rate / 2)  # Nyquist limit - can't see above this anyway
    ax.legend()
    ax.grid(True, alpha=0.3)

    out_path = os.path.join(
        script_dir,
        f"semg_fft_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    )
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"\nSaved plot to: {out_path}")

    plt.show()


if __name__ == "__main__":
    main()
