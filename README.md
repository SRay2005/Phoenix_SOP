# Wireless sEMG Signal Transmission

Wireless transmission of surface electromyography (sEMG) signals using ESP32 microcontrollers over WiFi (UDP).

**Study Oriented Project — BITS Pilani, under Prof. Y. Sujan**

## Overview

This project implements a wireless sEMG signal acquisition and transmission system using:
- **BioAmp Patchy Sensor** for sEMG signal capture (bandpass 72–720 Hz)
- **ESP-WROOM-32 / ESP32-C3 SuperMini** for 12-bit ADC sampling at 1 kHz and WiFi UDP transmission
- **Python receiver** for real-time visualization and CSV logging
- **FFT analysis tool** for frequency-domain signal validation

## Repository Structure

```
├── semg_wifi_transmitter/
│   └── semg_wifi_transmitter.ino   # Arduino firmware for ESP32 transmitter
├── semg_receiver.py                # Python UDP receiver with live plotting
├── semg_fft_analysis.py            # FFT spectral analysis tool
├── semg_log_*.csv                  # Captured sEMG data logs
├── scope_857.csv / .txt            # Oscilloscope validation captures
└── scope_858.csv / .txt            # Oscilloscope validation captures
```

## Results

| Configuration | Status | SNR (dB) |
|---|---|---|
| ESP-WROOM-32 + Patchy + Laptop USB | ✅ Successful | 10.7 – 14.8 |
| ESP-WROOM-32 + Patchy + Battery | ✅ Successful | Comparable |
| ESP-WROOM-32 + In-House Sensor | ❌ Failed | N/A |
| ESP32-C3 SuperMini + Patchy | ❌ Failed | N/A |

## Requirements

- **Hardware**: ESP-WROOM-32 (or ESP32-C3), BioAmp Patchy sensor, 10kΩ/10kΩ voltage divider
- **Firmware**: Arduino IDE with ESP32 board support
- **Receiver**: Python 3 with `matplotlib` and `numpy`

## Usage

1. Upload `semg_wifi_transmitter.ino` to the ESP32 (edit WiFi SSID, password, and laptop IP)
2. Run `python semg_receiver.py` on the laptop
3. Analyze captured data with `python semg_fft_analysis.py`
