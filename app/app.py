#!/usr/bin/env python3
import argparse
import glob
import json
import os
import random
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Lock
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import joblib
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_from_directory

VALID_MODES = {"sim", "serial", "esp32"}
PH_ADC_MAX = 1023.0
PH_ADC_REF_VOLTAGE = 5.0
PH_VOLTAGE_PH7 = 1.114
PH_SLOPE_ACID = 0.1805
PH_SLOPE_ALKALINE = 0.1438
PH_SLOPE = PH_SLOPE_ACID
DEFAULT_HUMIDITY = 60.0
DEFAULT_RAINFALL_MM = 100.0
RAINFALL_WINDOW_DAYS = 30
WEATHER_CACHE_TTL_SECONDS = 1800
WEATHER_HTTP_TIMEOUT_SECONDS = 8


def parse_start_mode_args(argv):
    parser = argparse.ArgumentParser(description="Run the SoilSage dashboard server.")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--sim", action="store_true", help="Start in simulation mode")
    mode_group.add_argument("--serial", action="store_true", help="Start in serial mode")
    mode_group.add_argument("--esp32", action="store_true", help="Start in ESP32 WiFi mode")
    parser.add_argument(
        "--no-check",
        action="store_true",
        help="Disable strict pH input range validation",
    )
    parser.add_argument(
        "--lock-mode",
        action="store_true",
        help="Hide mode selector and lock the startup mode",
    )
    parser.add_argument(
        "serial_port",
        nargs="?",
        help="Serial port for --serial (example: /dev/ttyACM0 or COM3)",
    )
    args, _ = parser.parse_known_args(argv)
    if args.serial_port and not args.serial:
        parser.error("serial_port can only be used with --serial")
    if args.sim:
        return "sim", None, args.lock_mode, args.no_check
    if args.serial:
        return "serial", args.serial_port, args.lock_mode, args.no_check
    if args.esp32:
        return "esp32", None, args.lock_mode, args.no_check
    return None, None, args.lock_mode, args.no_check


CLI_MODE_OVERRIDE, CLI_PORT_OVERRIDE, CLI_LOCK_MODE, CLI_NO_CHECK = (
    parse_start_mode_args(sys.argv[1:])
    if __name__ == "__main__"
    else (None, None, False, False)
)



def evaluate_ph(ph_val: float):
    if ph_val < 5.5:
        return (
            "Acidic soil detected",
            "Apply Lime (CaCO3) to neutralize acidity.",
            "bad",
        )
    if ph_val > 7.5:
        return (
            "Alkaline soil detected",
            "Add organic matter/mulch to improve soil balance.",
            "warn",
        )
    return (
        "Chemical equilibrium maintained",
        "pH is in the balanced range.",
        "ok",
    )


def ph_from_raw_adc(raw_adc: float):
    voltage = (raw_adc * PH_ADC_REF_VOLTAGE) / PH_ADC_MAX
    slope = PH_SLOPE_ACID if voltage > PH_VOLTAGE_PH7 else PH_SLOPE_ALKALINE
    return 7.0 - ((voltage - PH_VOLTAGE_PH7) / slope)


def parse_serial_line(line: str):
    parts = line.strip().split(",")
    numeric = [float(x) for x in parts]
    if len(numeric) == 7:
        # ESP32 packet format: phValueOrRaw,n,p,k,dhtTemp,humidity,waterTemp
        ph_raw, n, p, k, temp, hum, water_temp = numeric
        if 14.0 < ph_raw <= PH_ADC_MAX:
            ph_raw = ph_from_raw_adc(ph_raw)
        return [n, p, k, temp, hum, ph_raw, DEFAULT_RAINFALL_MM, water_temp]
    if len(numeric) == 6:
        # OLD ESP32 packet format: phValueOrRaw,n,p,k,dhtTemp,humidity
        ph_raw, n, p, k, temp, hum = numeric
        if 14.0 < ph_raw <= PH_ADC_MAX:
            ph_raw = ph_from_raw_adc(ph_raw)
        return [n, p, k, temp, hum, ph_raw, DEFAULT_RAINFALL_MM, -1.0]
    if len(numeric) == 5:
        # Fallback packet format: phValueOrRaw,n,p,k,dhtTemp
        ph_raw, n, p, k, temp = numeric
        if 14.0 < ph_raw <= PH_ADC_MAX:
            ph_raw = ph_from_raw_adc(ph_raw)
        return [n, p, k, temp, -1.0, ph_raw, DEFAULT_RAINFALL_MM, -1.0]
    raise ValueError("Expected 5, 6, or 7 comma-separated values")


