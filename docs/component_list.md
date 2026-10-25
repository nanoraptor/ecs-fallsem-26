# SoilSage: Component List & Bill of Materials

**Course:** ECS2001 — Project Ideation, Design and Prototyping  
**Created by:** Rahul, Abhiram, Nikhil, Sanjeev, Saketh and Shyam  

> [!IMPORTANT]
> The primary microcontroller for this project is strictly the **38-Pin ESP32 NodeMCU (DevKitC V4 / NodeMCU-32S)**.

---

## Bill of Materials (BOM)

| Item | Specification / Model | Qty | Est. Cost (INR) | Primary Pin Connections |
|---|---|---:|---|---|
| **Microcontroller** | **ESP32 NodeMCU 38-Pin** (ESP-WROOM-32) | 1 | ₹450 - ₹650 | Central processing unit |
| **NPK Soil Sensor** | RS485 Modbus RTU 3-probe (N, P, K) | 1 | ₹2,800 - ₹3,800 | 12V DC Ext Power + MAX485 differential bus |
| **RS485 Transceiver** | MAX485 TTL-to-RS485 Converter Module | 1 | ₹50 - ₹100 | `RX2` (16), `TX2` (17), `D4` (4), `VIN` (5V), `GND` |
| **pH Sensor & Probe** | Analog pH Sensor with BNC amplifier module | 1 | ₹1,600 - ₹2,400 | `D34` (via 10kΩ series resistor), `VIN` (5V), `GND` |
| **Water Temp Sensor** | Dallas DS18B20 waterproof probe | 1 | ₹180 - ₹250 | `D5` (with 4.7kΩ pull-up to 3.3V), `3V3`, `GND` |
| **Air Temp & Humidity** | DHT11 Sensor Module | 1 | ₹120 - ₹180 | `D18`, `3V3`, `GND` |
| **Display Unit** | 16×2 Character LCD with I2C Backing (`0x27`) | 1 | ₹180 - ₹260 | `D21` (SDA), `D22` (SCL), `VIN` (5V), `GND` |
| **External Power Supply** | 12V 1A / 2A DC Power Adapter | 1 | ₹180 - ₹300 | Powering RS485 NPK Sensor prongs |
| **Prototyping Board** | Standard 830-point Solderless Breadboard | 1 | ₹100 - ₹160 | Power rails & circuit distribution |
| **Jumper Wires** | Male-to-Male & Male-to-Female assortment | 40 pcs | ₹120 | Interconnections |
| **USB Data Cable** | Micro-USB to USB-A data & power cable | 1 | ₹100 | ESP32 programming & serial telemetry |
| **Current Limiting Resistor** | 10kΩ 1/4W Resistor | 1 | < ₹2 | Series protection between pH `AO` and `D34` |
| **Pull-up Resistor** | 4.7kΩ 1/4W Resistor | 1 | < ₹2 | OneWire pull-up for DS18B20 on `D5` |
| **pH Buffer Capsules** | SDFCL Analytical Buffers (pH 4.0, 7.0, 9.2) | 1 set | ₹250 - ₹400 | Dual-slope calibration |
| **Distilled Water** | 1 Liter Pure Distilled Water | 1 bottle | ₹50 - ₹80 | Probe rinsing between soil specimens |
| **KCl Storage Solution** | 3M Potassium Chloride solution (50ml) | 1 | ₹150 - ₹250 | pH bulb hydration & electrode longevity |
| **Total Estimated Cost** | | | **~₹6,500 - ₹9,000** | |

---

## Module Sourcing & Compatibility Notes

1. **ESP32 38-Pin Form Factor:**  
   Ensure the board has 19 pins per header side (labeled `NodeMCU-32S` or `ESP32 DevKitC`). Unlike the 30-pin board, GPIOs 16 (`RX2`) and 17 (`TX2`) are broken out next to GPIO 4 (`D4`) on the right header, simplifying the MAX485 wiring harness.
2. **NPK Soil Sensor:**  
   Must use the 4800 baud Modbus RTU protocol querying registers `0x001E`–`0x0020`. Powered strictly via 9V–24V DC (do not power directly from ESP32 3.3V or 5V pin).
3. **pH Electrode Glass Bulb:**  
   Requires careful handling. Store with wet protective cap filled with 3M KCl solution. Never allow the bulb to dry out.
