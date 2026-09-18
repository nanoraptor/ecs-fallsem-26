# SoilSage: AI-Driven Precision Soil Sustainability

## Overview

This is a cyber-physical system designed to combat soil acidification and nutrient runoff—major environmental concerns in modern chemistry. By integrating IoT sensors with a Random Forest Machine Learning model, the system identifies the soil's chemical state and provides precise neutralization strategies through recommendations of crops and fertilizers.

**Course:** ECS2001 - Project Ideation, Design and Prototyping  
**Created by:** Rahul, Abhiram, Nikhil, Sanjeev, Saketh and Shyam

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Running the Application](#running-the-application)
  - [Browser Dashboard](#-browser-dashboard)
  - [Command Line](#command-line)
- [Flags and Options](#flags-and-options)
- [ML Algorithm & Training](#ml-algorithm--training)

---

## Features

- **Hardware Sensing:** Real-time pH, NPK, Soil Temperature (DS18B20), and Air Temperature/Humidity (DHT11) monitoring via ESP32.
- **Cloud Rainfall Input:** 30-day rainfall is fetched online by location (Open-Meteo) for model input.
- **AI Inference:** Random Forest Classifier trained on agricultural datasets.
- **Smart Recommendations:** Crop prediction + fertilizer suggestion with pH-aware chemistry advice.

## Project Structure

- `app/app.py`: Browser dashboard (live readings + crop + fertilizer recommendation).
- `scripts/`: Contains utility scripts.
  - `ser_script.py`: Local Python bridge between ESP32 and ML model.
  - `sim_script.py`: Simulation script for software-only demonstration.
- `random_forest/`: Contains all machine learning related files.
  - `dataset/`: Contains the dataset used for training.
  - `model/`: Contains the serialized Random Forest model.
  - `training/`: Contains the training Jupyter notebook.
- `docs/setup.md`: Required hardware components and ESP32 wiring map.
- `esp32/`: Directory containing ESP32 firmware files for data acquisition.

## Setup

Before proceeding, set up the hardware per `docs/setup.md` and flash `esp32/esp32_full/esp32_full.ino` via ESP32 IDE.

1. Connect the ESP32 to your computer (for live/serial mode). This is commonly `/dev/ttyACM0` or `/dev/ttyUSB0` for Linux/macOS, or `COM3` for Windows.
2. Install dependencies:

**Linux / macOS:**
```bash
python3 -m pip install pandas joblib pyserial scikit-learn flask
```

**Windows:**
```powershell
py -m pip install pandas joblib pyserial scikit-learn flask
```

## Running the Application

### 🌐 Browser Dashboard

Start the local web dashboard:
```bash
# Simulation mode (default)
python3 app/app.py

# Wi-Fi mode (listen for ESP32)
python3 app/app.py --esp32

# Serial mode (connect to ESP32 via USB)
python3 app/app.py --serial
```
Open `http://127.0.0.1:5000` in your browser.

- Set your coordinates using **Use Browser Location** or manual latitude/longitude.
- The app fetches **rolling 30-day rainfall (mm)** online and feeds it to the model.
- If location/weather fetch is unavailable, the app falls back to cached or default rainfall and shows the source status in the UI.

### Command Line

You can run the core logic purely from the terminal without the web UI:

**Linux / macOS:**
```bash
# Simulation mode
python3 scripts/sim_script.py

# Serial mode connected to ESP32
python3 scripts/ser_script.py --port=/dev/ttyACM0
```

**Windows:**
```powershell
# Simulation mode
py scripts/sim_script.py

# Serial mode connected to ESP32
py scripts/ser_script.py --port=COM3
```

## Flags and Options

### App flags (`app/app.py`)

- `app/app.py` → starts in **SIM** mode
- `--sim` → explicitly starts in **SIM** mode
- `--serial <PORT>` → starts in **SERIAL** mode
- `--serial` → starts in **SERIAL** mode and auto-detects the port if `/dev/ttyACM0` is unavailable
- `--esp32` → starts the app in **Wi-Fi Mode** listening on `0.0.0.0` for POST requests from the ESP32.
- `--lock-mode` → hides the mode selector and prevents switching modes during runtime
- `--no-check` → skips strict pH input range validation (chemical status still shown)

> **Note:** The mode selector can be hidden by pressing 'm' in normal mode.

### Script Flags (`scripts/sim_script.py`, `scripts/ser_script.py`)

These scripts support optional flags to provide rainfall data:

- `--location <LAT> <LON>`: Fetches 30-day rainfall data from Open-Meteo based on the provided latitude and longitude.
  - If the API call fails, the script falls back to `--rainfall_data`, or a default value (100.0mm).
- `--rainfall_data <VALUE>`: Directly specifies the 30-day rainfall value in millimeters.

**Examples:**
```bash
# Simulation with location-based rainfall
python3 scripts/sim_script.py --location 34.0522 -118.2437

# Serial with direct rainfall data
python3 scripts/ser_script.py --port=/dev/ttyACM0 --rainfall_data 150.0
```

## ML Algorithm & Training

### Model Details
- **Algorithm:** `RandomForestClassifier`
- **Input features (strict order):** `Nitrogen`, `phosphorus`, `potassium`, `temperature`, `humidity`, `ph`, `rainfall`
- **Target label:** `label` (crop name)
- **Train/test split:** `80/20` using `train_test_split(..., test_size=0.2, random_state=42)`
- **Model params:** `n_estimators=100`, `random_state=42`
- **Saved model artifact:** `random_forest/model/soil_model.pkl` (via `joblib.dump`)

### Training Environment
- Trained in **Jupyter Notebook**.
- Training code is located in `random_forest/training/train.ipynb`.
- Dataset schema follows `random_forest/dataset/Crop_recommendation.csv`.

### Using the trained model in this project
1. Place the generated `soil_model.pkl` in the `random_forest/model/` directory.
2. Ensure runtime feature order exactly matches training feature order.
3. Run `scripts/ser_script.py`, `scripts/sim_script.py`, or `app/app.py` to load the model and predict crops.
