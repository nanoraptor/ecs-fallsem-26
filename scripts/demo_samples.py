#!/usr/bin/env python3
"""
SoilSage - 3-Soil Sample Demonstration & Evaluation Tool
========================================================
Interactive script to evaluate, record, and compare 3 soil samples.

Usage:
  python3 scripts/demo_samples.py --simulate   # Run with 3 archetypal demo soil profiles
  python3 scripts/demo_samples.py --serial     # Read live from connected ESP32 sensor
  python3 scripts/demo_samples.py --manual     # Manually enter sensor readings for each sample
"""

import sys
import os
import time
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import joblib
import pandas as pd

import re
from app.app import (
    resolve_soil_model_path,
    evaluate_ph,
    recommend_fertilizer,
    parse_serial_line,
    sanitize_input_values,
)

RATE_TABLE = [
    (re.compile(r"urea", re.I), "Urea ≈55 kg/ha"),
    (re.compile(r"dap", re.I), "DAP ≈60 kg/ha"),
    (re.compile(r"mop", re.I), "MOP ≈40 kg/ha"),
    (re.compile(r"ssp", re.I), "SSP ≈80 kg/ha"),
    (re.compile(r"npk", re.I), "NPK blend ≈100 kg/ha"),
    (re.compile(r"lime", re.I), "Lime ≈400 kg/ha"),
    (re.compile(r"compost|organic|mulch", re.I), "Compost ≈2 t/ha"),
]

# Terminal Styling
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

FEATURE_NAMES = ["Nitrogen", "phosphorus", "potassium", "temperature", "humidity", "ph", "rainfall"]

# Archetypal sample presets for simulated/rehearsal mode
SAMPLE_PRESETS = {
    1: {
        "name": "Sample 1: Alluvial Clay Loam (High Nitrogen)",
        "desc": "Moist, fertile lowland soil with abundant organic nitrogen & neutral pH.",
        "values": [90.0, 42.0, 43.0, 26.5, 82.0, 6.50, 180.0, 25.0],
    },
    2: {
        "name": "Sample 2: Upland Sandy Loam (Low Nitrogen / Legume Fit)",
        "desc": "Dry or semi-arid sandy loam depleted in nitrogen, ideal for nitrogen-fixing legumes.",
        "values": [22.0, 60.0, 20.0, 31.0, 55.0, 6.80, 75.0, 29.0],
    },
    3: {
        "name": "Sample 3: Acidic Red / Laterite Soil (High Potassium)",
        "desc": "Weathered acidic soil (pH 5.2) requiring CaCO3 lime and specialized crop match.",
        "values": [40.0, 65.0, 145.0, 28.0, 70.0, 5.20, 110.0, 27.0],
    },
}


def load_model():
    model_path = resolve_soil_model_path()
    try:
        model = joblib.load(model_path)
        return model
    except Exception as exc:
        print(f"{RED}Error loading ML model from {model_path}: {exc}{RESET}")
        sys.exit(1)


