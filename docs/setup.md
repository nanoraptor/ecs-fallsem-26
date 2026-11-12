# SoilSage: 38-Pin ESP32 Hardware Setup & Wiring Guide

**Course:** ECS2001 — Project Ideation, Design and Prototyping  
**Created by:** Rahul, Abhiram, Nikhil, Sanjeev, Saketh and Shyam  

> [!IMPORTANT]
> **Hardware Specification:**  
> This project is designed and wired **strictly for the 38-Pin ESP32 NodeMCU (DevKitC V4 / NodeMCU-32S)**.  
> **Do NOT use the 30-Pin ESP32 DevKit V1** — the pinouts, GPIO locations, and power routing differ significantly.

---

## 1. 38-Pin ESP32 Board Pinout Diagram (NodeMCU ESP-32S)

The 38-Pin ESP32 board (`NodeMCU ESP-32S V1.1`) features two rows of 19 pins with standard 0.1" (2.54mm) pitch.  
Both the **Top (Breadboard View)** and the **Bottom (Silkscreen View on the underside of the PCB)** are provided below:

### Top View (Component & Breadboard View)
```text
                         38-PIN ESP32 NodeMCU (ESP-32S)
                             TOP VIEW (BREADBOARD)
                               [ Antenna Area ]
                           +----------------------+
                     3V3 --|  1 [ ]        [ ] 38 |-- GND (Common Ground)
                      EN --|  2 [ ]        [ ] 37 |-- P23 (GPIO 23)
       (GPIO 36)     SVP --|  3 [ ]        [ ] 36 |-- P22 (GPIO 22) -> LCD SCL
       (GPIO 39)     SVN --|  4 [ ]        [ ] 35 |-- TX  (GPIO 1 / TX0)
pH In  (GPIO 34)     P34 --|  5 [ ]        [ ] 34 |-- RX  (GPIO 3 / RX0)
                     P35 --|  6 [ ]        [ ] 33 |-- P21 (GPIO 21) -> LCD SDA
                     P32 --|  7 [ ]        [ ] 32 |-- GND (Ground)
                     P33 --|  8 [ ]        [ ] 31 |-- P19 (GPIO 19)
                     P25 --|  9 [ ]        [ ] 30 |-- P18 (GPIO 18) -> DHT11 Data
                     P26 --| 10 [ ]        [ ] 29 |-- P5  (GPIO 5)  -> DS18B20 Temp
                     P27 --| 11 [ ]        [ ] 28 |-- P17 (GPIO 17) -> MAX485 DI (TX2)
                     P14 --| 12 [ ]        [ ] 27 |-- P16 (GPIO 16) -> MAX485 RO (RX2)
                     P12 --| 13 [ ]        [ ] 26 |-- P4  (GPIO 4)  -> MAX485 DE+RE
                     GND --| 14 [ ]        [ ] 25 |-- P0  (GPIO 0 / Boot)
                     P13 --| 15 [ ]        [ ] 24 |-- P2  (GPIO 2 / Onboard LED)
                     SD2 --| 16 [ ]        [ ] 23 |-- P15 (GPIO 15)
                     SD3 --| 17 [ ]        [ ] 22 |-- SD1 (Flash SD1)
                     CMD --| 18 [ ]        [ ] 21 |-- SDD (Flash SD0)
5V In / VIN           5V --| 19 [ ]        [ ] 20 |-- CLK (Flash CLK)
                           +----------USB---------+
```

