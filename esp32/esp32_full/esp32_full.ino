#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <DallasTemperature.h>
#include <OneWire.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);

// --- WiFi Credentials ---
// Configure with your local 2.4GHz WiFi SSID and password
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// --- Flask Server ---
// Replace with the IP address and port of the machine running app.py
// Example: "http://192.168.1.100:5000/api/esp32_reading"
const char* serverUrl = "http://YOUR_SERVER_IP:5000/api/esp32_reading"; 

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

// pH Calibration Voltages (Calibrated with SDFCL pH 4.0, 7.0, and 9.2 buffers with DS18B20 at ~30.5°C)
const float PH_VOLTAGE_PH7 = 1.114;
const float PH_SLOPE_ACID = 0.1805;    // V/pH for pH < 7 (normalized to 25°C)
const float PH_SLOPE_ALKALINE = 0.1438; // V/pH for pH >= 7 (normalized to 25°C)
const float PH_SLOPE = PH_SLOPE_ACID;

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
  // With 10kΩ series protection resistor (direct ADC connection, no divider):
  float espVoltage = (phRaw * 3.3) / 4095.0;
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
  lcd.print("SoilSage System");
  lcd.setCursor(0, 1);
  lcd.print("Initializing...");
  
  // Configure ADC resolution and attenuation for ESP32
  analogReadResolution(12);
  analogSetPinAttenuation(PH_PIN, ADC_11db); // Allow reading up to ~3.3V

  // Connect to WiFi
  lcd.clear();
  lcd.print("Connecting Wi-Fi");
  
  // Best practice: explicitly set mode and clear previous state
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true);
  delay(100);
  
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi!");
  
  lcd.clear();
  lcd.print("WiFi Connected!");
  lcd.setCursor(0, 1);
  lcd.print(WiFi.localIP());
  delay(2000);
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
  while (Serial2.available()) { Serial2.read(); } // Clear stale bytes
  digitalWrite(RE_DE_PIN, HIGH);
  delay(10);
  Serial2.write(npkRequest, sizeof(npkRequest));
  Serial2.flush();
  digitalWrite(RE_DE_PIN, LOW);

  // Wait up to 300ms for full 11-byte Modbus response
  unsigned long startWait = millis();
  while (Serial2.available() < 11 && (millis() - startWait) < 300) {
    delay(5);
  }

  int n = -1, p = -1, k = -1;
  if (Serial2.available() >= 11) {
    for (int i = 0; i < 11; i++) {
      npkResponse[i] = Serial2.read();
    }
    if (npkResponse[0] == 0x01 && npkResponse[1] == 0x03 && npkResponse[2] == 0x06) {
      n = (npkResponse[3] << 8) | npkResponse[4];
      p = (npkResponse[5] << 8) | npkResponse[6];
      k = (npkResponse[7] << 8) | npkResponse[8];
    }
  }
  while (Serial2.available()) { Serial2.read(); }

  // Fallback Serial Output for debugging
  String rawCsv = String(phValue, 2) + "," + String(n) + "," + String(p) + "," + String(k) + "," + String(dhtTemp, 1) + "," + String(humidity, 1) + "," + String(waterTemp, 1);
  Serial.println("Data: " + rawCsv);
  
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
                         ",\"water_temp\":" + String(waterTemp, 1) + 
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
