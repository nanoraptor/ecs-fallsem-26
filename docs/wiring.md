# SoilSage Wiring Guide (38-Pin ESP32 NodeMCU-32S)

Pin positions come from the physical board. The labels printed on the back of the board appear mirrored
(left and right swapped) compared with the top view used here. Do **not** use the 30-pin DevKit V1: its header layout differs.

## 1. Board pin map (top view, USB at the bottom)

```text
                                                  ┌────────────────────────┐
                                                  │     ESP-32S module     │
                                                  │   (antenna end, top)   │
                                                  ├────────────────────────┤
  3V3 rail (DS18B20, DHT11, 4.7k pull-up) ──  3V3 │  1                   1 │ GND  ── Digital GND rail (LCD, MAX485, 12V -, DHT11, DS18B20)
                                               EN │  2                   2 │ D23
                                               VP │  3                   3 │ D22  ── LCD SCL
                                               VN │  4                   4 │ TX0
         pH module AO/SIG, via 10k series ──  D34 │  5                   5 │ RX0
                                              D35 │  6                   6 │ D21  ── LCD SDA
                                              D32 │  7                   7 │ GND  ── Digital GND (spare, same rail)
                                              D33 │  8                   8 │ D19
                                              D25 │  9                   9 │ D18  ── DHT11 DATA
                                              D26 │ 10                  10 │ D5   ── DS18B20 DATA (+4.7k to 3V3)
                                              D27 │ 11                  11 │ D17  ── MAX485 DI  (TX2)
                                              D14 │ 12                  12 │ D16  ── MAX485 RO  (RX2)
                                              D12 │ 13                  13 │ D4   ── MAX485 DE + RE (jumpered)
    pH module GND ONLY (clean analog GND) ──  GND │ 14                  14 │ D0
                                              D13 │ 15                  15 │ D2
                                              SD2 │ 16                  16 │ D15
                                              SD3 │ 17                  17 │ SD1
                                             CMD* │ 18                  18 │ SD0
                5V rail (pH, MAX485, LCD) ──   5V │ 19                  19 │ CLK
                                                  ├────────────────────────┤
                                                  │        [ USB ]         │
                                                  └────────────────────────┘
```

`*` The pin just above `5V` may be silkscreened `GND` on some boards, but it is `CMD` on standard 38-pin boards. Do not use it.
`VP` = GPIO36, `VN` = GPIO39, `TX0` = GPIO1, `RX0` = GPIO3, `D17` = TX2, `D16` = RX2.

## 2. Power rails and grounding

The board has one 3V3 pin, one 5V pin and three GND pins, so build these rails on a breadboard:

```text
 ESP32 3V3 (left header, row 1)    ──►  3V3 RAIL      ──► DS18B20 VCC, DHT11 VCC, 4.7k pull-up
 ESP32 5V  (left header, row 19)   ──►  5V RAIL       ──► pH VCC, MAX485 VCC, LCD VCC
 ESP32 GND (left header, row 14)   ──►  pH GND ONLY                       [clean analog ground]
 ESP32 GND (right header, row 1/7) ──►  DIGITAL GND RAIL ──► LCD, MAX485, 12V supply (-), DHT11, DS18B20
```

**Why the pH ground is separate:** the pH probe is a very sensitive analog signal (about 59 mV per pH unit).
Switching loads such as the LCD backlight, the MAX485 and the 12V NPK supply cause small voltage drops
("ground bounce") on a shared ground track, which makes the pH reading jump. Give the pH module its own GND pin
and put everything else on the digital ground rail.

All GND pins are joined inside the board, so this reduces noise coupling but is not isolation. The 12V supply
negative must still connect to the ESP32 ground (via the digital GND rail) so every signal shares one reference.

## 3. Module wiring

### pH probe module
```text
 pH module                         ESP32 / rails
 ┌─────────────┐
 │ Po (analog) ├──[ 10k ohm ]────► D34 (GPIO34)            left header, row 5
 │ V+          ├─────────────────► 5V rail
 │ G           ├─────────────────► ESP32 GND, left row 14  (pH ONLY, nothing else on this pin)
 └─────────────┘
 Leave To and Do unconnected.
```

