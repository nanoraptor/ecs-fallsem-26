# SoilSage: Hardware Setup & Wiring Guide

**Created by:** Rahul, Abhiram, Nikhil, Sanjeev, Saketh  
**Course:** ECS2001 - Project Ideation, Design and Prototyping  

## Core components

| Component | Qty | Purpose |
|---|---:|---|
| ESP32 DevkitC V4 (38 Pin) | 1 | Main controller |
| Analog pH sensor module + probe | 1 | pH reading |
| RS485 NPK Sensor | 1 | NPK reading |
| MAX485 TTL-to-RS485 Converter | 1 | Serial comms for NPK |
| External DC power supply (5-30V) | 1 | Powering NPK sensor |
| DS18B20 waterproof temp sensor | 1 | Water temperature (used for pH compensation) |
| DHT11 sensor module | 1 | Humidity & Temp input for model |
| 16x2 I2C LCD Display | 1 | Real-time sensor readout display |
| 10kΩ & 20kΩ resistors | 1 each | Voltage divider for pH sensor |
| 4.7kΩ resistor | 1 | DS18B20 data pull-up |
| Breadboard | 1 | Wiring/power distribution |
| Jumper wires (M-M / M-F) | As needed | Connections |
| USB cable | 1 | Power + programming |

## ESP32 wiring (for `esp32/esp32_full/esp32_full.ino`)

| Module | Module pin | ESP32 pin | Note |
|---|---|---|---|
| pH sensor | `VCC` | `5V` (VIN) |
| pH sensor | `GND` | `GND` |
| pH sensor | `AO` / `SIG` | `GPIO34` | **MUST use 10k/20k voltage divider to protect 3.3V ESP32 ADC** (Sensor OUT -> 10k -> GPIO34 -> 20k -> GND) |
| MAX485 | `VCC` | `3.3V` / `5V` | ESP32 logic is 3.3V, if powering MAX485 with 5V, ensure RO line to RX doesn't exceed 3.3V (use divider or 3.3V MAX3485) |
| MAX485 | `GND` | `GND` |
| MAX485 | `DI` (TX) | `GPIO17` (TX2)|
| MAX485 | `DE` & `RE` | `GPIO4` |
| MAX485 | `RO` (RX) | `GPIO16` (RX2)|
| MAX485 | `A` & `B` | NPK Sensor `A`/`B` |
| NPK Sensor| `VCC` / `GND` | Ext Power | Use external DC power supply (e.g., 12V) and connect its ground to ESP32 ground. |
| DS18B20 | `VCC` | `3.3V` / `5V` |
| DS18B20 | `GND` | `GND` |
| DS18B20 | `DATA` | `GPIO5` | Use 4.7k pullup |
| DHT11 | `VCC` | `3.3V` / `5V` |
| DHT11 | `GND` | `GND` |
| DHT11 | `DATA` | `GPIO18` |
| I2C LCD | `VCC` | `5V` (VIN) | Needs 5V for backlight |
| I2C LCD | `GND` | `GND` |
| I2C LCD | `SDA` | `GPIO21` |
| I2C LCD | `SCL` | `GPIO22` |

## Notes

- Keep **all grounds common** (every module GND + External Power Supply GND connected to ESP32 GND).
- **CRITICAL:** ESP32 ADC pins are 3.3V max. The pH sensor outputs 5V. Use the 10k/20k resistors as a voltage divider to step down the signal.
- The `esp32_full.ino` firmware connects directly to Wi-Fi and sends data via HTTP POST to the dashboard. You must update `ssid`, `password`, and `serverUrl` in the `.ino` file.
- Start the dashboard using `python3 app/app.py --esp32` to listen for Wi-Fi sensor data.

## Additional Stuff to buy and important notes

- You will need pH buffer solutions to calibrate the pH electrode (as most of the electrodes are non-calibrated out of the box).
- Distilled water is needed to clean the pH sensor between every soil sample test.
- The soil solutions should be made with distilled water in a 1:2 ratio of soil and water. The electrode will get damaged if it is dipped in a solution which contains a lot of solid sand particles. Let the slurry/solution settle or filter out the solution.
- A pH electrode stand will be helpful in handling the pH electrode. The bulb of the pH electrode should not touch the bottom of the container, as it will break the electrode. You can also use microphone stands with minor tweaks.
- The DS18B20 probe is required because the pH sensor used in this project does not have built-in temperature compensation.

## Potential improvements

- The webui (app.py) can be hosted on a cloud server for remote access.
- Implementing a robust PCB instead of a breadboard for the complex power distribution.
