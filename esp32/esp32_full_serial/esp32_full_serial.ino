#include <DHT.h>
#include <DallasTemperature.h>
#include <OneWire.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);

// --- Pin Definitions (ESP32 38-Pin) ---
#define PH_PIN 34          // ADC1_CH6
#define DHT_PIN 18         // GPIO18
#define WATER_TEMP_PIN 5   // GPIO5
#define DHT_TYPE DHT11

// RS485 / MAX485 pins
#define RE_DE_PIN 4        // GPIO4
#define RX_PIN 16          // RX2
#define TX_PIN 17          // TX2

const uint16_t LOOP_DELAY_MS = 2000;
const float DEFAULT_COMPENSATION_TEMP_C = 25.0;
const float PH_REFERENCE_TEMP_K = 298.15;

// pH Calibration (Calibrated with SDFCL pH 4.0, 7.0, and 9.2 buffers with DS18B20 at ~30.5°C)
const float PH_VOLTAGE_PH7 = 1.114;
const float PH_SLOPE_ACID = 0.1805;    // V/pH for pH < 7 (normalized to 25°C)
const float PH_SLOPE_ALKALINE = 0.1438; // V/pH for pH >= 7 (normalized to 25°C)
const float PH_SLOPE = PH_SLOPE_ACID;

OneWire oneWire(WATER_TEMP_PIN);
DallasTemperature waterTempSensor(&oneWire);
DHT dht(DHT_PIN, DHT_TYPE);

// Modbus RTU frame for NPK
const byte npkRequest[] = {0x01, 0x03, 0x00, 0x1E, 0x00, 0x03, 0x65, 0xCD};
byte npkResponse[32];

float readWaterTempC() {
  waterTempSensor.requestTemperatures();
  return waterTempSensor.getTempCByIndex(0);
}

float phFromRawCalibrated(int phRaw, float waterTempC) {
  float espVoltage = (phRaw * 3.3) / 4095.0;
  // With 10kΩ series protection resistor (direct ADC connection, no divider):
  float originalVoltage = espVoltage;
  const float tempFactor = (waterTempC + 273.15) / PH_REFERENCE_TEMP_K;
  // Dual-slope temperature compensation (acid vs alkaline)
  const float slope = (originalVoltage > PH_VOLTAGE_PH7 ? PH_SLOPE_ACID : PH_SLOPE_ALKALINE) * tempFactor;
  return 7.0 - ((originalVoltage - PH_VOLTAGE_PH7) / slope);
}

int readAverageRaw(uint8_t pin, uint8_t samples, uint8_t sampleDelayMs = 10) {
  long total = 0;
  for (uint8_t i = 0; i < samples; i++) {
    total += analogRead(pin);
    delay(sampleDelayMs);
  }
  return (int)(total / samples);
}

void setup() {
  Serial.begin(115200);
  
  // Initialize RS485 on Serial2
  Serial2.begin(4800, SERIAL_8N1, RX_PIN, TX_PIN);
  pinMode(RE_DE_PIN, OUTPUT);
  digitalWrite(RE_DE_PIN, LOW); // Receive mode

  waterTempSensor.begin();
  dht.begin();
  
  // Initialize LCD
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("SoilSage Serial");
  lcd.setCursor(0, 1);
  lcd.print("Initializing...");
  
  analogReadResolution(12);
  analogSetPinAttenuation(PH_PIN, ADC_11db);
  
  Serial.println("ESP32 Serial Mode Started!");
}

void loop() {
  float waterTemp = readWaterTempC();
  bool waterTempOk = (waterTemp != DEVICE_DISCONNECTED_C && waterTemp >= -55.0 && waterTemp <= 125.0);
  float compensationTempC = waterTempOk ? waterTemp : DEFAULT_COMPENSATION_TEMP_C;

  int phRaw = readAverageRaw(PH_PIN, 20, 20);
  float phValue = phFromRawCalibrated(phRaw, compensationTempC);
  
  float dhtTemp = dht.readTemperature();
  float humidity = dht.readHumidity();
  if (isnan(dhtTemp)) dhtTemp = -1.0;
  if (isnan(humidity)) humidity = -1.0;

  // Read NPK
  while (Serial2.available()) { Serial2.read(); } // Clear stale bytes
  digitalWrite(RE_DE_PIN, HIGH);
  delay(5);
  Serial2.write(npkRequest, sizeof(npkRequest));
  Serial2.flush();
  digitalWrite(RE_DE_PIN, LOW);

  // Wait up to 400ms for full Modbus response
  unsigned long startWait = millis();
  while (Serial2.available() < 11 && (millis() - startWait) < 400) {
    delay(10);
  }

  int n = -1, p = -1, k = -1;
  int bytesReceived = Serial2.available();
  if (bytesReceived >= 11) {
    int readLen = (bytesReceived > (int)sizeof(npkResponse)) ? sizeof(npkResponse) : bytesReceived;
    for (int i = 0; i < readLen; i++) {
      npkResponse[i] = Serial2.read();
    }

    // Find the Modbus header (0x01 0x03 0x06) to ignore line-transient glitch bytes (0x00 / 0xFF)
    int headerIndex = -1;
    for (int i = 0; i <= readLen - 9; i++) {
      if (npkResponse[i] == 0x01 && npkResponse[i + 1] == 0x03 && npkResponse[i + 2] == 0x06) {
        headerIndex = i;
        break;
      }
    }

    if (headerIndex != -1) {
      n = (npkResponse[headerIndex + 3] << 8) | npkResponse[headerIndex + 4];
      p = (npkResponse[headerIndex + 5] << 8) | npkResponse[headerIndex + 6];
      k = (npkResponse[headerIndex + 7] << 8) | npkResponse[headerIndex + 8];
    }
  }
  while (Serial2.available()) { Serial2.read(); }

  // Output CSV string for Python backend
  String rawCsv = String(phValue, 2) + "," + String(n) + "," + String(p) + "," + String(k) + "," + String(dhtTemp, 1) + "," + String(humidity, 1) + "," + String(waterTemp, 1);
  Serial.println(rawCsv);

  // Update LCD
  static bool showAltScreen = false;
  lcd.clear();
  if (!showAltScreen) {
    lcd.setCursor(0, 0);
    lcd.print("pH:"); lcd.print(phValue, 1);
    lcd.print(" T:"); lcd.print(dhtTemp, 1); lcd.print("C");
    lcd.setCursor(0, 1);
    lcd.print("N:"); lcd.print(n);
    lcd.print(" P:"); lcd.print(p);
    lcd.print(" K:"); lcd.print(k);
  } else {
    lcd.setCursor(0, 0);
    lcd.print("Sol Temp: "); lcd.print(waterTemp, 1); lcd.print("C");
    lcd.setCursor(0, 1);
    lcd.print("Humidity: "); lcd.print(humidity, 1); lcd.print("%");
  }
  showAltScreen = !showAltScreen;

  delay(LOOP_DELAY_MS);
}
