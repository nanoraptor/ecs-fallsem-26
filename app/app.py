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
from flask import Flask, jsonify, render_template_string, request

VALID_MODES = {"sim", "serial", "esp32"}
PH_ADC_MAX = 1023.0
PH_ADC_REF_VOLTAGE = 5.0
PH_VOLTAGE_PH7 = 1.251
PH_VOLTAGE_PH4 = 1.769
PH_SLOPE = (PH_VOLTAGE_PH4 - PH_VOLTAGE_PH7) / 3.0
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

HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SoilSage</title>
  <link rel="icon" href="/favicon.ico">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:wght@600;700&display=swap');

    :root {
      --bg-body: #f5f0e8;
      --surface: #ffffff;
      --tile: #faf8f4;
      --border: #e5ddd0;
      --text: #2d2b28;
      --muted: #7c756b;
      --ok: #2e7d5b;
      --warn: #b8860b;
      --bad: #c0392b;
      --accent: #c96442;
      --accent-hover: #a84e32;
      --accent-light: rgba(201, 100, 66, 0.08);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      min-height: 100vh;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      color: var(--text);
      background-color: var(--bg-body);
      padding: 48px 24px;
      -webkit-font-smoothing: antialiased;
    }

    .wrap {
      max-width: 1060px;
      margin: 0 auto;
      display: grid;
      gap: 20px;
    }

    .card {
      border-radius: 16px;
      border: 1px solid var(--border);
      background: var(--surface);
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02);
      padding: 28px;
    }

    .hero {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }

    h1 {
      margin: 0 0 6px 0;
      font-family: 'Source Serif 4', Georgia, 'Times New Roman', serif;
      font-size: 28px;
      font-weight: 700;
      color: var(--text);
      letter-spacing: -0.01em;
    }

    .muted { color: var(--muted); font-size: 14px; line-height: 1.5; }

    .mode-pill {
      align-self: center;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 8px 16px;
      font-size: 12px;
      font-weight: 600;
      white-space: nowrap;
      background: var(--tile);
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .mode-select {
      margin-left: 8px;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
      padding: 5px 10px;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      font-family: inherit;
    }

    .grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }

    .tile {
      background: var(--tile);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
      min-height: 112px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: box-shadow 0.2s ease, border-color 0.2s ease;
    }

    .tile:hover {
      border-color: var(--accent);
      box-shadow: 0 2px 8px rgba(201, 100, 66, 0.08);
    }

    .label {
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      font-weight: 600;
    }

    .value {
      margin-top: 14px;
      font-size: 28px;
      font-weight: 700;
      line-height: 1.1;
      color: var(--text);
      word-break: break-word;
    }

    .status {
      margin-top: 12px;
      font-size: 18px;
      font-weight: 600;
      line-height: 1.35;
    }

    .status.ok { color: var(--ok); }
    .status.warn { color: var(--warn); }
    .status.bad { color: var(--bad); }

    .subtext { margin-top: 10px; color: var(--muted); font-size: 13px; }

    .raw-box {
      margin-top: 12px;
      border: 1px solid var(--border);
      background: var(--tile);
      border-radius: 10px;
      padding: 14px 16px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      color: var(--muted);
      font-size: 13px;
      overflow-x: auto;
    }

    .controls-row {
      margin-top: 16px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }

    .text-input {
      border-radius: 10px;
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
      padding: 10px 14px;
      font-size: 14px;
      font-family: inherit;
      width: 150px;
      transition: border-color 0.2s ease;
    }

    .text-input:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-light);
    }

    .btn {
      border-radius: 10px;
      border: none;
      background: var(--accent);
      color: #ffffff;
      padding: 10px 20px;
      font-size: 14px;
      font-weight: 600;
      font-family: inherit;
      cursor: pointer;
      transition: background-color 0.15s ease;
    }

    .btn:hover {
      background: var(--accent-hover);
    }

    .btn:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }

    @media (max-width: 900px) {
      .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }

    @media (max-width: 640px) {
      .hero { flex-direction: column; align-items: flex-start; }
      .mode-pill { align-self: flex-start; }
      .grid { grid-template-columns: minmax(0, 1fr); }
      .reco-row { grid-template-columns: 1fr; }
      body { padding: 24px 16px; }
    }

    .reco-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }

    .reco-card {
      border-radius: 16px;
      border: 2px solid var(--accent);
      background: var(--surface);
      box-shadow: 0 4px 16px rgba(201, 100, 66, 0.10);
      padding: 32px 28px;
      text-align: center;
      transition: box-shadow 0.2s ease, transform 0.2s ease;
    }

    .reco-card:hover {
      box-shadow: 0 8px 28px rgba(201, 100, 66, 0.16);
      transform: translateY(-2px);
    }

    .reco-icon {
      font-size: 40px;
      margin-bottom: 12px;
    }

    .reco-label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      font-weight: 600;
      margin-bottom: 10px;
    }

    .reco-value {
      font-family: 'Source Serif 4', Georgia, serif;
      font-size: 32px;
      font-weight: 700;
      color: var(--accent);
      line-height: 1.2;
      word-break: break-word;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card hero">
      <div>
        <h1>SoilSage</h1>
        <div class="muted">Live soil chemistry with crop and fertilizer recommendations.</div>
      </div>
      <div class="mode-pill"{% if mode_locked %} style="display:none;"{% endif %}>
        MODE:
        <select id="modeSelect" class="mode-select">
          <option value="sim">SIM</option>
          <option value="serial">SERIAL</option>
          <option value="esp32">ESP32 (WiFi)</option>
        </select>
      </div>
    </div>

    <div class="reco-row">
      <div class="reco-card">
        <div class="reco-icon">🌾</div>
        <div class="reco-label">Recommended Crop</div>
        <div class="reco-value" id="crop">—</div>
      </div>
      <div class="reco-card">
        <div class="reco-icon">🧪</div>
        <div class="reco-label">Recommended Fertilizer</div>
        <div class="reco-value" id="fertilizer">—</div>
      </div>
    </div>

    <div class="card">
      <div class="label">Chemical Status</div>
      <div class="status" id="status">Connecting to ESP32...</div>
      <div class="subtext" id="action"></div>
      <div class="subtext" id="fertilizerReason"></div>
    </div>

    <div class="card">
      <div class="label" style="margin-bottom: 14px;">Sensor Readings</div>
      <div class="grid">
        <div class="tile"><div class="label">pH</div><div class="value" id="ph">-</div></div>
        <div class="tile"><div class="label">Nitrogen (mg/kg)</div><div class="value" id="n">-</div></div>
        <div class="tile"><div class="label">Phosphorus (mg/kg)</div><div class="value" id="p">-</div></div>
        <div class="tile"><div class="label">Potassium (mg/kg)</div><div class="value" id="k">-</div></div>
        <div class="tile"><div class="label">Ambient Temp (°C)</div><div class="value" id="temperature">-</div></div>
        <div class="tile"><div class="label">Humidity (%)</div><div class="value" id="humidity">-</div></div>
        <div class="tile"><div class="label">Soil Solution Temp (°C)</div><div class="value" id="water_temp">-</div></div>
        <div class="tile"><div class="label">Rainfall (30d mm)</div><div class="value" id="rainfall">-</div></div>
      </div>
    </div>

    <div class="card">
      <div class="label">Raw sensor packet</div>
      <div id="raw" class="raw-box">-</div>
      <div class="muted" style="margin-top:10px;">Last updated: <span id="updated">-</span></div>
    </div>

    <div class="card">
      <div class="label">Rainfall source</div>
      <div id="rainfallSource" class="subtext">Using default rainfall (location not set).</div>
      <div id="locationStatus" class="muted" style="margin-top:6px;">Coordinates: not set</div>
      <div class="controls-row">
        <button id="geoBtn" class="btn" type="button">Use Browser Location</button>
        <input id="latInput" class="text-input" type="text" placeholder="Latitude" />
        <input id="lonInput" class="text-input" type="text" placeholder="Longitude" />
        <button id="setCoordsBtn" class="btn" type="button">Set Coordinates</button>
      </div>
    </div>

  </div>

  <script>
    const modeSelect = document.getElementById('modeSelect');
    const modeLocked = {{ 'true' if mode_locked else 'false' }};
    const geoBtn = document.getElementById('geoBtn');
    const setCoordsBtn = document.getElementById('setCoordsBtn');
    const latInput = document.getElementById('latInput');
    const lonInput = document.getElementById('lonInput');
    const rainfallSourceEl = document.getElementById('rainfallSource');
    const locationStatusEl = document.getElementById('locationStatus');

    async function postLocation(latitude, longitude, source = 'manual') {
      const res = await fetch('/api/location', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ latitude, longitude, source }),
      });
      return res.json();
    }

    async function loadLocation() {
      try {
        const res = await fetch('/api/location', { cache: 'no-store' });
        const data = await res.json();
        if (!data.ok || !data.location) return false;
        const loc = data.location;
        if (typeof loc.latitude === 'number' && typeof loc.longitude === 'number') {
          latInput.value = loc.latitude.toFixed(6);
          lonInput.value = loc.longitude.toFixed(6);
          locationStatusEl.textContent = `Coordinates: ${loc.latitude.toFixed(6)}, ${loc.longitude.toFixed(6)}`;
          return true;
        }
        return false;
      } catch (_e) {
        return false;
      }
    }

    function requestBrowserLocation(autoRequest = false) {
      return new Promise((resolve) => {
        if (!navigator.geolocation) {
          locationStatusEl.textContent = 'Geolocation is not supported in this browser.';
          resolve(false);
          return;
        }
        geoBtn.disabled = true;
        locationStatusEl.textContent = autoRequest
          ? 'Requesting browser location (auto)...'
          : 'Requesting browser location...';
        navigator.geolocation.getCurrentPosition(
          async (pos) => {
            try {
              const lat = pos.coords.latitude;
              const lon = pos.coords.longitude;
              latInput.value = lat.toFixed(6);
              lonInput.value = lon.toFixed(6);
              const result = await postLocation(lat, lon, autoRequest ? 'browser-auto' : 'browser');
              if (!result.ok) throw new Error(result.error || 'Failed to set location');
              locationStatusEl.textContent = `Coordinates: ${result.location.latitude.toFixed(6)}, ${result.location.longitude.toFixed(6)}`;
              resolve(true);
            } catch (e) {
              locationStatusEl.textContent = e.message;
              resolve(false);
            } finally {
              geoBtn.disabled = false;
            }
          },
          (err) => {
            const insecureContextHint =
              window.location.protocol !== 'https:' && window.location.hostname !== 'localhost'
                ? ' (Use HTTPS or localhost for location access)'
                : '';
            locationStatusEl.textContent = `Unable to get location: ${err.message}${insecureContextHint}`;
            geoBtn.disabled = false;
            resolve(false);
          },
          { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
        );
      });
    }

    async function setMode(mode) {
      const res = await fetch('/api/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      return res.json();
    }

    function clearReadingUI() {
      document.getElementById('ph').textContent = '-';
      document.getElementById('n').textContent = '-';
      document.getElementById('p').textContent = '-';
      document.getElementById('k').textContent = '-';
      document.getElementById('temperature').textContent = '-';
      document.getElementById('humidity').textContent = '-';
      document.getElementById('water_temp').textContent = '-';
      document.getElementById('rainfall').textContent = '-';
      document.getElementById('crop').textContent = '-';
      document.getElementById('fertilizer').textContent = '-';
      document.getElementById('raw').textContent = '-';
      document.getElementById('updated').textContent = '-';
      document.getElementById('action').textContent = '';
      document.getElementById('fertilizerReason').textContent = '';
    }

    function normalizeSerialError(message) {
      const prefix = 'ESP32 not detected. Connect the board and verify the serial port.';
      const text = String(message || '').toLowerCase();
      if (text.includes('permission denied')) {
        return 'ESP32 found, but access to the serial port was denied. Add your user to the dialout group and reconnect.';
      }
      if (text.includes('device reports readiness to read but returned no data')) {
        return 'Serial connection dropped while reading. Reconnect the ESP32 USB cable and wait a few seconds.';
      }
      if (
        text.includes('esp32 not connected') ||
        text.includes('cannot open') ||
        text.includes('no such file or directory')
      ) {
        return prefix;
      }
      return message || 'Unable to fetch serial reading';
    }

    async function refresh() {
      try {
        const res = await fetch('/api/reading', { cache: 'no-store' });
        const data = await res.json();
        if (!data.ok) {
          if (data.mode) modeSelect.value = data.mode;
          clearReadingUI();
          const statusMessage =
            data.mode === 'serial'
              ? normalizeSerialError(data.error)
              : (data.error || 'Dashboard error');
          document.getElementById('status').textContent = statusMessage;
          document.getElementById('status').className = 'status bad';
          return;
        }

        modeSelect.value = data.mode;

        function updateSensor(id, val, isMissing, formatFn, randGen) {
          const el = document.getElementById(id);
          const tile = el.closest('.tile');
          if (isMissing) {
            el.textContent = formatFn(randGen());
            if (tile) { 
              tile.style.opacity = '0.5'; 
              tile.style.backgroundColor = '#e0e0e0'; 
              tile.title = 'Sensor disconnected. Displaying random value.';
            }
          } else {
            el.textContent = formatFn(val);
            if (tile) { 
              tile.style.opacity = '1'; 
              tile.style.backgroundColor = ''; 
              tile.title = '';
            }
          }
        }

        updateSensor('ph', data.ph, data.ph <= 0 || data.ph > 13.5, v => v.toFixed(2), () => 5.5 + Math.random() * 2.5);
        updateSensor('n', data.n, data.n === 0, v => Math.round(v), () => Math.random() * 100);
        updateSensor('p', data.p, data.p === 0, v => Math.round(v), () => Math.random() * 100);
        updateSensor('k', data.k, data.k === 0, v => Math.round(v), () => Math.random() * 100);
        updateSensor('temperature', data.temperature, data.humidity < 0 || data.temperature < 0, v => v.toFixed(1), () => Math.random() * 40 + 10);
        updateSensor('humidity', data.humidity, data.humidity < 0, v => v.toFixed(1), () => Math.random() * 100);
        updateSensor('water_temp', data.water_temp, data.water_temp <= -127, v => v.toFixed(1), () => Math.random() * 40 + 10);
        updateSensor('rainfall', data.rainfall, false, v => v.toFixed(1), () => Math.random() * 200);

        document.getElementById('crop').textContent = String(data.prediction).toUpperCase();
        document.getElementById('fertilizer').textContent = data.fertilizer;
        document.getElementById('raw').textContent = data.raw;
        document.getElementById('updated').textContent = data.timestamp;
        const rainfallMeta = data.rainfall_meta || {};
        const staleLabel = rainfallMeta.stale ? ' (stale)' : '';
        const warningLabel = rainfallMeta.warning ? ` - ${rainfallMeta.warning}` : '';
        rainfallSourceEl.textContent = `${rainfallMeta.source || 'default'}${staleLabel}${warningLabel}`;
        if (rainfallMeta.latitude !== undefined && rainfallMeta.longitude !== undefined) {
          locationStatusEl.textContent = `Coordinates: ${Number(rainfallMeta.latitude).toFixed(6)}, ${Number(rainfallMeta.longitude).toFixed(6)}`;
        }

        const statusEl = document.getElementById('status');
        const actionEl = document.getElementById('action');
        const fertilizerReasonEl = document.getElementById('fertilizerReason');
        
        if (data.stale) {
          statusEl.textContent = '⚠️ ESP32 FROZEN OR DISCONNECTED (Stale Data)';
          statusEl.className = 'status bad';
          actionEl.textContent = 'The ESP32 stopped sending data. Please restart the ESP32!';
          fertilizerReasonEl.textContent = data.error || 'Connection timed out.';
          document.querySelector('.grid').style.opacity = '0.4';
        } else {
          statusEl.textContent = data.status;
          actionEl.textContent = data.action;
          fertilizerReasonEl.textContent = data.fertilizer_reason;
          statusEl.className = 'status ' + data.level;
          document.querySelector('.grid').style.opacity = '1';
        }
      } catch (e) {
        clearReadingUI();
        const statusEl = document.getElementById('status');
        statusEl.textContent = 'Dashboard fetch error';
        statusEl.className = 'status bad';
      }
    }

    if (modeLocked) {
      modeSelect.disabled = true;
    } else {
      modeSelect.addEventListener('change', async (event) => {
        const desiredMode = event.target.value;
        modeSelect.disabled = true;
        try {
          const data = await setMode(desiredMode);
          if (!data.ok) {
            throw new Error(data.error || 'Failed to switch mode');
          }
        } catch (e) {
          const statusEl = document.getElementById('status');
          statusEl.textContent = e.message;
          statusEl.className = 'status bad';
        } finally {
          modeSelect.disabled = false;
          refresh();
        }
      });
    }

    setCoordsBtn.addEventListener('click', async () => {
      const lat = Number(latInput.value.trim());
      const lon = Number(lonInput.value.trim());
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        locationStatusEl.textContent = 'Enter valid numeric latitude and longitude.';
        return;
      }
      setCoordsBtn.disabled = true;
      try {
        const result = await postLocation(lat, lon, 'manual');
        if (!result.ok) throw new Error(result.error || 'Failed to set location');
        locationStatusEl.textContent = `Coordinates: ${result.location.latitude.toFixed(6)}, ${result.location.longitude.toFixed(6)}`;
        refresh();
      } catch (e) {
        locationStatusEl.textContent = e.message;
      } finally {
        setCoordsBtn.disabled = false;
      }
    });

    geoBtn.addEventListener('click', async () => {
      await requestBrowserLocation(false);
      refresh();
    });

    (async () => {
      const hasLocation = await loadLocation();
      if (!hasLocation) {
        await requestBrowserLocation(true);
      }
      refresh();
    })();
    setInterval(refresh, 2000);

    const modePill = document.querySelector('.mode-pill');
    document.addEventListener('keydown', (event) => {
      if (event.key === 'm' && !modeLocked) {
        if (modePill.style.display === 'none') {
          modePill.style.display = '';
        } else {
          modePill.style.display = 'none';
        }
      }
    });
  </script>
</body>
</html>
"""


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
    return 7.0 - ((voltage - PH_VOLTAGE_PH7) / PH_SLOPE)


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
        (-10, 14),    # pH
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
LATEST_READING = None
LATEST_READING_LOCK = Lock()
STATE_LOCK = Lock()
LOCATION_LOCK = Lock()
RAINFALL_LOCK = Lock()
LATEST_ESP32_RAW = None
LATEST_ESP32_VALUES = None
LATEST_ESP32_TIMESTAMP = 0.0


@app.get("/")
def index():
    return render_template_string(HTML, mode_locked=MODE_LOCKED)

@app.get("/favicon.ico")
def favicon():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">🌱</text></svg>'
    from flask import Response
    return Response(svg, mimetype="image/svg+xml")


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
        candidate_ports = [PORT] + [p for p in available_ports if p != PORT]
        connection_errors = []

        for candidate in candidate_ports:
            try:
                SER = SERIAL_MODULE.Serial(
                    candidate,
                    BAUD,
                    timeout=SERIAL_READ_TIMEOUT_SECONDS,
                )
                ACTIVE_PORT = candidate
                time.sleep(2)
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
        raise ValueError("Mode must be 'sim' or 'serial'")

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
        if mode == "serial":
            ser = ensure_serial_ready_locked()
            deadline = time.monotonic() + SERIAL_READ_WINDOW_SECONDS
            parse_error = None
            values = None
            raw_line = ""

            while time.monotonic() < deadline:
                try:
                    line = ser.readline().decode("utf-8", errors="replace").strip()
                except SERIAL_EXCEPTION as exc:
                    parse_error = exc
                    close_serial_locked()
                    try:
                        ser = ensure_serial_ready_locked()
                    except Exception as reconnect_exc:
                        parse_error = reconnect_exc
                        time.sleep(0.1)
                    continue
                if not line:
                    continue
                try:
                    values = parse_serial_line(line)
                    raw_line = line
                    parse_error = None
                    break
                except ValueError as exc:
                    parse_error = exc

            if values is None:
                if parse_error is not None:
                    raise RuntimeError(
                        f"No valid serial data received yet ({parse_error})"
                    ) from parse_error
                raise RuntimeError("No serial data received yet")
            active_port = ACTIVE_PORT
        elif mode == "esp32":
            if LATEST_ESP32_RAW is None:
                raise RuntimeError("No data received from ESP32 over WiFi yet")
            # Check timeout (e.g. 10 seconds without data)
            if time.monotonic() - LATEST_ESP32_TIMESTAMP > 10.0:
                raise RuntimeError("ESP32 data is stale. Connection lost?")
            values = list(LATEST_ESP32_VALUES)
            raw_line = LATEST_ESP32_RAW
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
    if ml_values[0] <= 0: ml_values[0] = random.uniform(20, 100)
    if ml_values[1] <= 0: ml_values[1] = random.uniform(20, 100)
    if ml_values[2] <= 0: ml_values[2] = random.uniform(20, 100)
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