def recommend_fertilizer(crop: str, n: float, p: float, k: float, ph_val: float):
    crop_key = str(crop).strip().lower()
    crop_map = {
        "rice": "Urea + DAP",
        "maize": "NPK 20-20-0",
        "banana": "NPK 10-26-26",
        "apple": "NPK 12-12-17",
        "cotton": "NPK 20-10-10",
        "coffee": "NPK 17-17-17",
        "grapes": "NPK 19-19-19",
        "mango": "NPK 10-10-10",
        "chickpea": "SSP + MOP",
        "lentil": "SSP",
        "kidneybeans": "SSP + MOP",
    }
    base_fertilizer = crop_map.get(crop_key, "NPK 19-19-19")
    reasons = [f"Crop support for {crop_key or 'predicted crop'}."]
    additives = []

    if n < 50:
        additives.append("Urea (Nitrogen boost)")
        reasons.append("Nitrogen is low.")
    if p < 30:
        additives.append("SSP / DAP (Phosphorus boost)")
        reasons.append("Phosphorus is low.")
    if k < 30:
        additives.append("MOP (Potassium boost)")
        reasons.append("Potassium is low.")

    fertilizer_parts = [base_fertilizer] + additives

    if ph_val < 5.5:
        fertilizer_parts.append("Agricultural Lime")
        reasons.append("Soil is acidic, so lime is recommended.")
    elif ph_val > 7.5:
        fertilizer_parts.append("Organic Compost")
        reasons.append("Soil is alkaline, so organic matter is recommended.")

    fertilizer = " + ".join(fertilizer_parts)
    return fertilizer, " ".join(reasons)


def sanitize_input_values(values: list, skip_ph_check: bool = False):
    """
    Sanitizes a list of 8 sensor values.
    The order is N, P, K, temp, humidity, pH, rainfall, water_temp.
    Raises ValueError on validation failure.
    """
    if len(values) != 8:
        raise ValueError(f"Expected 8 values for sanitization, but got {len(values)}")

    sanitized = []
    labels = ["Nitrogen", "Phosphorus", "Potassium", "Temperature", "Humidity", "pH", "Rainfall", "Water Temp"]
    ranges = [
        (-10, 2000),  # N
        (-10, 2000),  # P
        (-10, 2000),  # K
        (-40, 60),    # Temp
        (-10, 100),   # Humidity
        (-10, 15),    # pH
        (-10, 1000),  # Rainfall
        (-130, 125),  # Water Temp
    ]

    import math
    for val, label, (min_val, max_val) in zip(values, labels, ranges):
        try:
            f_val = float(val)
            if math.isnan(f_val):
                f_val = -1.0
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid non-numeric value for {label}: {val}") from e

        if label == "pH" and 14.0 < f_val <= PH_ADC_MAX:
            # Handle sketches that send raw ADC pH (0-1023) instead of calibrated pH value.
            f_val = ph_from_raw_adc(f_val)

        if label == "pH" and skip_ph_check:
            sanitized.append(f_val)
            continue

        if not (min_val <= f_val <= max_val):
            raise ValueError(f"{label} value {f_val} is out of the acceptable range ({min_val} - {max_val})")
        sanitized.append(f_val)

    return sanitized


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

MODE = os.getenv("SOURCE_MODE", "sim").lower()
DEFAULT_SERIAL_PORT = "/dev/ttyACM0"
PORT = os.getenv("ESP32_PORT", DEFAULT_SERIAL_PORT)
BAUD = int(os.getenv("ESP32_BAUD", "115200"))
MODE_LOCKED = False
PH_RANGE_CHECK_ENABLED = True
SERIAL_READ_TIMEOUT_SECONDS = 0.5
SERIAL_READ_WINDOW_SECONDS = 3.0
if MODE not in VALID_MODES:
    MODE = "sim"