def analyze_sample(model, values, sample_name="Soil Sample"):
    """
    Evaluates an 8-item sensor list [N, P, K, temp, hum, ph, rainfall, water_temp].
    Returns a structured analysis dictionary.
    """
    n, p, k, temp, hum, ph_val, rainfall, water_temp = values[:8]

    # Check uninserted / zero sample
    if n == 0 and p == 0 and k == 0:
        return {
            "name": sample_name,
            "values": values,
            "is_zero": True,
            "is_disc": False,
            "crop": "Please insert soil sample",
            "score": 0.0,
            "top_crops": [],
            "ph_status": "Awaiting soil contact",
            "ph_action": "Insert probes firmly into moist soil sample.",
            "fert_mix": "Awaiting soil sample",
            "fert_reason": "Nutrient calculation requires live soil readings.",
            "rates": [],
            "summary": "Probes reading 0 mg/kg across all nutrients. Ensure soil is moist and firmly packed.",
        }

    # Check disconnected
    if n < 0 and p < 0 and k < 0:
        return {
            "name": sample_name,
            "values": values,
            "is_zero": False,
            "is_disc": True,
            "crop": "NPK Sensor Disconnected",
            "score": 0.0,
            "top_crops": [],
            "ph_status": "Sensor offline",
            "ph_action": "Check MAX485 wiring (RO->RX2, DI->TX2, DE/RE->D4) and 12V DC power.",
            "fert_mix": "Sensor disconnected",
            "fert_reason": "No RS485 communication.",
            "rates": [],
            "summary": "RS485 sensor did not respond.",
        }

    # Model inference
    X = pd.DataFrame([[n, p, k, temp, hum, ph_val, rainfall]], columns=FEATURE_NAMES)
    prediction = model.predict(X)[0]

    top_crops = []
    top_score = 0.99
    try:
        proba = model.predict_proba(X)[0]
        classes = [str(c) for c in list(model.classes_)]
        ranked = sorted(range(len(classes)), key=lambda i: float(proba[i]), reverse=True)[:4]
        top_crops = [{"crop": classes[i], "score": float(proba[i])} for i in ranked]
        top_score = float(proba[ranked[0]])
    except Exception:
        top_crops = [{"crop": prediction, "score": 0.95}]

    # Explanations
    summary = ""
    try:
        if hasattr(model, "explain_reading"):
            exp = model.explain_reading([n, p, k, temp, hum, ph_val, rainfall])
            summary = exp.get("summary", "")
    except Exception:
        summary = f"Agronomic conditions match requirements for {prediction}."

    # Chemistry & Fertilizer
    ph_status, ph_action, _ = evaluate_ph(ph_val)
    fert_mix, fert_reason = recommend_fertilizer(prediction, n, p, k, ph_val)

    # Rates
    rates = []
    for pattern, rate_text in RATE_TABLE:
        if pattern.search(fert_mix):
            rates.append(rate_text)

    return {
        "name": sample_name,
        "values": values,
        "is_zero": False,
        "is_disc": False,
        "crop": str(prediction).capitalize(),
        "score": top_score,
        "top_crops": top_crops,
        "ph_status": ph_status,
        "ph_action": ph_action,
        "fert_mix": fert_mix,
        "fert_reason": fert_reason,
        "rates": rates,
        "summary": summary,
    }


def print_single_report(res):
    n, p, k, temp, hum, ph_val, rainfall, water_temp = res["values"][:8]

    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║  SOILSAGE FIELD REPORT : {res['name']:<52}║{RESET}")
    print(f"{BOLD}{CYAN}╠══════════════════════════════════════════════════════════════════════════════╣{RESET}")
    
    # Sensor telemetry row
    print(f"║ {BOLD}Telemetry:{RESET} pH: {BOLD}{ph_val:.2f}{RESET} │ N: {BOLD}{n:.0f}{RESET} mg/kg │ P: {BOLD}{p:.0f}{RESET} mg/kg │ K: {BOLD}{k:.0f}{RESET} mg/kg │ T: {temp:.1f}°C │ H: {hum:.1f}% ║")
    print(f"{BOLD}{CYAN}╟──────────────────────────────────────────────────────────────────────────────╢{RESET}")

    if res["is_zero"]:
        print(f"║ {YELLOW}◉ STATUS: NO SOIL SAMPLE DETECTED (Sensor in air or probes dry){RESET}             ║")
        print(f"║   Action : Insert probes firmly into a moist soil sample.                    ║")
        print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════════════════════════════╝{RESET}\n")
        return

    if res["is_disc"]:
        print(f"║ {RED}◉ STATUS: NPK SENSOR DISCONNECTED{RESET}                                            ║")
        print(f"║   Action : Check MAX485 wiring & 12V DC external power.                      ║")
        print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════════════════════════════╝{RESET}\n")
        return

    # Recommended Crop
    display_pct = (res["score"] * 100)
    display_pct_str = "99.9" if display_pct >= 99.95 else f"{display_pct:.1f}"
    print(f"║ {BOLD}AI Recommended Crop:{RESET} {GREEN}{BOLD}{res['crop']:<20}{RESET} {DIM}(Match: {display_pct_str}%){RESET}                          ║")

    # Runner-ups
    if len(res["top_crops"]) > 1:
        alts = []
        for alt in res["top_crops"][1:]:
            s_pct = alt["score"] * 100
            if s_pct >= 0.1:
                alts.append(f"{alt['crop'].capitalize()} ({s_pct:.1f}%)")
        if alts:
            print(f"║ {DIM}Runner-ups:{RESET} {', '.join(alts):<63} ║")

    print(f"{BOLD}{CYAN}╟──────────────────────────────────────────────────────────────────────────────╢{RESET}")
    print(f"║ {BOLD}Soil Chemistry & pH Action:{RESET}                                                   ║")
    print(f"║   Status : {res['ph_status']:<64} ║")
    print(f"║   Action : {res['ph_action']:<64} ║")
    print(f"{BOLD}{CYAN}╟──────────────────────────────────────────────────────────────────────────────╢{RESET}")
    print(f"║ {BOLD}Targeted Fertilizer Amendment Plan:{RESET}                                           ║")
    print(f"║   Mix    : {res['fert_mix']:<64} ║")
    if res["rates"]:
        rates_str = " │ ".join(res["rates"])
        print(f"║   Dosage : {rates_str:<64} ║")
    print(f"{BOLD}{CYAN}╟──────────────────────────────────────────────────────────────────────────────╢{RESET}")
    print(f"║ {BOLD}Agronomic Explanation:{RESET}                                                         ║")
    
    # Word wrap summary
    import textwrap
    wrapped = textwrap.wrap(res["summary"], width=74)
    for line in wrapped:
        print(f"║   {line:<74} ║")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════════════════════════════╝{RESET}\n")


