#include <DHT.h>
#include <DallasTemperature.h>
#include <OneWire.h>

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

// pH Calibration
const float PH_VOLTAGE_PH7 = 1.251;
const float PH_VOLTAGE_PH4 = 1.769;
const float PH_SLOPE = (PH_VOLTAGE_PH4 - PH_VOLTAGE_PH7) / 3.0;

OneWire oneWire(WATER_TEMP_PIN);
DallasTemperature waterTempSensor(&oneWire);
DHT dht(DHT_PIN, DHT_TYPE);

// Modbus RTU frame for NPK
const byte npkRequest[] = {0x01, 0x03, 0x00, 0x1E, 0x00, 0x03, 0x65, 0xCD};
byte npkResponse[11];

float readWaterTempC() {
  waterTempSensor.requestTemperatures();
  return waterTempSensor.getTempCByIndex(0);
}

float phFromRawCalibrated(int phRaw, float waterTempC) {
  float espVoltage = (phRaw * 3.3) / 4095.0;
  float originalVoltage = espVoltage * 1.5;
  const float tempFactor = (waterTempC + 273.15) / PH_REFERENCE_TEMP_K;
  const float compensatedSlope = PH_SLOPE * tempFactor;
  return 7.0 - ((originalVoltage - PH_VOLTAGE_PH7) / compensatedSlope);
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
  digitalWrite(RE_DE_PIN, HIGH);
  delay(10);
  Serial2.write(npkRequest, sizeof(npkRequest));
  Serial2.flush();
  digitalWrite(RE_DE_PIN, LOW);
  delay(100);

  int n = 0, p = 0, k = 0;
  if (Serial2.available() >= 11) {
    for (int i = 0; i < 11; i++) {
      npkResponse[i] = Serial2.read();
    }
    n = (npkResponse[3] << 8) | npkResponse[4];
    p = (npkResponse[5] << 8) | npkResponse[6];
    k = (npkResponse[7] << 8) | npkResponse[8];
  } else {
    while (Serial2.available()) { Serial2.read(); }
  }

  // Output CSV string for Python backend
  String rawCsv = String(phValue, 2) + "," + String(n) + "," + String(p) + "," + String(k) + "," + String(dhtTemp, 1) + "," + String(humidity, 1);
  Serial.println(rawCsv);

  delay(LOOP_DELAY_MS);
}
