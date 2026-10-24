# SoilSage: AI-Driven Precision Soil Sustainability

## Overview

**SoilSage** is a cyber-physical system designed to combat soil acidification, nutrient depletion, and fertilizer runoff. By integrating real-time IoT soil sensors with an **Agronomic Explainable Boosting Machine (EBM)**, the system analyzes field chemistry, predicts the optimal crop, and provides precise neutralization strategies through customized crop and fertilizer recommendations accompanied by farmer-friendly explanations.

**Course:** ECS2001 — Project Ideation, Design and Prototyping  
**Created by:** Rahul, Abhiram, Nikhil, Sanjeev, Saketh and Shyam

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [The 3-Pillar Architecture & UI](#the-3-pillar-architecture--ui)
- [Project Structure](#project-structure)
- [Hardware & Sensor Setup](#hardware--sensor-setup)
- [Installation](#installation)
- [Running the Application](#running-the-application)
  - [Web Dashboard](#-web-dashboard)
  - [Terminal CLI Scripts](#-terminal-cli-scripts)
- [Command Line Flags & Options](#command-line-flags--options)
- [Explainable AI Model & Training](#explainable-ai-model--training)

---

## Key Features

- **Multi-Parameter Hardware Sensing:** Real-time acquisition of Soil pH, Nitrogen (N), Phosphorus (P), Potassium (K), Soil Solution Temperature (DS18B20), and Ambient Air Temperature/Humidity (DHT11) via ESP32.
- **Explainable Boosting Machine (EBM):** Replaced legacy black-box models with `AgronomicEBMClassifier`, achieving **99.55% validation accuracy** across 22 crops with biological response curves.
- **Farmer-Friendly Explanations:** Explains *why* a crop was chosen in plain English, highlighting ideal nutrient ranges, overall soil suitability percentage, and comparisons against the runner-up crop.
- **Adaptive Fertilizer & pH Correction:** Tailored fertilizer formulation (NPK ratios, urea, SSP/DAP, MOP) with pH correction advisories (Agricultural Lime for acidic soil, Organic Compost for alkaline soil).
- **Online 30-Day Rainfall Sync:** Automatically fetches rolling 30-day precipitation for your field coordinates via Open-Meteo, with graceful caching and manual overrides.
- **Robust Modbus RTU Engine:** Resilient RS485 communication with a 300 ms response window, stale buffer clearing, and automatic frame header validation.
- **Mint Greenhouse Visual Console:** Built on the `Design.md` aesthetic system (`#b7ffb4` Mint canvas, `#262626` Carbon Ink borders, `#00ff00` Lime botanical specimen accents, and monospace JetBrains Mono metrics).

---

## The 3-Pillar Architecture & UI

The console is structured around three actionable pillars:

1. **Pillar 01 — Recommended Crop:** Monumental display typography showing the top predicted crop, suitability match percentage, litmus pH gauge, and top-3 alternative crop rankings with probability chips.
2. **Pillar 02 — Fertilizer Mix:** Customized chemical and organic fertilizer formulation, target NPK nutrient progress bars, and pH balancing advisories.
3. **Pillar 03 — Why This Crop Fits Your Soil:** Interpretability cards displaying each nutrient's fit (`Ideal match`, `Good fit`, `Needs boost`, `Watch level`), the crop's biological ideal window vs. field measurement, and comparative reasoning against the next-best alternative.
4. **Supporting Telemetry:** Real-time sensor tiles with missing-probe detection (`— mg/kg`), 40-poll pH trend line chart, GPS coordinate picker, and verbatim ESP32 probe telemetry inspection.

---

## Project Structure

```text
├── app/
│   ├── app.py                     # Flask web server, serial/Wi-Fi engine & ML API
│   ├── templates/
│   │   └── dashboard.html         # Mint Greenhouse 3-pillar console template
│   └── static/
│       ├── css/soilsage.css       # Complete Design.md botanical styling
│       ├── js/dashboard.js        # Live polling (2s), Chart.js & explanation renderer
│       └── vendor/                # Tabler & Chart.js offline dependencies
├── ml/
│   ├── __init__.py                # Package exports & backward-compatibility aliases
│   ├── ebm_model.py               # AgronomicEBMClassifier architecture & agronomy knowledge base
│   ├── dataset/
│   │   └── Crop_recommendation.csv # 22-crop multi-nutrient agricultural dataset
│   ├── model/
│   │   └── soil_model.pkl         # Serialized EBM model (pickle protocol 4)
│   └── training/
│       ├── train_ebm.py           # Standalone reproducible training script
│       └── train.ipynb            # Interactive evaluation & training notebook
├── scripts/
│   ├── ser_script.py              # Standalone CLI bridge for USB serial hardware
│   └── sim_script.py              # Standalone simulation CLI demo
├── esp32/
│   ├── esp32_full_serial/         # USB Serial firmware (Modbus RTU NPK + DS18B20 + DHT11 + pH)
│   ├── esp32_full/                # Wi-Fi HTTP POST firmware
│   └── esp32_test/                # Diagnostic sketches (I2C scanner, NPK baud sweep, pH calibration)
├── docs/
│   ├── setup.md                   # Wiring pinout, resistor protection & buffer calibration
│   └── component_list.md          # Bill of materials and hardware specifications
├── CHANGES.md                     # Detailed upgrade manifest
└── README.md                      # Project documentation
```

---

## Hardware & Sensor Setup

Refer to [`docs/setup.md`](docs/setup.md) for full wiring tables and component specifications.

- **Main Controller:** ESP32 DevKit V1 (30-pin or 38-pin).
- **NPK Sensor:** RS485 Modbus RTU 3-probe sensor powered by an external 9V–24V DC supply (common ground tied to ESP32).
  - MAX485 `DE` + `RE` $\rightarrow$ **GPIO 4**
  - MAX485 `RO` $\rightarrow$ **GPIO 16 (RX2)**
  - MAX485 `DI` $\rightarrow$ **GPIO 17 (TX2)**
  - MAX485 `A`/`B` $\rightarrow$ NPK Yellow (A) / Blue (B)
- **pH Probe:** Analog electrode with BNC amplifier module $\rightarrow$ 10kΩ series protection resistor $\rightarrow$ **GPIO 34**.
  - Calibrated with SDFCL pH 4.0, 7.0, and 9.2 buffer capsules:  
    `PH_VOLTAGE_PH7 = 1.114V`, `PH_SLOPE_ACID = 0.1805`, `PH_SLOPE_ALKALINE = 0.1438`.
- **Soil Solution Temperature:** Dallas DS18B20 waterproof probe $\rightarrow$ **GPIO 5** (4.7kΩ pull-up).
- **Air Temperature & Humidity:** DHT11 $\rightarrow$ **GPIO 18**.
- **Local LCD:** 16x2 I2C Display (`0x27`) $\rightarrow$ SDA **GPIO 21**, SCL **GPIO 22**.

---

## Installation

1. Clone or extract the repository:
   ```bash
   git clone https://github.com/nanoraptor/SoilSage.git
   cd SoilSage
   ```

2. Install Python dependencies:

   **Linux / macOS:**
   ```bash
   python3 -m pip install pandas joblib pyserial scikit-learn flask
   ```

   **Windows:**
   ```powershell
   py -m pip install pandas joblib pyserial scikit-learn flask
   ```

---

## Running the Application

### 🌐 Web Dashboard

Start the local Flask dashboard:

```bash
# Serial Mode (Recommended for USB connection to ESP32)
python3 app/app.py --serial

# Simulation Mode (Software demonstration without hardware)
python3 app/app.py --sim

# Wi-Fi Mode (Listens for incoming HTTP POST packets from ESP32)
python3 app/app.py --esp32
```

Open your browser at `http://127.0.0.1:5000`.

- Click **Use browser location** or enter latitude and longitude to fetch local rolling 30-day rainfall from Open-Meteo.
- Readings poll automatically every 2 seconds. Press `M` to reveal or hide the mode switcher.

### 💻 Terminal CLI Scripts

Run the pipeline directly from the command line without launching the web server:

```bash
# Simulation mode with synthetic soil telemetry
python3 scripts/sim_script.py

# USB Serial mode connected directly to ESP32
python3 scripts/ser_script.py --port=/dev/ttyUSB0
```

---

## Command Line Flags & Options

### Web App (`app/app.py`)

| Flag | Description |
|---|---|
| *(no flags)* | Starts in **SIM** (simulation) mode by default. |
| `--sim` | Explicitly starts in **SIM** mode. |
| `--serial` | Starts in **SERIAL** mode and auto-detects active port (`/dev/ttyUSB*` or `/dev/ttyACM*`). |
| `--serial <PORT>` | Starts in **SERIAL** mode binding directly to the specified port (e.g. `/dev/ttyUSB0` or `COM3`). |
| `--esp32` | Starts in **Wi-Fi Mode** listening on `0.0.0.0:5000` for ESP32 POST payloads. |
| `--lock-mode` | Locks the mode dropdown in the web UI. |
| `--no-check` | Disables strict pH range clamping for testing extreme buffer inputs. |

### CLI Scripts (`scripts/sim_script.py`, `scripts/ser_script.py`)

| Flag | Description |
|---|---|
| `--location <LAT> <LON>` | Fetches 30-day rainfall from Open-Meteo for the given coordinates. |
| `--rainfall_data <VALUE>` | Overrides rainfall directly in millimeters (e.g. `--rainfall_data 120.0`). |
| `--port <PORT>` | *(ser_script only)* Specifies serial port to connect (default: `/dev/ttyACM0`). |

---

## Explainable AI Model & Training

### Architecture: `AgronomicEBMClassifier`

Unlike standard black-box classifiers, SoilSage uses an **Explainable Boosting Machine (EBM)** rooted in Generalized Additive Models (GAM):

$$g(E[y]) = \beta_0 + \sum_{j=1}^{M} f_j(x_j)$$

- **Accuracy:** **99.55% validation accuracy** on an 80/20 stratified split across 2,200 agricultural samples.
- **Input Features:** `Nitrogen`, `phosphorus`, `potassium`, `temperature`, `humidity`, `ph`, `rainfall`.
- **Interpretability:**
  - Evaluates per-crop biological tolerance curves for all 7 soil and atmospheric factors.
  - Automatically identifies which factors are within the crop's ideal biological window vs. which nutrients need soil amendment.
  - Generates plain-English summaries and direct pairwise explanations against the runner-up crop.

### Re-training the Model

To train and regenerate `ml/model/soil_model.pkl`:

```bash
# Option 1: Standalone training script
python3 ml/training/train_ebm.py

# Option 2: Jupyter Notebook
jupyter notebook ml/training/train.ipynb
```
The resulting model artifact is serialized using standard pickle protocol 4 and loaded automatically by `app/app.py`, `scripts/ser_script.py`, and `scripts/sim_script.py`.