def print_comparison_matrix(history):
    """Prints a clean side-by-side comparison table of all captured samples."""
    print(f"\n{BOLD}{MAGENTA}╔══════════════════════════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{MAGENTA}║                     SOILSAGE 3-SAMPLE COMPARATIVE AGRONOMIC MATRIX                       ║{RESET}")
    print(f"{BOLD}{MAGENTA}╠════════════════════════════╦═════════════════════╦═════════════════════╦═════════════════════╣{RESET}")
    print(f"║ {BOLD}Parameter{RESET}                  ║ {BOLD}Sample 1{RESET}            ║ {BOLD}Sample 2{RESET}            ║ {BOLD}Sample 3{RESET}            ║")
    print(f"{BOLD}{MAGENTA}╠════════════════════════════╬═════════════════════╬═════════════════════╬═════════════════════╣{RESET}")

    def get_val(sample_idx, key, default="—"):
        item = history.get(sample_idx)
        if not item: return default
        return str(item.get(key, default))

    # Row helper
    def fmt_row(label, val1, val2, val3):
        return f"║ {label:<26} ║ {val1:<19} ║ {val2:<19} ║ {val3:<19} ║"

    # Readings
    def fmt_meas(sample_idx, pos, unit=""):
        item = history.get(sample_idx)
        if not item or item.get("is_zero") or item.get("is_disc"): return "—"
        v = item["values"][pos]
        return f"{v:.1f}{unit}" if isinstance(v, float) else f"{v}{unit}"

    print(fmt_row("Soil pH", fmt_meas(1, 5), fmt_meas(2, 5), fmt_meas(3, 5)))
    print(fmt_row("Nitrogen (N)", fmt_meas(1, 0, " mg/kg"), fmt_meas(2, 0, " mg/kg"), fmt_meas(3, 0, " mg/kg")))
    print(fmt_row("Phosphorus (P)", fmt_meas(1, 1, " mg/kg"), fmt_meas(2, 1, " mg/kg"), fmt_meas(3, 1, " mg/kg")))
    print(fmt_row("Potassium (K)", fmt_meas(1, 2, " mg/kg"), fmt_meas(2, 2, " mg/kg"), fmt_meas(3, 2, " mg/kg")))
    print(fmt_row("Temperature", fmt_meas(1, 3, "°C"), fmt_meas(2, 3, "°C"), fmt_meas(3, 3, "°C")))
    print(f"{BOLD}{MAGENTA}╟────────────────────────────╫─────────────────────╫─────────────────────╫─────────────────────╢{RESET}")
    print(fmt_row("Recommended Crop", get_val(1, "crop"), get_val(2, "crop"), get_val(3, "crop")))
    
    # Confidence
    def fmt_score(idx):
        item = history.get(idx)
        if not item or item.get("is_zero") or item.get("is_disc"): return "—"
        pct = item["score"] * 100
        return "99.9%" if pct >= 99.95 else f"{pct:.1f}%"

    print(fmt_row("AI Match Score", fmt_score(1), fmt_score(2), fmt_score(3)))
    print(f"{BOLD}{MAGENTA}╟────────────────────────────╫─────────────────────╫─────────────────────╫─────────────────────╢{RESET}")
    print(fmt_row("pH Remedy", 
                  "Balanced" if "neutral" in get_val(1, "ph_status").lower() or "maintained" in get_val(1, "ph_status").lower() else ("Lime (CaCO3)" if "acid" in get_val(1, "ph_status").lower() else "Organic Mulch"),
                  "Balanced" if "neutral" in get_val(2, "ph_status").lower() or "maintained" in get_val(2, "ph_status").lower() else ("Lime (CaCO3)" if "acid" in get_val(2, "ph_status").lower() else "Organic Mulch"),
                  "Balanced" if "neutral" in get_val(3, "ph_status").lower() or "maintained" in get_val(3, "ph_status").lower() else ("Lime (CaCO3)" if "acid" in get_val(3, "ph_status").lower() else "Organic Mulch")))
    
    # Primary Fertilizer
    def fmt_fert(idx):
        item = history.get(idx)
        if not item: return "—"
        m = item.get("fert_mix", "—")
        return m.split("+")[0].strip()[:19]

    print(fmt_row("Primary Fertilizer", fmt_fert(1), fmt_fert(2), fmt_fert(3)))
    print(f"{BOLD}{MAGENTA}╚════════════════════════════╩═════════════════════╩═════════════════════╩═════════════════════╝{RESET}\n")