SER = None
SERIAL_MODULE = None
SERIAL_EXCEPTION = None
SERIAL_PORT_LIST = None
ACTIVE_PORT = PORT
LOCATION = {"latitude": None, "longitude": None, "source": "unset", "updated_at": None}
RAINFALL_CACHE = {}
LAST_RAINFALL = None

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
LATEST_READING = None
LATEST_READING_LOCK = Lock()
STATE_LOCK = Lock()
SERIAL_LOCK = Lock()
LOCATION_LOCK = Lock()
RAINFALL_LOCK = Lock()
LATEST_ESP32_RAW = None
LATEST_ESP32_VALUES = None
LATEST_ESP32_TIMESTAMP = 0.0


@app.get("/")
def index():
    return render_template("dashboard.html", mode_locked=MODE_LOCKED, mode=get_mode(), v=int(time.time()))

@app.get("/favicon.ico")
def favicon():
    return send_from_directory("static/img", "favicon.svg", mimetype="image/svg+xml")


def get_mode():
    with STATE_LOCK:
        return MODE


def close_serial_locked():
    global SER, ACTIVE_PORT
    if SER is not None:
        SER.close()
        SER = None
    ACTIVE_PORT = PORT


def list_serial_ports_locked():
    ports = []
    if SERIAL_PORT_LIST is not None:
        try:
            ports.extend(
                str(port.device).strip()
                for port in SERIAL_PORT_LIST.comports()
                if getattr(port, "device", None)
            )
        except Exception:
            pass

    if os.name != "nt":
        for pattern in (
            "/dev/ttyACM*",
            "/dev/ttyUSB*",
            "/dev/cu.usbmodem*",
            "/dev/cu.usbserial*",
        ):
            ports.extend(sorted(glob.glob(pattern)))

    unique_ports = []
    seen = set()
    for port in ports:
        if not port or port in seen:
            continue
        seen.add(port)
        unique_ports.append(port)
    return unique_ports


def get_active_port():
    with STATE_LOCK:
        return ACTIVE_PORT


def ensure_serial_ready_locked():
    global SERIAL_MODULE, SERIAL_EXCEPTION, SERIAL_PORT_LIST, SER, ACTIVE_PORT

    if SERIAL_MODULE is None:
        try:
            import serial as serial_module
            from serial import SerialException as serial_exception
            from serial.tools import list_ports as serial_port_list
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "pyserial missing. Install with: pip install pyserial"
            ) from exc
        SERIAL_MODULE = serial_module
        SERIAL_EXCEPTION = serial_exception
        SERIAL_PORT_LIST = serial_port_list

    if SER is None:
        available_ports = list_serial_ports_locked()
        candidate_ports = available_ports if available_ports else [PORT]
        connection_errors = []

        for candidate in candidate_ports:
            try:
                SER = SERIAL_MODULE.Serial(
                    candidate,
                    BAUD,
                    timeout=SERIAL_READ_TIMEOUT_SECONDS,
                )
                SER.dtr = False
                SER.rts = False
                ACTIVE_PORT = candidate
                SER.reset_input_buffer()
                break
            except SERIAL_EXCEPTION as exc:
                SER = None
                connection_errors.append(f"{candidate}: {exc}")

        if SER is None:
            attempted = ", ".join(candidate_ports) if candidate_ports else PORT
            detected = ", ".join(available_ports) if available_ports else "none"
            details = "; ".join(connection_errors) if connection_errors else "unknown"
            raise RuntimeError(
                f"ESP32 not connected. Tried ports: {attempted}. "
                f"Detected serial ports: {detected}. Open errors: {details}."
            )
    return SER


def switch_mode(new_mode: str):
    global MODE, LATEST_READING
    mode = str(new_mode).strip().lower()
    if mode not in VALID_MODES:
        raise ValueError(f"Mode must be one of: {', '.join(sorted(VALID_MODES))}")

    with STATE_LOCK:
        if mode == MODE:
            return MODE
        if mode != "serial":
            close_serial_locked()
        MODE = mode

    with LATEST_READING_LOCK:
        LATEST_READING = None
    return mode


