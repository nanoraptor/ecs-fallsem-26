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
  
  // With 10kΩ series protection resistor (direct connection, no divider)
  float espVoltage = (avgRaw * 3.3) / 4095.0;
  float originalVoltage = espVoltage;

  // Live pH calculation with newly calibrated dual-slope parameters
  const float tempFactor = (tempC != DEVICE_DISCONNECTED_C) ? ((tempC + 273.15) / 298.15) : 1.0;
  const float slope = (originalVoltage > 1.114 ? 0.1805 : 0.1438) * tempFactor;
  float livePh = 7.0 - ((originalVoltage - 1.114) / slope);

  // 3. Print Results
  Serial.println("\n=================================");
  if (tempC == DEVICE_DISCONNECTED_C) {
    Serial.println("TEMP : ERROR (Check DS18B20 wiring!)");
  } else {
    Serial.print("TEMP : "); Serial.print(tempC, 1); Serial.println(" °C");
  }
  Serial.print("VOLTS: "); Serial.print(originalVoltage, 3); Serial.println(" V");
  Serial.print("CALCULATED pH: "); Serial.println(livePh, 2);
  Serial.println("=================================");

  delay(3000);
}