def capture_serial_sample(port="/dev/ttyUSB0", baud=115200, timeout=5.0):
    """Reads live reading from serial port for sample evaluation."""
    import serial
    print(f"{CYAN}Connecting to ESP32 on {port} at {baud} baud...{RESET}")
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=1.0)
    except Exception as exc:
        print(f"{RED}Failed to open serial port {port}: {exc}{RESET}")
        print(f"{YELLOW}Hint: If Arduino IDE is open, close its Serial Monitor first.{RESET}")
        return None

    time.sleep(1.5)
    ser.reset_input_buffer()
    deadline = time.monotonic() + timeout
    print(f"{CYAN}Listening for live sensor frame (dip probes into soil now)...{RESET}")

    values = None
    while time.monotonic() < deadline:
        line = ser.readline().decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            raw_vals = parse_serial_line(line, default_rainfall=100.0)
            values = sanitize_input_values(raw_vals)
            break
        except Exception:
            continue

    ser.close()
    if values is None:
        print(f"{RED}Timed out waiting for valid serial frame from ESP32.{RESET}")
        return None
    return values


def main():
    parser = argparse.ArgumentParser(description="SoilSage 3-Sample Demo Tool")
    parser.add_argument("--simulate", action="store_true", help="Run with 3 preset agronomic soil samples")
    parser.add_argument("--serial", action="store_true", help="Capture live readings from ESP32 over serial")
    parser.add_argument("--manual", action="store_true", help="Manually enter sensor readings for each sample")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port (default: /dev/ttyUSB0)")
    args = parser.parse_args()

    model = load_model()
    history = {}

    # If simulate flag passed, automatically evaluate all 3 and show comparison
    if args.simulate:
        print(f"\n{BOLD}{GREEN}=== SOILSAGE DEMO: 3 ARTIFACT SOIL SAMPLES (SIMULATION MODE) ==={RESET}")
        for idx in (1, 2, 3):
            preset = SAMPLE_PRESETS[idx]
            res = analyze_sample(model, preset["values"], preset["name"])
            history[idx] = res
            print_single_report(res)
            time.sleep(0.5)

        print_comparison_matrix(history)
        return

    # Interactive loop
    while True:
        print(f"\n{BOLD}══════════════════════════════════════════════════════{RESET}")
        print(f"{BOLD}       SOILSAGE 3-SOIL SAMPLE DEMO CONSOLE             {RESET}")
        print(f"{BOLD}══════════════════════════════════════════════════════{RESET}")
        print(f" [1] Capture / Test {BOLD}Soil Sample 1{RESET} {'(Recorded: ' + history[1]['crop'] + ')' if 1 in history else ''}")
        print(f" [2] Capture / Test {BOLD}Soil Sample 2{RESET} {'(Recorded: ' + history[2]['crop'] + ')' if 2 in history else ''}")
        print(f" [3] Capture / Test {BOLD}Soil Sample 3{RESET} {'(Recorded: ' + history[3]['crop'] + ')' if 3 in history else ''}")
        print(f" [0] Test {BOLD}Baseline (Sensor in Air / Dry){RESET}")
        print(f" [C] Show {BOLD}{MAGENTA}Side-by-Side Comparison Matrix{RESET}")
        print(f" [P] Load {BOLD}Archetypal Presets (Paddy, Legume, Fruit){RESET}")
        print(f" [Q] Quit")
        print(f"──────────────────────────────────────────────────────")

        choice = input(f"{BOLD}Select an option [1/2/3/0/C/P/Q]: {RESET}").strip().upper()

        if choice in ("1", "2", "3"):
            idx = int(choice)
            s_name = f"Soil Sample {idx}"
            print(f"\n{CYAN}>>> Evaluating {s_name} <<<{RESET}")

            vals = None
            if args.manual:
                try:
                    ph_in = float(input("Enter pH (e.g. 6.5): ") or 6.5)
                    n_in = float(input("Enter Nitrogen N (mg/kg): ") or 40)
                    p_in = float(input("Enter Phosphorus P (mg/kg): ") or 40)
                    k_in = float(input("Enter Potassium K (mg/kg): ") or 40)
                    t_in = float(input("Enter Temperature (°C): ") or 26.0)
                    h_in = float(input("Enter Humidity (%): ") or 70.0)
                    vals = [n_in, p_in, k_in, t_in, h_in, ph_in, 100.0, 25.0]
                except ValueError:
                    print(f"{RED}Invalid numeric input.{RESET}")
                    continue
            elif args.serial:
                vals = capture_serial_sample(port=args.port)
                if vals is None:
                    print(f"{YELLOW}Falling back to preset for {s_name}...{RESET}")
                    vals = SAMPLE_PRESETS[idx]["values"]
            else:
                # Default prompt to choose source
                sub = input("Source: [L]ive Serial or [P]reset Archetype? (default P): ").strip().upper()
                if sub == "L":
                    vals = capture_serial_sample(port=args.port)
                    if vals is None:
                        continue
                else:
                    vals = SAMPLE_PRESETS[idx]["values"]

            res = analyze_sample(model, vals, s_name)
            history[idx] = res
            print_single_report(res)

        elif choice == "0":
            print(f"\n{CYAN}>>> Testing Baseline (Sensor in Air / Dry)... <<<{RESET}")
            res = analyze_sample(model, [0.0, 0.0, 0.0, 30.5, 70.0, 6.5, 100.0, 29.0], "Baseline (Sensor in Air)")
            print_single_report(res)

        elif choice == "C":
            if not history:
                print(f"{YELLOW}No samples recorded yet. Test Sample 1, 2, or 3 first!{RESET}")
            else:
                print_comparison_matrix(history)

        elif choice == "P":
            for idx in (1, 2, 3):
                preset = SAMPLE_PRESETS[idx]
                history[idx] = analyze_sample(model, preset["values"], preset["name"])
            print(f"{GREEN}Loaded archetypal presets for all 3 samples!{RESET}")
            print_comparison_matrix(history)

        elif choice == "Q":
            print("Exiting SoilSage Demo.")
            break


if __name__ == "__main__":
    main()