### Bottom View (Silkscreen View on Underside of PCB)
*(Matches the silkscreen text printed on the back of your NodeMCU ESP-32S board)*
```text
                         38-PIN ESP32 NodeMCU (ESP-32S)
                       BOTTOM VIEW (SILKSCREEN / BACK)
                               [ Antenna Area ]
                           +----------------------+
         (Common Ground) GND --| 38 [ ]        [ ]  1 |-- 3V3
                    (GPIO 23) P23 --| 37 [ ]        [ ]  2 |-- EN
            LCD SCL <- (GPIO 22) P22 --| 36 [ ]        [ ]  3 |-- SVP     (GPIO 36)
             TX0 / GPIO 1 <-  TX  --| 35 [ ]        [ ]  4 |-- SVN     (GPIO 39)
             RX0 / GPIO 3 <-  RX  --| 34 [ ]        [ ]  5 |-- P34     (GPIO 34) -> pH In
            LCD SDA <- (GPIO 21) P21 --| 33 [ ]        [ ]  6 |-- P35
                    (Ground) GND --| 32 [ ]        [ ]  7 |-- P32
                    (GPIO 19) P19 --| 31 [ ]        [ ]  8 |-- P33
         DHT11 Data <- (GPIO 18) P18 --| 30 [ ]        [ ]  9 |-- P25
       DS18B20 Temp <- (GPIO 5)  P5  --| 29 [ ]        [ ] 10 |-- P26
       MAX485 DI (TX2) <- (GPIO 17) P17 --| 28 [ ]        [ ] 11 |-- P27
       MAX485 RO (RX2) <- (GPIO 16) P16 --| 27 [ ]        [ ] 12 |-- P14
     MAX485 DE+RE <- (GPIO 4)  P4  --| 26 [ ]        [ ] 13 |-- P12
                    (GPIO 0)  P0  --| 25 [ ]        [ ] 14 |-- GND     (Ground)
                    (GPIO 2)  P2  --| 24 [ ]        [ ] 15 |-- P13
                    (GPIO 15) P15 --| 23 [ ]        [ ] 16 |-- SD2
                               SD1 --| 22 [ ]        [ ] 17 |-- SD3
                               SDD --| 21 [ ]        [ ] 18 |-- CMD
                               CLK --| 20 [ ]        [ ] 19 |-- 5V      (VIN / 5V In)
                           +----------USB---------+
```

---

## 2. Complete Module Connection Table

All connections are mapped specifically to the **38-Pin ESP32 (NodeMCU ESP-32S)**:

| Peripheral Module | Module Pin | ESP32 Pin (Silkscreen) | Notes & Requirements |
|---|---|---|---|
| **Analog pH Sensor Module** | `VCC` | **`5V`** (VIN, Pin 19) | Powered from 5V rail for operational amplifier stability |
| | `GND` | **`GND`** (Pin 14 / 32 / 38) | Common ground rail |
| | `SIG` / `AO` | **`P34`** (GPIO 34, Pin 5) | Connect in series through a **10kΩ protection resistor** (Sensor `AO` -> 10kΩ resistor -> `P34`). Protects the 3.3V ESP32 ADC pin. |
| **RS485 MAX485 Converter** | `VCC` | **`5V`** (VIN, Pin 19) | Powers the TTL transceiver |
| | `GND` | **`GND`** (Pin 14 / 32 / 38) | Tied to ESP32 ground |
| | `RO` (Receiver Out) | **`P16`** (RX2 / GPIO 16, Pin 27) | Hardware UART2 Receive line |
| | `DI` (Driver In) | **`P17`** (TX2 / GPIO 17, Pin 28) | Hardware UART2 Transmit line |
| | `DE` (Driver Enable) | **`P4`** (GPIO 4, Pin 26) | Jumpered together with `RE` |
| | `RE` (Receiver Enable) | **`P4`** (GPIO 4, Pin 26) | Low = Listen, High = Transmit |
| | `A` (RS485 +) | NPK Yellow Cable | Differential RS485 data line A |
| | `B` (RS485 -) | NPK Blue Cable | Differential RS485 data line B |
| **NPK Soil Sensor (3-Prong)** | Brown Wire (`VCC`) | External DC Power (+) | **12V DC External Power Supply** (9V–24V supported) |
| | Black Wire (`GND`) | External DC Power (-) | **MUST be bridged to ESP32 GND** (Common Reference) |
| | Yellow Wire (`A`) | MAX485 `A` terminal | RS485 Non-inverting |
| | Blue Wire (`B`) | MAX485 `B` terminal | RS485 Inverting |
| **DS18B20 Temp Probe** | `VCC` (Red) | **`3V3`** (Pin 1) | 3.3V logic level |
| | `GND` (Black) | **`GND`** (Pin 14 / 32 / 38) | Common ground |
| | `DATA` (Yellow/White)| **`P5`** (GPIO 5, Pin 29) | Use **4.7kΩ pull-up resistor** between `DATA` and `3V3` |
| **DHT11 Air Temp & Hum** | `VCC` (+) | **`3V3`** (Pin 1) | 3.3V logic level |
| | `GND` (-) | **`GND`** (Pin 14 / 32 / 38) | Common ground |
| | `DATA` (Out) | **`P18`** (GPIO 18, Pin 30) | Single-bus digital communication |
| **16×2 I2C LCD Display** | `VCC` | **`5V`** (VIN, Pin 19) | Needs 5V for crisp backlight & contrast |
| | `GND` | **`GND`** (Pin 14 / 32 / 38) | Common ground |
| | `SDA` | **`P21`** (GPIO 21, Pin 33) | ESP32 Hardware I2C Data (`0x27` address) |
| | `SCL` | **`P22`** (GPIO 22, Pin 36) | ESP32 Hardware I2C Clock |

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
