# SoilSage: 38-Pin ESP32 Hardware Setup & Wiring Guide

**Course:** ECS2001 — Project Ideation, Design and Prototyping  
**Created by:** Rahul, Abhiram, Nikhil, Sanjeev, Saketh and Shyam  

> [!IMPORTANT]
> **Hardware Specification:**  
> This project is designed and wired **strictly for the 38-Pin ESP32 NodeMCU (DevKitC V4 / NodeMCU-32S)**.  
> **Do NOT use the 30-Pin ESP32 DevKit V1** — the pinouts, GPIO locations, and power routing differ significantly.

---

## 1. 38-Pin ESP32 Board Pinout Diagram

The 38-Pin ESP32 board features two rows of 19 pins with standard 0.1" (2.54mm) pitch:

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

---

## 2. Complete Module Connection Table

All connections are mapped specifically to the **38-Pin ESP32**:

| Peripheral Module | Module Pin | ESP32 Pin (38-Pin Board) | Notes & Requirements |
|---|---|---|---|
| **Analog pH Sensor Module** | `VCC` | `VIN` (5V) | Powered from 5V rail for operational amplifier stability |
| | `GND` | `GND` | Common ground rail |
| | `SIG` / `AO` | **`D34`** (GPIO 34) | **10kΩ series resistor** between sensor `AO` and `D34` (limits ESD & protects ADC1_CH6) |
| **RS485 MAX485 Converter** | `VCC` | `VIN` (5V) or `3V3` | Powers the TTL transceiver |
| | `GND` | `GND` | Tied to ESP32 ground |
| | `RO` (Receiver Out) | **`RX2`** (GPIO 16) | Hardware UART2 Receive line |
| | `DI` (Driver In) | **`TX2`** (GPIO 17) | Hardware UART2 Transmit line |
| | `DE` (Driver Enable) | **`D4`** (GPIO 4) | Jumpered together with `RE` |
| | `RE` (Receiver Enable) | **`D4`** (GPIO 4) | Low = Listen, High = Transmit |
| | `A` (RS485 +) | NPK Yellow Cable | Differential RS485 data line A |
| | `B` (RS485 -) | NPK Blue Cable | Differential RS485 data line B |
| **NPK Soil Sensor (3-Prong)** | Brown Wire (`VCC`) | External DC Power (+) | **12V DC External Power Supply** (9V–24V supported) |
| | Black Wire (`GND`) | External DC Power (-) | **MUST be bridged to ESP32 GND** (Common Reference) |
| | Yellow Wire (`A`) | MAX485 `A` terminal | RS485 Non-inverting |
| | Blue Wire (`B`) | MAX485 `B` terminal | RS485 Inverting |
| **DS18B20 Temp Probe** | `VCC` (Red) | `3V3` | 3.3V logic level |
| | `GND` (Black) | `GND` | Common ground |
| | `DATA` (Yellow/White)| **`D5`** (GPIO 5) | **4.7kΩ pull-up resistor** between `DATA` and `3V3` |
| **DHT11 Air Temp & Hum** | `VCC` (+) | `3V3` | 3.3V logic level |
| | `GND` (-) | `GND` | Common ground |
| | `DATA` (Out) | **`D18`** (GPIO 18) | Single-bus digital communication |
| **16×2 I2C LCD Display** | `VCC` | `VIN` (5V) | Requires 5V for crisp backlight & contrast |
| | `GND` | `GND` | Common ground |
| | `SDA` | **`D21`** (GPIO 21) | ESP32 Hardware I2C Data (`0x27` address) |
| | `SCL` | **`D22`** (GPIO 22) | ESP32 Hardware I2C Clock |

---

## 3. Power Architecture & Critical Grounding Rule

```text
 +-------------------------+
 | External 12V DC Supply  |
 |  (+) ------------------------------------------> NPK Sensor Brown (VCC)
 |  (-) --------+---------------------------------> NPK Sensor Black (GND)
 +--------------|----------+
                |
                +-- COMMON GROUND BRIDGE (CRITICAL!)
                |
 +--------------|----------+
 | ESP32 38-Pin Board      |
 |  GND --------+----------> MAX485 GND, pH GND, DS18B20 GND, DHT11 GND, LCD GND
 |  VIN (5V) --------------> MAX485 VCC, pH VCC, LCD VCC
 |  3V3 -------------------> DS18B20 VCC, DHT11 VCC, 4.7kΩ Pull-up
 |  USB (5V) --------------> Powered via PC / Power Bank USB
 +-------------------------+
```

> [!CAUTION]
> **Common Ground Requirement:**  
> The external 12V DC power supply ground **MUST** be connected directly to the ESP32 `GND` rail on your breadboard. Without this common ground, the RS485 differential signals float, causing communication timeouts (`NPK Sensor Disconnected`).

---

## 4. Sensor Calibration & Agricultural Chemistry

### Dual-Slope Calibrated pH
Standard glass-bulb pH electrodes exhibit different voltage slopes in acidic vs. alkaline regimes and shift with temperature (Nernst equation):

$$V_{\text{pH}} = V_{\text{pH7}} - \text{Slope} \times (\text{pH} - 7) \times \left(\frac{T_K}{298.15}\right)$$

SoilSage implements dual-slope temperature compensation utilizing live solution temperature from the DS18B20 probe:
- **Reference Voltage ($V_{\text{pH7}}$):** `1.114 V`
- **Acidic Slope ($< 7.0$):** `0.1805 V/pH` (normalized to 25°C)
- **Alkaline Slope ($\ge 7.0$):** `0.1438 V/pH` (normalized to 25°C)
- Calibrated using SDFCL analytical buffer capsules at pH 4.0, 7.0, and 9.2 at ~30.5°C.

### Safe Soil Slurry Preparation
1. Mix soil and distilled water in a **1:2 weight ratio** (e.g., 20g soil in 40ml distilled water).
2. Stir vigorously for 2 minutes and allow solid sand particles to settle for 5 minutes.
3. Submerge only the glass bulb and reference junction into the supernatant liquid.
4. **Never** force the pH electrode into dry or gritty soil — use the stainless-steel NPK prongs for direct soil insertion.

---

## 5. Fail-Safe Zero-Sensing & Display Protocols

When the NPK sensor is dry or in the air, electric conductivity is zero ($N = 0, P = 0, K = 0$).

1. **16×2 LCD Readout:**
   - **Line 0:** Shows live telemetry (`pH:6.5  T:30.5C` alternating with `N:0   P:0   K:0 `).
   - **Line 1:** Persistently displays `Insert Soil Smpl` so you always know the probe needs moist soil.
2. **Web Dashboard Console:**
   - **Pillar 01:** Displays `Please insert soil sample` without match percentage.
   - **Pillar 02:** Displays `Awaiting soil sample` and clears chemical rates.
   - **Pillar 03:** Header shifts to `◉ 03 / Awaiting Soil Sample`.
   - **Sensor Readings Tiles:** Displays `0 mg/kg` (status `Low`) with active indicators (not greyed out).
