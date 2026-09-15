import argparse
import os
import sys
import time
import json
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode
from datetime import date, timedelta

import joblib
import pandas as pd

try:
    import serial
    from serial import SerialException
except ModuleNotFoundError:
    print("Error: pyserial is not installed. Run: pip install pyserial")
    sys.exit(1)

PH_ADC_MAX = 1023.0
PH_ADC_REF_VOLTAGE = 5.0
PH_VOLTAGE_PH7 = 1.251
PH_VOLTAGE_PH4 = 1.769
PH_SLOPE = (PH_VOLTAGE_PH4 - PH_VOLTAGE_PH7) / 3.0
DEFAULT_HUMIDITY = 60.0
DEFAULT_RAINFALL_MM = 100.0
RAINFALL_WINDOW_DAYS = 30
WEATHER_HTTP_TIMEOUT_SECONDS = 8

COLS = [
    "Nitrogen",
    "phosphorus",
    "potassium",
    "temperature",
    "humidity",
    "ph",
    "rainfall",
]


def ph_from_raw_adc(raw_adc: float):
    voltage = (raw_adc * PH_ADC_REF_VOLTAGE) / PH_ADC_MAX
    return 7.0 - ((voltage - PH_VOLTAGE_PH7) / PH_SLOPE)


def parse_serial_line(line: str, rainfall: float):
    parts = line.strip().split(",")
    numeric = [float(x) for x in parts]
    if len(numeric) == 7:
        if 14.0 < numeric[5] <= PH_ADC_MAX:
            numeric[5] = ph_from_raw_adc(numeric[5])
        numeric[6] = rainfall
        return numeric
    if len(numeric) == 6:
        # ESP32 packet format: phValueOrRaw,n,p,k,dhtTemp,humidity
        ph_raw, n, p, k, temp, hum = numeric
        if 14.0 < ph_raw <= PH_ADC_MAX:
            ph_raw = ph_from_raw_adc(ph_raw)
        return [n, p, k, temp, hum, ph_raw, rainfall]
    if len(numeric) == 5:
        # Fallback packet format: phValueOrRaw,n,p,k,dhtTemp
        ph_raw, n, p, k, temp = numeric
        if 14.0 < ph_raw <= PH_ADC_MAX:
            ph_raw = ph_from_raw_adc(ph_raw)
        return [
            n,
            p,
            k,
            temp,
            DEFAULT_HUMIDITY,
            ph_raw,
            rainfall,
        ]
    raise ValueError("Expected 5, 6, or 7 comma-separated values")


