#include <OneWire.h>
#include <DallasTemperature.h>

// --- Pin Definitions ---
#define WATER_TEMP_PIN 5   // DS18B20 Data pin
#define PH_PIN 34          // pH Sensor Analog pin

OneWire oneWire(WATER_TEMP_PIN);
DallasTemperature waterTempSensor(&oneWire);

void setup() {
  Serial.begin(115200);
  Serial.println("--- pH & Temperature Calibration Tool Started ---");
  
  // Initialize DS18B20
  waterTempSensor.begin();

  // Configure ESP32 ADC (0-4095 range, up to ~3.3V)
  analogReadResolution(12);
  analogSetPinAttenuation(PH_PIN, ADC_11db);
}

void loop() {
  // 1. Read Water Temperature
  waterTempSensor.requestTemperatures();
  float tempC = waterTempSensor.getTempCByIndex(0);
  
  // 2. Read pH Voltage (Average of 50 samples for stability)
  long totalRaw = 0;
  for (int i = 0; i < 50; i++) {
    totalRaw += analogRead(PH_PIN);
    delay(10);
  }
  int avgRaw = totalRaw / 50;
  
  // Reverse the 10k/20k Voltage Divider math
  float espVoltage = (avgRaw * 3.3) / 4095.0;
  float originalVoltage = espVoltage * 1.5;

  // 3. Print Results
  Serial.println("\n=================================");
  if (tempC == DEVICE_DISCONNECTED_C) {
    Serial.println("TEMP : ERROR (Check DS18B20 wiring!)");
  } else {
    Serial.print("TEMP : "); Serial.print(tempC, 1); Serial.println(" °C");
  }
  Serial.print("VOLTS: "); Serial.print(originalVoltage, 3); Serial.println(" V");
  Serial.println("=================================");

  delay(3000);
}