def get_location_snapshot():
    with LOCATION_LOCK:
        return dict(LOCATION)


def set_location(latitude, longitude, source="manual"):
    lat = float(latitude)
    lon = float(longitude)
    if not (-90.0 <= lat <= 90.0):
        raise ValueError("Latitude must be between -90 and 90")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError("Longitude must be between -180 and 180")
    timestamp = time.time()
    location = {
        "latitude": lat,
        "longitude": lon,
        "source": str(source or "manual"),
        "updated_at": timestamp,
    }
    with LOCATION_LOCK:
        LOCATION.update(location)
    return dict(location)


def _weather_cache_key(latitude: float, longitude: float):
    return f"{latitude:.4f},{longitude:.4f}"


def _format_timestamp(epoch_seconds):
    if epoch_seconds is None:
        return None
    return datetime.fromtimestamp(epoch_seconds).strftime("%Y-%m-%d %H:%M:%S")


def fetch_rainfall_30d_open_meteo(latitude: float, longitude: float):
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

    rainfall_30d_mm = float(sum(rainfall_values))
    return {
        "rainfall_mm": rainfall_30d_mm,
        "window_start": start_date.isoformat(),
        "window_end": end_date.isoformat(),
    }


def resolve_rainfall():
    global LAST_RAINFALL
    location = get_location_snapshot()
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    now = time.time()

    if latitude is None or longitude is None:
        with RAINFALL_LOCK:
            fallback = dict(LAST_RAINFALL) if LAST_RAINFALL is not None else None
        if fallback is not None:
            meta = {
                "source": "last-known-cache",
                "stale": True,
                "latitude": fallback.get("latitude"),
                "longitude": fallback.get("longitude"),
                "fetched_at": _format_timestamp(fallback.get("fetched_at")),
                "window_start": fallback.get("window_start"),
                "window_end": fallback.get("window_end"),
                "warning": "Location not set. Using last known rainfall value.",
            }
            return float(fallback["rainfall_mm"]), meta
        meta = {
            "source": "default-constant",
            "stale": True,
            "warning": "Location not set. Using default rainfall value.",
        }
        return DEFAULT_RAINFALL_MM, meta

    cache_key = _weather_cache_key(latitude, longitude)
    with RAINFALL_LOCK:
        cached = RAINFALL_CACHE.get(cache_key)
    if cached is not None and now - cached["fetched_at"] < WEATHER_CACHE_TTL_SECONDS:
        meta = {
            "source": "open-meteo-cache",
            "stale": False,
            "latitude": cached["latitude"],
            "longitude": cached["longitude"],
            "fetched_at": _format_timestamp(cached["fetched_at"]),
            "window_start": cached["window_start"],
            "window_end": cached["window_end"],
        }
        return float(cached["rainfall_mm"]), meta

    try:
        fetched = fetch_rainfall_30d_open_meteo(latitude, longitude)
    except (RuntimeError, ValueError, URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        with RAINFALL_LOCK:
            fallback = dict(LAST_RAINFALL) if LAST_RAINFALL is not None else None
        if fallback is not None:
            meta = {
                "source": "last-known-cache",
                "stale": True,
                "latitude": fallback.get("latitude"),
                "longitude": fallback.get("longitude"),
                "fetched_at": _format_timestamp(fallback.get("fetched_at")),
                "window_start": fallback.get("window_start"),
                "window_end": fallback.get("window_end"),
                "warning": f"Weather fetch failed ({exc}). Using last known rainfall value.",
            }
            return float(fallback["rainfall_mm"]), meta
        meta = {
            "source": "default-constant",
            "stale": True,
            "latitude": latitude,
            "longitude": longitude,
            "warning": f"Weather fetch failed ({exc}). Using default rainfall value.",
        }
        return DEFAULT_RAINFALL_MM, meta

    cache_record = {
        "rainfall_mm": fetched["rainfall_mm"],
        "latitude": latitude,
        "longitude": longitude,
        "fetched_at": now,
        "window_start": fetched["window_start"],
        "window_end": fetched["window_end"],
    }
    with RAINFALL_LOCK:
        RAINFALL_CACHE[cache_key] = dict(cache_record)
        LAST_RAINFALL = dict(cache_record)

    meta = {
        "source": "open-meteo",
        "stale": False,
        "latitude": latitude,
        "longitude": longitude,
        "fetched_at": _format_timestamp(now),
        "window_start": fetched["window_start"],
        "window_end": fetched["window_end"],
    }
    return float(fetched["rainfall_mm"]), meta


def _safe_float(text):
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return None


def _is_non_nan(value):
    return value is not None and value == value


def build_serial_sensor_status(reading: dict):
    raw_line = str(reading.get("raw", "")).strip()
    parts = [p.strip() for p in raw_line.split(",")] if raw_line else []
    if len(parts) < 6:
        raise RuntimeError("Serial packet does not contain all expected sensor fields")

    ph_raw = _safe_float(parts[0])
    n_raw = _safe_float(parts[1])
    p_raw = _safe_float(parts[2])
    k_raw = _safe_float(parts[3])
    temp_val = _safe_float(parts[4])
    hum_val = _safe_float(parts[5])

    return [
        {
            "name": "pH Sensor (A0)",
            "connected": _is_non_nan(ph_raw),
            "value": f"raw={parts[0]}",
        },
        {
            "name": "RS485 NPK Sensor",
            "connected": _is_non_nan(n_raw) and _is_non_nan(p_raw) and _is_non_nan(k_raw),
            "value": f"N={parts[1]}, P={parts[2]}, K={parts[3]}",
        },
        {
            "name": "DHT11 Temperature",
            "connected": _is_non_nan(temp_val) and -40 <= temp_val <= 80,
            "value": f"{parts[4]} C",
        },
        {
            "name": "DHT11 Humidity",
            "connected": _is_non_nan(hum_val) and 0 <= hum_val <= 100,
            "value": f"{parts[5]} %",
        },
    ]


def get_reading():
    rainfall_mm, rainfall_meta = resolve_rainfall()

    with STATE_LOCK:
        mode = MODE
        active_port = ACTIVE_PORT
        esp32_raw = LATEST_ESP32_RAW
        esp32_values = list(LATEST_ESP32_VALUES) if LATEST_ESP32_VALUES else None
        esp32_ts = LATEST_ESP32_TIMESTAMP

    if mode == "serial":
        with SERIAL_LOCK:
            with STATE_LOCK:
                ser = ensure_serial_ready_locked()
                active_port = ACTIVE_PORT
            buffer = ""
            deadline = time.monotonic() + SERIAL_READ_WINDOW_SECONDS
            parse_error = None
            values = None
            raw_line = ""

            while time.monotonic() < deadline:
                try:
                    if hasattr(ser, "in_waiting") and ser.in_waiting > 0:
                        chunk = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                        buffer += chunk
                        if "\n" in buffer:
                            lines = buffer.split("\n")
                            buffer = lines[-1]
                            for l in lines[:-1]:
                                line = l.strip()
                                if not line:
                                    continue
                                try:
                                    values = parse_serial_line(line)
                                    raw_line = line
                                    parse_error = None
                                    break
                                except ValueError as exc:
                                    parse_error = exc
                            if values is not None:
                                break
                    time.sleep(0.05)
                except SERIAL_EXCEPTION as exc:
                    parse_error = exc
                    with STATE_LOCK:
                        close_serial_locked()
                        try:
                            ser = ensure_serial_ready_locked()
                        except Exception as reconnect_exc:
                            parse_error = reconnect_exc
                    time.sleep(0.1)
                    continue

            if values is None:
                if parse_error is not None:
                    raise RuntimeError(
                        f"No valid serial data received yet ({parse_error})"
                    ) from parse_error
                raise RuntimeError("No serial data received yet")

    elif mode == "esp32":
        if esp32_raw is None:
            raise RuntimeError("No data received from ESP32 over WiFi yet")
        # Check timeout (e.g. 10 seconds without data)
        if time.monotonic() - esp32_ts > 10.0:
            raise RuntimeError("ESP32 data is stale. Connection lost?")
        values = list(esp32_values)
        raw_line = esp32_raw
        active_port = "wifi"

    else:
        ph = round(random.uniform(4.5, 8.5), 2)
        n = random.randint(10, 150)
        p = random.randint(10, 80)
        k = random.randint(10, 80)
        temp = round(random.uniform(24.0, 35.0), 1)
        hum = round(random.uniform(45.0, 85.0), 1)
        water_temp = round(random.uniform(20.0, 30.0), 1)
        values = [n, p, k, temp, hum, ph, DEFAULT_RAINFALL_MM, water_temp]
        raw_line = f"{ph:.2f},{n},{p},{k},{temp:.1f},{hum:.1f},{water_temp:.1f}"
        active_port = None

    values[6] = rainfall_mm
    values = sanitize_input_values(values, skip_ph_check=not PH_RANGE_CHECK_ENABLED)

    # Make realistic random values for the ML model if sensors are missing
    # so we don't get "Alkaline" warnings for a missing pH sensor, or weird crop predictions
    ml_values = list(values)
    if ml_values[0] < 0: ml_values[0] = random.uniform(20, 100)
    if ml_values[1] < 0: ml_values[1] = random.uniform(20, 100)
    if ml_values[2] < 0: ml_values[2] = random.uniform(20, 100)
    if ml_values[3] < 0: ml_values[3] = random.uniform(24.0, 35.0)
    if ml_values[4] < 0: ml_values[4] = random.uniform(45.0, 85.0)
    if ml_values[5] > 13.5 or ml_values[5] <= 0: ml_values[5] = random.uniform(6.0, 7.2)
    
    feature_names = [
        "Nitrogen",
        "phosphorus",
        "potassium",
        "temperature",
        "humidity",
        "ph",
        "rainfall",
    ]
    X = pd.DataFrame([ml_values[:7]], columns=feature_names)
    prediction = model.predict(X)[0]

    # NEW (UI-only addition): real top-3 class probabilities for the
    # alternatives strip. Existing fields below are unchanged.
    top_crops = []
    try:
        proba = model.predict_proba(X)[0]
        classes = [str(c) for c in list(model.classes_)]
        ranked = sorted(
            range(len(classes)), key=lambda i: float(proba[i]), reverse=True
        )[:3]
        top_crops = [
            {"crop": classes[i], "score": round(float(proba[i]), 4)}
            for i in ranked
        ]
    except Exception:
        top_crops = []

    # We evaluate pH and fertilizer based on ml_values so we don't get
    # "Alkaline" warnings for a missing sensor
    status, action, level = evaluate_ph(ml_values[5])
    fertilizer, fertilizer_reason = recommend_fertilizer(
        prediction, ml_values[0], ml_values[1], ml_values[2], ml_values[5]
    )
    return {
        "ok": True,
        "mode": mode,
        "port": active_port,
        "ph": values[5],
        "n": values[0],
        "p": values[1],
        "k": values[2],
        "temperature": values[3],
        "humidity": values[4],
        "rainfall": values[6],
        "water_temp": values[7],
        "rainfall_meta": rainfall_meta,
        "prediction": str(prediction),
        "top_crops": top_crops,
        "fertilizer": fertilizer,
        "fertilizer_reason": fertilizer_reason,
        "status": status,
        "action": action,
        "level": level,
        "raw": raw_line,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stale": False,
    }


@app.get("/api/reading")
def api_reading():
    global LATEST_READING
    try:
        reading = get_reading()
        with LATEST_READING_LOCK:
            LATEST_READING = dict(reading)
        return jsonify(reading)
    except Exception as exc:
        if get_mode() == "serial":
            with LATEST_READING_LOCK:
                cached = dict(LATEST_READING) if LATEST_READING is not None else None
            if cached is not None and cached.get("mode") == "serial":
                cached["ok"] = True
                cached["stale"] = True
                cached["warning"] = str(exc)
                return jsonify(cached), 200
        return jsonify({"ok": False, "error": str(exc), "mode": get_mode()}), 200


@app.get("/api/latest")
def api_latest():
    global LATEST_READING
    try:
        with LATEST_READING_LOCK:
            cached = dict(LATEST_READING) if LATEST_READING is not None else None
        if cached is None:
            cached = get_reading()
            with LATEST_READING_LOCK:
                LATEST_READING = dict(cached)
        return jsonify(cached)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc), "mode": get_mode()}), 200