def fetch_rainfall_data(latitude: float, longitude: float):
    end_date = date.today()
    start_date = end_date - timedelta(days=RAINFALL_WINDOW_DAYS - 1)
    params = {
        "latitude": f"{latitude:.6f}",
        "longitude": f"{longitude:.6f}",
        "daily": "precipitation_sum",
        "past_days": str(RAINFALL_WINDOW_DAYS),
        "forecast_days": "0",
        "timezone": "auto",
    }
    url = f"https://api.open-meteo.com/v1/forecast?{urlencode(params)}"

    with urlopen(url, timeout=WEATHER_HTTP_TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8"))

    daily = payload.get("daily", {})
    time_values = daily.get("time")
    precipitation = daily.get("precipitation_sum")
    if (
        not isinstance(time_values, list)
        or not isinstance(precipitation, list)
        or not precipitation
        or len(time_values) != len(precipitation)
    ):
        raise RuntimeError("Weather API returned no precipitation data")

    rainfall_values = []
    for day_text, value in zip(time_values, precipitation):
        if value is None:
            continue
        try:
            day_value = date.fromisoformat(str(day_text))
        except ValueError:
            continue
        if start_date <= day_value <= end_date:
            rainfall_values.append(max(float(value), 0.0))

    if not rainfall_values:
        raise RuntimeError("Weather API precipitation values were empty")

    return float(sum(rainfall_values))


def resolve_soil_model_path():
    env_model_path = os.getenv("SOIL_MODEL_PATH")
    checked_paths = []
    if env_model_path:
        configured_path = Path(env_model_path).expanduser()
        if not configured_path.is_absolute():
            configured_path = (Path.cwd() / configured_path).resolve()
        checked_paths.append(configured_path)
        if configured_path.is_file():
            return configured_path
        raise FileNotFoundError(
            f"SOIL_MODEL_PATH points to a missing file: {configured_path}"
        )

    script_dir = Path(__file__).resolve().parent
    roots = [Path.cwd(), script_dir, script_dir.parent]
    relative_paths = (
        Path("soil_model.pkl"),
        Path("model") / "soil_model.pkl",
        Path("random_forest") / "model" / "soil_model.pkl",
    )
    seen = set()

    for root in roots:
        for relative_path in relative_paths:
            candidate = (root / relative_path).resolve()
            if candidate in seen:
                continue
            seen.add(candidate)
            checked_paths.append(candidate)
            if candidate.is_file():
                return candidate

    checked_display = ", ".join(str(path) for path in checked_paths)
    raise FileNotFoundError(f"soil_model.pkl not found. Checked: {checked_display}")


try:
    model = joblib.load(resolve_soil_model_path())
except FileNotFoundError as exc:
    print(f"Error: {exc}")
    sys.exit(1)

parser = argparse.ArgumentParser(
    description="Read ESP32 serial data and run crop prediction."
)
parser.add_argument(
    "--port",
    default=os.getenv("ESP32_PORT", "/dev/ttyACM0"),
    help="ESP32 serial port (example: /dev/ttyACM0 or COM3)",
)
parser.add_argument(
    "--location",
    nargs=2,
    type=float,
    metavar=("LAT", "LON"),
    help="Latitude and Longitude to fetch rainfall data.",
)
parser.add_argument(
    "--rainfall_data", type=float, help="Specify rainfall data directly."
)
args = parser.parse_args()

rainfall = DEFAULT_RAINFALL_MM
use_default_warning = False

if args.location is not None:
    try:
        print(f"Fetching rainfall data for location: {args.location}")
        fetched_rainfall = fetch_rainfall_data(args.location[0], args.location[1])
        print(f"Successfully fetched rainfall data: {fetched_rainfall:.2f}mm")
        rainfall = fetched_rainfall
    except Exception as e:
        print(f"Warning: Failed to fetch rainfall data from location ({e}).")
        if args.rainfall_data is not None:
            print(f"Falling back to rainfall_data flag: {args.rainfall_data}mm")
            rainfall = args.rainfall_data
        else:
            use_default_warning = True
elif args.rainfall_data is not None:
    rainfall = args.rainfall_data
else:
    use_default_warning = True

if use_default_warning:
    print(f"Using default rainfall value: {DEFAULT_RAINFALL_MM}mm")

port = args.port
try:
    ser = serial.Serial(port, 9600, timeout=1)
except SerialException as exc:
    print(f"Error: cannot open serial port {port}: {exc}")
    sys.exit(1)

time.sleep(2)
print(f"System Live. Reading Soil Chemistry from {port}...")

try:
    while True:
        if ser.in_waiting <= 0:
            continue

        line = ser.readline().decode("utf-8", errors="replace").strip()
        if not line:
            continue

        try:
            values = parse_serial_line(line, rainfall)
        except (ValueError, IndexError) as e:
            print(f"Skipping malformed row: {line} ({e})")
            continue

        current_readings = pd.DataFrame([values], columns=COLS)
        prediction = model.predict(current_readings)[0]

        print(f"--- Sensor Data: {line} ---")
        print(f"--- Rainfall: {rainfall:.2f}mm ---")
        print(f"Recommended Crop: {prediction}")

        ph_val = values[5]
        if ph_val < 5.5:
            print("ACTION: Soil is acidic. Suggest adding Lime (CaCO3).")
        elif ph_val > 7.5:
            print("ACTION: Soil is alkaline. Suggest adding organic mulch.")
        else:
            print("ACTION: pH is in balanced range.")
except KeyboardInterrupt:
    print("\nStopped by user.")
finally:
    ser.close()
