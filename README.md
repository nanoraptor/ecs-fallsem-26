# SoilSage: AI-Driven Precision Soil Sustainability

**Course:** ECS2001 — Project Ideation, Design and Prototyping  
**Created by:** Rahul, Abhiram, Nikhil, Sanjeev, Saketh and Shyam  

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![ESP32 38-Pin](https://img.shields.io/badge/Hardware-ESP32%2038--Pin%20NodeMCU-red.svg)](docs/setup.md)
[![Model Accuracy](https://img.shields.io/badge/EBM%20Accuracy-99.55%25-brightgreen.svg)](ml/model/soil_model.pkl)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Hardware Architecture & 38-Pin ESP32 Wiring](#hardware-architecture--38-pin-esp32-wiring)
- [The 3-Pillar Console & UI Design](#the-3-pillar-console--ui-design)
- [Project Structure](#project-structure)
- [Installation & Quickstart](#installation--quickstart)
- [Running the Application](#running-the-application)
  - [🌐 Web Dashboard Console](#-web-dashboard-console)
  - [🧪 Interactive 3-Soil Sample Demo Tool](#-interactive-3-soil-sample-demo-tool)
  - [💻 Standalone Terminal CLI Scripts](#-standalone-terminal-cli-scripts)
- [Command Line Flags & Options](#command-line-flags--options)
- [Explainable AI Model (EBM)](#explainable-ai-model-ebm)
- [Troubleshooting & FAQ](#troubleshooting--faq)

---

## Overview

**SoilSage** is a precision agriculture cyber-physical system designed to combat soil acidification, nutrient depletion, and chemical fertilizer overuse. By integrating real-time IoT hardware telemetry with an **Agronomic Explainable Boosting Machine (EBM)**, SoilSage measures field chemistry, diagnoses macro-nutrient imbalances, recommends the optimal crop from 22 agricultural cultivars, and formulates precise chemical/organic soil amendment plans.

---

## Key Features

- **38-Pin ESP32 Sensor Array:** Acquires live Soil pH, Nitrogen (N), Phosphorus (P), Potassium (K), Soil Solution Temperature (DS18B20), Ambient Air Temperature, and Humidity (DHT11).
- **Fail-Safe Zero NPK / Uninserted Probe UX:** When the sensor is in the air or soil is uninserted (`0, 0, 0 mg/kg`), the system suppresses default crop predictions and prompts *"Please insert soil sample"* on both the Web Console and the 16×2 LCD screen without greying out the tiles.
- **Persistent 16×2 LCD Dual-Readout:** Displays live sensor readings (`pH:6.5 T:30.5C` / `N:0 P:0 K:0`) on Line 0 while simultaneously keeping `Insert Soil Smpl` on Line 1.
- **Dual-Slope Calibrated pH Compensation:** Calibrated with SDFCL pH 4.0, 7.0, and 9.2 analytical buffers (`PH_VOLTAGE_PH7 = 1.114V`, `PH_SLOPE_ACID = 0.1805`, `PH_SLOPE_ALKALINE = 0.1438`) dynamically compensated by live DS18B20 water temperature.
- **Frame-Hunting Modbus RTU Engine:** Resilient RS485 communication searching for the `0x01 0x03 0x06` frame sync header across a 32-byte circular buffer, eliminating MAX485 `DE/RE` line transient glitch bytes.
- **Explainable Boosting Machine (`AgronomicEBMClassifier`):** 99.55% validation accuracy across 22 crops, providing exact biological window evaluations and plain-language reasoning.
- **Interactive 3-Sample Demo Suite:** Dedicated terminal and web demonstration workflows for testing and comparing 3 distinct soil samples side-by-side.
- **Mint Greenhouse Visual Console:** Built strictly on the `Design.md` design system (`#b7ffb4` Mint canvas, `#262626` Carbon Ink borders, `#00ff00` Lime botanical specimen accents, JetBrains Mono metrics).

---

## Hardware Architecture & 38-Pin ESP32 Wiring

> [!IMPORTANT]
> **Hardware Specification:**  
> This system is built specifically for the **38-Pin ESP32 NodeMCU (DevKitC V4 / NodeMCU-32S)**.  
> **Do NOT use the 30-Pin DevKit V1** — pinout locations and header assignments differ.

### 38-Pin ESP32 Header Diagram

```text
                           38-PIN ESP32 DEVKIT
                                (Top View)
                           +------------------+
                     3V3 --|  1 [ ]    [ ] 38 |-- GND (Common Ground)
                      EN --|  2 [ ]    [ ] 37 |-- D23 (GPIO 23)
           (GPIO 36)  VP --|  3 [ ]    [ ] 36 |-- D22 (GPIO 22) -> LCD SCL
           (GPIO 39)  VN --|  4 [ ]    [ ] 35 |-- TX0 (GPIO 1)
   pH In   (GPIO 34) D34 --|  5 [ ]    [ ] 34 |-- RX0 (GPIO 3)
           (GPIO 35) D35 --|  6 [ ]    [ ] 33 |-- D21 (GPIO 21) -> LCD SDA
           (GPIO 32) D32 --|  7 [ ]    [ ] 32 |-- D19 (GPIO 19)
           (GPIO 33) D33 --|  8 [ ]    [ ] 31 |-- D18 (GPIO 18) -> DHT11 Data
           (GPIO 25) D25 --|  9 [ ]    [ ] 30 |-- D5  (GPIO 5)  -> DS18B20 Temp
           (GPIO 26) D26 --| 10 [ ]    [ ] 29 |-- TX2 (GPIO 17) -> MAX485 DI
           (GPIO 27) D27 --| 11 [ ]    [ ] 28 |-- RX2 (GPIO 16) -> MAX485 RO
           (GPIO 14) D14 --| 12 [ ]    [ ] 27 |-- D4  (GPIO 4)  -> MAX485 DE+RE
           (GPIO 12) D12 --| 13 [ ]    [ ] 26 |-- D2  (GPIO 2)  (Onboard LED)
                     GND --| 14 [ ]    [ ] 25 |-- D15 (GPIO 15)
           (GPIO 13) D13 --| 15 [ ]    [ ] 24 |-- D8  (SD1)
            (SD2)     D9 --| 16 [ ]    [ ] 23 |-- D7  (SD0)
            (SD3)    D10 --| 17 [ ]    [ ] 22 |-- D6  (CLK)
            (CMD)    D11 --| 18 [ ]    [ ] 21 |-- D0  (GPIO 0)
          5V Power   VIN --| 19 [ ]    [ ] 20 |-- CLK
                           +--------USB-------+
```

### Complete Pin Connections

| Module | Pin | 38-Pin ESP32 Pin | Purpose & Electrical Requirement |
|---|---|---|---|
| **Analog pH Probe** | `SIG` / `AO` | **`D34`** (GPIO 34) | In series through **10kΩ protection resistor** (protects ADC1_CH6) |
| | `VCC` | `VIN` (5V) | Powered from 5V rail |
| | `GND` | `GND` | Common ground rail |
| **MAX485 Converter** | `RO` (RX) | **`RX2`** (GPIO 16) | Hardware UART2 Receive line |
| | `DI` (TX) | **`TX2`** (GPIO 17) | Hardware UART2 Transmit line |
| | `DE` & `RE` | **`D4`** (GPIO 4) | Jumpered together (High = Transmit, Low = Receive) |
| | `VCC` | `VIN` (5V) | TTL Transceiver power |
| | `GND` | `GND` | Common ground rail |
| | `A` & `B` | NPK Sensor `A` & `B` | Differential RS485 twisted-pair |
| **NPK Sensor (3-Prong)** | Brown Wire | **12V DC (+)** | External 12V 1A/2A DC power supply |
| | Black Wire | **12V DC (-)** | **CRITICAL: MUST bridge to ESP32 GND** |
| | Yellow Wire | MAX485 `A` | RS485 Non-inverting data |
| | Blue Wire | MAX485 `B` | RS485 Inverting data |
| **DS18B20 Temp Probe** | `DATA` | **`D5`** (GPIO 5) | **4.7kΩ pull-up resistor** to 3.3V |
| | `VCC` / `GND` | `3V3` / `GND` | 3.3V logic level |
| **DHT11 Air Sensor** | `DATA` | **`D18`** (GPIO 18) | Single-bus digital temperature & humidity |
| | `VCC` / `GND` | `3V3` / `GND` | 3.3V logic level |
| **16×2 I2C LCD Display** | `SDA` | **`D21`** (GPIO 21) | Hardware I2C Data (`0x27`) |
| | `SCL` | **`D22`** (GPIO 22) | Hardware I2C Clock |
| | `VCC` / `GND` | `VIN` (5V) / `GND` | 5V supply for display contrast & backlight |

*For complete wiring diagrams and step-by-step assembly, see [`docs/setup.md`](docs/setup.md).*

---

## The 3-Pillar Console & UI Design

The web interface (`app/templates/dashboard.html`) is structured into 3 distinct functional pillars:

```text
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ ◉ 01 / RECOMMENDED CROP                                                     │
 │ PRIMARY CULTIVAR SPECIMEN                                                   │
 │ Rice                                      [ 98.4% match ]                   │
 │ Runner-ups: Jute (1.4%) · Maize (0.2%)                                      │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ ◉ 02 / FERTILIZER MIX                                                       │
 │ [ Urea + DAP ]  [ Agricultural Lime ]                                       │
 │ Dosage: Urea ≈55 kg/ha · DAP ≈60 kg/ha · Lime ≈400 kg/ha                    │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │ ◉ 03 / WHY RICE FITS YOUR SOIL                                              │
 │ [ 92% soil match ]                                                          │
 │ • Humidity: 82.0% (Ideal match)  • Soil pH: 6.50 (Ideal match)              │
 │ • Nitrogen: 90 mg/kg (Good fit)  • Phosphorus: 42 mg/kg (Good fit)          │
 └─────────────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```text
├── app/
│   ├── app.py                     # Flask web server, serial/Wi-Fi telemetry & ML API
│   ├── templates/
│   │   └── dashboard.html         # Mint Greenhouse 3-pillar console template
│   └── static/
│       ├── css/soilsage.css       # Complete botanical design styling
│       ├── js/dashboard.js        # Live polling (2s), Chart.js & UI update engine
│       └── vendor/                # Offline Tabler & Chart.js dependencies
├── ml/
│   ├── ebm_model.py               # AgronomicEBMClassifier architecture & agronomy knowledge base
│   ├── dataset/
│   │   └── Crop_recommendation.csv # 22-crop multi-nutrient agricultural dataset
│   ├── model/
│   │   └── soil_model.pkl         # Serialized EBM model (pickle protocol 4)
│   └── training/
│       ├── train_ebm.py           # Standalone training script
│       └── train.ipynb            # Jupyter evaluation notebook
├── scripts/
│   ├── demo_samples.py            # Interactive 3-soil sample evaluation & matrix tool
│   ├── ser_script.py              # Standalone CLI bridge for USB serial hardware
│   └── sim_script.py              # Standalone simulation CLI demo
├── esp32/
│   ├── esp32_full_serial/         # USB Serial firmware (38-Pin ESP32 + LCD)
│   ├── esp32_full/                # Wi-Fi HTTP POST firmware (38-Pin ESP32 + LCD)
│   └── esp32_test/                # Standalone diagnostic sketches (read_npk, test_ph)
├── docs/
│   ├── setup.md                   # Complete 38-Pin ESP32 wiring & calibration guide
│   └── component_list.md          # Bill of materials and hardware specifications
├── README.md                      # Primary project documentation
└── repo.zip                       # Synchronized repository archive
```

---

## Installation & Quickstart

### 1. Clone or Extract the Repository
```bash
git clone https://github.com/nanoraptor/SoilSage.git
cd SoilSage
```

### 2. Install Python Dependencies
```bash
python3 -m pip install pandas joblib pyserial scikit-learn flask
```

### 3. Flash the 38-Pin ESP32 Firmware
1. Open [`esp32/esp32_full_serial/esp32_full_serial.ino`](esp32/esp32_full_serial/esp32_full_serial.ino) in Arduino IDE.
2. Select **Board:** `ESP32 Dev Module` and your serial port (`/dev/ttyUSB0` or `COM3`).
3. Click **Upload** ($\rightarrow$).
4. Close the Arduino IDE Serial Monitor before starting the Python server.

---

## Running the Application

### 🌐 Web Dashboard Console

```bash
# Recommended: USB Serial connection to ESP32
python3 app/app.py --serial

# Simulation Mode (Software demonstration without hardware)
python3 app/app.py --sim

# Wi-Fi Mode (Receives HTTP POST payloads from ESP32)
python3 app/app.py --esp32
```
Open **`http://127.0.0.1:5000`** in your browser.  
*(Press `Ctrl + Shift + R` for a clean cache reload).*

---

### 🧪 Interactive 3-Soil Sample Demo Tool

Designed specifically for project evaluations, viva presentations, and comparing 3 distinct soil samples:

```bash
# Option A: Run simulated dry-run rehearsal with 3 agronomic archetypes
python3 scripts/demo_samples.py --simulate

# Option B: Live capture with connected 38-Pin ESP32
python3 scripts/demo_samples.py --serial

# Option C: Interactive menu (evaluate samples 1, 2, 3 individually and compare)
python3 scripts/demo_samples.py
```

The tool records readings for Sample 1, Sample 2, and Sample 3 and generates a side-by-side **Comparative Agronomic Matrix**:

```text
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║                     SOILSAGE 3-SAMPLE COMPARATIVE AGRONOMIC MATRIX                       ║
╠════════════════════════════╦═════════════════════╦═════════════════════╦═════════════════════╣
║ Parameter                  ║ Sample 1            ║ Sample 2            ║ Sample 3            ║
╠════════════════════════════╬═════════════════════╬═════════════════════╬═════════════════════╣
║ Soil pH                    ║ 6.5                 ║ 6.8                 ║ 5.2                 ║
║ Nitrogen (N)               ║ 90.0 mg/kg          ║ 22.0 mg/kg          ║ 40.0 mg/kg          ║
║ Phosphorus (P)             ║ 42.0 mg/kg          ║ 60.0 mg/kg          ║ 65.0 mg/kg          ║
║ Potassium (K)              ║ 43.0 mg/kg          ║ 20.0 mg/kg          ║ 145.0 mg/kg         ║
║ Temperature                ║ 26.5°C              ║ 31.0°C              ║ 28.0°C              ║
╟────────────────────────────╫─────────────────────╫─────────────────────╫─────────────────────╢
║ Recommended Crop           ║ Jute                ║ Mothbeans           ║ Apple               ║
║ AI Match Score             ║ 92.6%               ║ 94.1%               ║ 99.9%               ║
╟────────────────────────────╫─────────────────────╫─────────────────────╫─────────────────────╢
║ pH Remedy                  ║ Balanced            ║ Balanced            ║ Lime (CaCO3)        ║
║ Primary Fertilizer         ║ NPK 19-19-19        ║ NPK 19-19-19        ║ NPK 12-12-17        ║
╚════════════════════════════╩═════════════════════╩═════════════════════╩═════════════════════╝
```

---

### 💻 Standalone Terminal CLI Scripts

```bash
# Direct terminal execution without launching the browser
python3 scripts/ser_script.py --port=/dev/ttyUSB0
```

---

## Command Line Flags & Options

### Web App (`app/app.py`)

| Flag | Description |
|---|---|
| *(no flags)* | Starts in **SIM** (simulation) mode by default. |
| `--sim` | Explicitly starts in **SIM** mode. |
| `--serial` | Starts in **SERIAL** mode and auto-detects active port (`/dev/ttyUSB*`). |
| `--serial <PORT>` | Binds directly to a specific port (e.g. `--serial /dev/ttyUSB0`). |
| `--esp32` | Starts in **Wi-Fi Mode** listening on `0.0.0.0:5000` for ESP32 POST packets. |
| `--lock-mode` | Locks the mode selector dropdown in the browser UI. |
| `--no-check` | Disables strict pH bounds clamping for testing extreme buffers. |

---

## Explainable AI Model (EBM)

Unlike black-box neural networks, SoilSage employs an **Explainable Boosting Machine (EBM)** rooted in Generalized Additive Models with pairwise interactions:

$$g(E[y]) = \beta_0 + \sum_{j=1}^{M} f_j(x_j) + \sum_{i \ne j} f_{ij}(x_i, x_j)$$

- **Validation Accuracy:** **99.55%** on stratified 80/20 train/test evaluation across 2,200 agricultural specimens.
- **Input Dimensions (7):** `Nitrogen`, `phosphorus`, `potassium`, `temperature`, `humidity`, `ph`, `rainfall`.
- **Crops Supported (22):** Rice, Maize, Chickpea, Kidneybeans, Pigeonpeas, Mothbeans, Mungbean, Blackgram, Lentil, Pomegranate, Banana, Mango, Grapes, Watermelon, Muskmelon, Apple, Orange, Papaya, Coconut, Cotton, Jute, Coffee.
- **Model Re-training:**
  ```bash
  python3 ml/training/train_ebm.py
  ```

---

## Troubleshooting & FAQ

#### 1. Why does the dashboard say "ESP32 frozen or disconnected"?
The Arduino IDE Serial Monitor is likely open. In Linux, only one application can access `/dev/ttyUSB0` at a time. Close the Serial Monitor tab in Arduino IDE, then restart `python3 app/app.py --serial`.

#### 2. Why does the dashboard say "NPK Sensor Disconnected"?
1. Check that the external **12V DC power supply ground is connected to the ESP32 GND** (Common Ground).
2. Check MAX485 connections: `RO` $\rightarrow$ `RX2` (GPIO 16), `DI` $\rightarrow$ `TX2` (GPIO 17), `DE/RE` tied together to `D4` (GPIO 4).
3. Verify that the sensor is receiving at least 9V–12V DC power.

#### 3. Why does the screen say "Please insert soil sample"?
When the sensor prongs are dry or in air, conductivity is 0 ($N=0, P=0, K=0$). SoilSage intentionally suppresses default crop predictions. Insert the prongs firmly into a moist soil sample to obtain live agronomic recommendations.