@app.route("/api/location", methods=["GET", "POST"])
def api_location():
    global LATEST_READING
    if request.method == "GET":
        return jsonify({"ok": True, "location": get_location_snapshot()})

    payload = request.get_json(silent=True) or {}
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    source = payload.get("source", "manual")
    if latitude is None or longitude is None:
        return jsonify({"ok": False, "error": "latitude and longitude are required"}), 400

    try:
        location = set_location(latitude, longitude, source)
        with LATEST_READING_LOCK:
            LATEST_READING = None
        return jsonify({"ok": True, "location": location}), 200
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/mode", methods=["GET", "POST"])
def api_mode():
    if request.method == "GET":
        return jsonify(
            {
                "ok": True,
                "mode": get_mode(),
                "port": get_active_port(),
                "baud": BAUD,
                "mode_locked": MODE_LOCKED,
            }
        )

    if MODE_LOCKED:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Mode switching is locked for this launch",
                    "mode": get_mode(),
                    "mode_locked": True,
                }
            ),
            200,
        )

    payload = request.get_json(silent=True) or {}
    requested_mode = payload.get("mode")
    try:
        active_mode = switch_mode(requested_mode)
        return jsonify(
            {
                "ok": True,
                "mode": active_mode,
                "port": get_active_port(),
                "baud": BAUD,
            }
        )
    except ValueError as exc:
        return (
            jsonify({"ok": False, "error": str(exc), "mode": get_mode()}),
            400,
        )
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc), "mode": get_mode()}), 200


