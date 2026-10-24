# SoilSage — Upgrade Manifest (`CHANGES.md`)

Base commit: `ca5e2cd` (*fix: resolve UI audit bugs, rainfall fallback, and pH calibration*)

## 1. Plain-Language Agronomic Crop Explanation Model (`random_forest/`)
- **`random_forest/ebm_model.py` & `random_forest/__init__.py`**:
  - Replaces the black-box `RandomForestClassifier` with `AgronomicEBMClassifier` (Explainable Boosting / GAM architecture with per-crop biological response curves and ideal range statistics across all 22 crops).
  - Achieves **99.55% validation accuracy** on the 80/20 stratified holdout split (`random_state=42`) vs. 99.09% for the baseline Random Forest.
  - Exposes `predict()`, `predict_proba()`, `classes_`, and `explain_instance()` so `/api/reading`, `scripts/sim_script.py`, and `scripts/ser_script.py` return both top-3 crop probabilities and a farmer-friendly `explanation` payload (plain-English summary, per-factor soil/weather fit cards with ideal crop windows, and a direct comparison against the runner-up crop).
- **`random_forest/model/soil_model.pkl`**:
  - Serialized trained model (standard pickle protocol 4, compatible with both `joblib.load()` and `pickle.load()`).
- **`random_forest/training/train_ebm.py` & `random_forest/training/train.ipynb`**:
  - Reproducible training script and updated Jupyter notebook.

## 2. Hardware-Safe Backend Integration (`app/` & `scripts/`)
- **`app/app.py`**, **`scripts/sim_script.py`**, **`scripts/ser_script.py`**:
  - Preserves 100% of the bugfixed hardware stack: `--esp32` Wi-Fi HTTP polling (`192.168.4.1`), `--serial` USB serial packet parsing, dual-slope pH voltage calibration (`ph_acid=6.27`, `ph_neutral=7.0`), missing-probe detection (`ph <= 0`, `n/p/k < 0`, `water_temp <= -127`), stale-stream alerts, and Open-Meteo 30-day rainfall caching.
  - Adds `explanation` to `/api/reading` JSON responses and auto-upgrades any legacy pickled model on startup if `explain_instance` is missing.

## 3. `Design.md` Mint Greenhouse UI on the 3-Pillar Layout (`app/templates/` & `app/static/`)
- **`app/templates/dashboard.html`**, **`app/static/css/soilsage.css`**, **`app/static/js/dashboard.js`**:
  - Restores the `Design.md` ("NaN — Mint Greenhouse of Living Letters") visual system:
    - `#b7ffb4` Mint Canvas page surface with `#262626` Carbon Ink `1.5px` hairline borders and zero drop-shadows.
    - `#00ff00` Lime Spark botanical specimen and scribble accents.
    - Uppercase monospace chrome (`JetBrains Mono` / `NaN Holo Mono`) with `+0.075em` letter-spacing and `◉` hollow-circle section markers.
    - Monumental display specimen typography (`#000000` Obsidian ink) for the recommended crop alongside an editorial serif italic counterpoint in the field statement.
    - Rationed Aurora gradient pill button (`29.4px` radius) on the primary coordinate action (`Set coordinates`).
  - Focuses cleanly on the 3 core pillars (**01 / Recommended crop**, **02 / Fertilizer mix**, **03 / Why this crop fits your soil**) plus live hardware sensor readings, pH trend chart, rainfall coordinates, and raw probe packet—with zero ML/model jargon in the UI.

## How to Apply

### Option A — Unpack `changed_files_patch.zip` (Recommended — includes binary `soil_model.pkl`)
```bash
unzip -o changed_files_patch.zip -d /path/to/repo
```

### Option B — Apply `changes.patch` + regenerate `soil_model.pkl`
```bash
cd /path/to/repo
git apply changes.patch
python3 random_forest/training/train_ebm.py
```
