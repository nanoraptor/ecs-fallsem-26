import joblib
import pandas as pd
import time
import random
import os
import sys
import argparse
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode
from datetime import date, timedelta
import json

# ANSI Colors for a cool terminal look
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

DEFAULT_RAINFALL_MM = 100.0
RAINFALL_WINDOW_DAYS = 30
WEATHER_HTTP_TIMEOUT_SECONDS = 8


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


# Load model
try:
    model = joblib.load(resolve_soil_model_path())
except FileNotFoundError as exc:
    print(f"{RED}Error: {exc}{RESET}")
    sys.exit(1)

parser = argparse.ArgumentParser(
    description="Run the simulation script with optional rainfall data."
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
        print(f"{YELLOW}Fetching rainfall data for location: {args.location}{RESET}")
        fetched_rainfall = fetch_rainfall_data(args.location[0], args.location[1])
        print(
            f"{GREEN}Successfully fetched rainfall data: {fetched_rainfall:.2f}mm{RESET}"
        )
        rainfall = fetched_rainfall
    except Exception as e:
        print(
            f"{RED}Warning: Failed to fetch rainfall data from location ({e}).{RESET}"
        )
        if args.rainfall_data is not None:
            print(
                f"{YELLOW}Falling back to rainfall_data flag: {args.rainfall_data}mm{RESET}"
            )
            rainfall = args.rainfall_data
        else:
            use_default_warning = True
elif args.rainfall_data is not None:
    rainfall = args.rainfall_data
else:
    use_default_warning = True

if use_default_warning:
    print(f"{RED}Using default rainfall value: {DEFAULT_RAINFALL_MM}mm{RESET}")

os.system("clear")
print(f"{BOLD}--- AI SUSTAINABILITY: SOIL CHEMISTRY MONITOR ---{RESET}")

try:
    while True:
        # Simulated values
        ph = round(random.uniform(4.5, 8.5), 2)
        n = random.randint(10, 150)
        p = random.randint(10, 80)
        k = random.randint(10, 80)
        temp = round(random.uniform(20.0, 35.0), 1)
        humidity = round(random.uniform(40.0, 80.0), 1)

        # Matching your CSV columns exactly
        cols = [
            "Nitrogen",
            "phosphorus",
            "potassium",
            "temperature",
            "humidity",
            "ph",
            "rainfall",
        ]
        data = pd.DataFrame(
            [[n, p, k, temp, humidity, ph, rainfall]], columns=cols
        )

        prediction = model.predict(data)[0]

        print(
            f"Sensors -> pH: {ph} | N: {n} | P: {p} | K: {k} | Temp: {temp}°C | Humidity: {humidity}% | Rainfall: {rainfall:.2f}mm"
        )
        print(f"AI Result -> {GREEN}{BOLD}{prediction.upper()}{RESET}")

        # Chemistry EVS Logic
        if ph < 5.5:
            print(f"{RED}STATUS: Acidic. Action: Apply CaCO3 (Neutralization).{RESET}")
        elif ph > 7.5:
            print(f"{YELLOW}STATUS: Alkaline. Action: Apply Organic Matter.{RESET}")
        else:
            print("STATUS: Chemical Equilibrium maintained.")

        print("-" * 40)
        time.sleep(2)
except KeyboardInterrupt:
    print("\nStopped by user.")