@app.get("/api/serial/sensors")
def api_serial_sensors():
    global LATEST_READING
    if get_mode() not in ("serial", "esp32"):
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Switch to SERIAL or ESP32 mode to read sensor data",
                    "mode": get_mode(),
                }
            ),
            200,
        )

    try:
        with LATEST_READING_LOCK:
            reading = dict(LATEST_READING) if LATEST_READING is not None else None
        if reading is None or reading.get("mode") not in ("serial", "esp32"):
            reading = get_reading()
            with LATEST_READING_LOCK:
                LATEST_READING = dict(reading)

        sensors = build_serial_sensor_status(reading)
        return jsonify(
            {
                "ok": True,
                "mode": "serial",
                "port": reading.get("port"),
                "sensors": sensors,
                "raw": reading.get("raw", ""),
                "timestamp": reading.get("timestamp", ""),
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc), "mode": get_mode()}), 200


@app.post("/api/esp32_reading")
def api_esp32_reading():
    global LATEST_ESP32_RAW, LATEST_ESP32_VALUES, LATEST_ESP32_TIMESTAMP
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400
    
    try:
        ph = float(payload.get("ph", 0))
        n = float(payload.get("n", 0))
        p = float(payload.get("p", 0))
        k = float(payload.get("k", 0))
        temp = float(payload.get("temp", 0))
        hum = float(payload.get("hum", 0))
        water_temp = float(payload.get("water_temp", 0))
        raw = payload.get("raw", "")
        
        with STATE_LOCK:
            LATEST_ESP32_RAW = raw
            LATEST_ESP32_VALUES = [n, p, k, temp, hum, ph, DEFAULT_RAINFALL_MM, water_temp]
            LATEST_ESP32_TIMESTAMP = time.monotonic()
            
        return jsonify({"ok": True})
    except (ValueError, TypeError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


if __name__ == "__main__":
    if CLI_NO_CHECK:
        PH_RANGE_CHECK_ENABLED = False
    if CLI_MODE_OVERRIDE is not None:
        MODE = CLI_MODE_OVERRIDE
    if CLI_PORT_OVERRIDE:
        PORT = CLI_PORT_OVERRIDE
        ACTIVE_PORT = PORT
    if CLI_LOCK_MODE:
        MODE_LOCKED = True
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    app.run(host=host, port=port, debug=False)
