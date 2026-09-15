#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <DallasTemperature.h>
#include <OneWire.h>

// --- WiFi Credentials ---
const char* ssid = "rahkickz-mb";
const char* password = "123456789";

// --- Flask Server ---
// Replace with the IP address of the machine running app.py
const char* serverUrl = "http://172.20.54.242:5000/api/esp32_reading"; 

// --- Pin Definitions (ESP32 38-Pin) ---
#define PH_PIN 34          // ADC1_CH6 (Input only)
#define DHT_PIN 18         // GPIO18
#define WATER_TEMP_PIN 5   // GPIO5
#define DHT_TYPE DHT11

// RS485 / MAX485 pins using HardwareSerial (Serial2)
#define RE_DE_PIN 4        // GPIO4
#define RX_PIN 16          // RX2
#define TX_PIN 17          // TX2

const uint16_t LOOP_DELAY_MS = 3000;
const float DEFAULT_COMPENSATION_TEMP_C = 25.0;
const float PH_REFERENCE_TEMP_K = 298.15;

// pH Calibration Voltages (These are original 5V scale voltages)
const float PH_VOLTAGE_PH7 = 1.251;
const float PH_VOLTAGE_PH4 = 1.769;
const float PH_SLOPE = (PH_VOLTAGE_PH4 - PH_VOLTAGE_PH7) / 3.0;

OneWire oneWire(WATER_TEMP_PIN);
DallasTemperature waterTempSensor(&oneWire);
DHT dht(DHT_PIN, DHT_TYPE);

// Modbus RTU frame for NPK
const byte npkRequest[] = {0x01, 0x03, 0x00, 0x1E, 0x00, 0x03, 0x65, 0xCD};
byte npkResponse[11];

bool isValidWaterTempC(float tempC) {
  return tempC != DEVICE_DISCONNECTED_C && tempC >= -55.0 && tempC <= 125.0;
}

float readWaterTempC() {
  waterTempSensor.requestTemperatures();
  return waterTempSensor.getTempCByIndex(0);
}

float phFromRawCalibrated(int phRaw, float waterTempC) {
  // ESP32 ADC is 12-bit (0-4095) with 3.3V reference.
  // We use a voltage divider (10k and 20k) to step down the 5V pH sensor output.
  // Vout = Vin * (20 / (10 + 20)) = Vin * 2/3.
  // So Vin (original voltage) = Vout * 1.5.
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
  
  // Configure ADC resolution and attenuation for ESP32
  analogReadResolution(12);
  analogSetPinAttenuation(PH_PIN, ADC_11db); // Allow reading up to ~3.3V

  // Connect to WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi!");
}

void loop() {
  float waterTemp = readWaterTempC();
  bool waterTempOk = isValidWaterTempC(waterTemp);
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

  // Fallback Serial Output for debugging
  String rawCsv = String(phValue, 2) + "," + String(n) + "," + String(p) + "," + String(k) + "," + String(dhtTemp, 1) + "," + String(humidity, 1);
  Serial.println("Data: " + rawCsv);

  // Send via HTTP POST
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    String jsonPayload = "{\"ph\":" + String(phValue, 2) + 
                         ",\"n\":" + String(n) + 
                         ",\"p\":" + String(p) + 
                         ",\"k\":" + String(k) + 
                         ",\"temp\":" + String(dhtTemp, 1) + 
                         ",\"hum\":" + String(humidity, 1) + 
                         ",\"raw\":\"" + rawCsv + "\"}";
                         
    int httpResponseCode = http.POST(jsonPayload);
    if (httpResponseCode > 0) {
      Serial.print("HTTP Response code: ");
      Serial.println(httpResponseCode);
    } else {
      Serial.print("Error code: ");
      Serial.println(httpResponseCode);
    }
    http.end();
  }

  delay(LOOP_DELAY_MS);
}