### MAX485 + NPK sensor (RS485)
```text
 MAX485                          ESP32 / NPK sensor
 ┌──────────────┐
 │ RO           ├───────────────► D16 (GPIO16, RX2)        right header, row 12
 │ DI           ├◄──────────────  D17 (GPIO17, TX2)        right header, row 11
 │ DE ─┐ jumper │
 │ RE ─┴────────┼◄──────────────  D4  (GPIO4)              right header, row 13
 │ VCC          ├───────────────► 5V rail
 │ GND          ├───────────────► Digital GND rail
 │ A            ├───────────────► NPK Yellow wire
 │ B            ├───────────────► NPK Blue wire
 └──────────────┘

 NPK sensor power (separate 12V supply):
   Brown wire ──► 12V DC (+)
   Black wire ──► 12V DC (-)  AND  Digital GND rail   (common ground is mandatory)
```

### DS18B20 temperature probe
```text
 DS18B20
 ┌──────┐
 │ DATA ├──────┬─────────────────► D5 (GPIO5)              right header, row 10
 │      │   [4.7k]
 │ VCC  ├──────┴─────────────────► 3V3 rail   (pull-up between DATA and 3V3)
 │ GND  ├─────────────────────────► Digital GND rail
 └──────┘
```

### DHT11 air sensor
```text
 DHT11
 ┌──────┐
 │ DATA ├─────────────────────────► D18 (GPIO18)            right header, row 9
 │ VCC  ├─────────────────────────► 3V3 rail
 │ GND  ├─────────────────────────► Digital GND rail
 └──────┘
```

### 16x2 I2C LCD (address 0x27)
```text
 LCD (I2C backpack)
 ┌──────┐
 │ SDA  ├─────────────────────────► D21 (GPIO21)            right header, row 6
 │ SCL  ├─────────────────────────► D22 (GPIO22)            right header, row 3
 │ VCC  ├─────────────────────────► 5V rail
 │ GND  ├─────────────────────────► Digital GND rail
 └──────┘
```

## 4. Connection table

| Module | Module pin | Connects to | Header / row (top view) | Notes |
|---|---|---|---|---|
| pH probe | SIG / AO | D34 (GPIO34) | left, row 5 | 10k series resistor |
| pH probe | VCC | 5V rail | | |
| pH probe | GND | ESP32 GND | left, row 14 | Dedicated clean analog ground, pH only |
| MAX485 | RO | D16 (RX2) | right, row 12 | UART2 receive |
| MAX485 | DI | D17 (TX2) | right, row 11 | UART2 transmit |
| MAX485 | DE + RE | D4 (GPIO4) | right, row 13 | Jumpered together |
| MAX485 | VCC / GND | 5V rail / Digital GND rail | | |
| MAX485 | A / B | NPK Yellow / Blue | | Differential pair |
| NPK sensor | Brown / Black | 12V (+) / 12V (-) | | Black also to Digital GND rail |
| DS18B20 | DATA | D5 (GPIO5) | right, row 10 | 4.7k pull-up to 3V3 |
| DS18B20 | VCC / GND | 3V3 rail / Digital GND rail | | |
| DHT11 | DATA | D18 (GPIO18) | right, row 9 | |
| DHT11 | VCC / GND | 3V3 rail / Digital GND rail | | |
| LCD | SDA | D21 (GPIO21) | right, row 6 | |
| LCD | SCL | D22 (GPIO22) | right, row 3 | |
| LCD | VCC / GND | 5V rail / Digital GND rail | | |

Digital GND rail feeds from the ESP32 GND at right header row 1 (or row 7).

## 5. Notes

- ESP32 GPIOs are 3.3V only. A MAX485 module powered from 5V drives `RO` at 5V logic, so put a voltage divider
  or level shifter on `RO` before `D16`, or use a 3.3V-compatible MAX485 module.
- Confirm the pH module's `AO` never exceeds 3.3V at the ADC. The 10k series resistor only limits current,
  it does not divide the voltage.
- For a steadier pH reading, keep the pH wires short and away from the RS485 and 12V wiring, add a 100nF capacitor
  from D34 to GND close to the ESP32, and average several ADC samples in firmware.
- DS18B20 reading -127 C means DATA is loose or the 4.7k pull-up is missing.
