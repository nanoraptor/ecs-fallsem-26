#define PH_PIN 34 // Must be an input-only pin on ESP32

// Calibration values (from a 5V perspective)
const float PH_VOLTAGE_PH7 = 1.251;
const float PH_VOLTAGE_PH4 = 1.769;
const float PH_SLOPE = (PH_VOLTAGE_PH4 - PH_VOLTAGE_PH7) / 3.0;

void setup() {
  Serial.begin(115200);
  Serial.println("pH Sensor Diagnostic Test Started!");
  
  // Configure ESP32 ADC (0-4095 range, up to ~3.3V)
  analogReadResolution(12);
  analogSetPinAttenuation(PH_PIN, ADC_11db);
}

void loop() {
  // Take 20 quick readings and average them to reduce noise
  long totalRaw = 0;
  for (int i = 0; i < 20; i++) {
    totalRaw += analogRead(PH_PIN);
    delay(10);
  }
  int avgRaw = totalRaw / 20;

  // 1. Convert the raw ESP32 reading (0-4095) back to the voltage the ESP32 is seeing (0-3.3V)
  float espVoltage = (avgRaw * 3.3) / 4095.0;

  // 2. Reverse the Voltage Divider math (Vout = Vin * 2/3, so Vin = Vout * 1.5)
  // This calculates the original voltage coming out of the sensor module before the resistors.
  float originalVoltage = espVoltage * 1.5;

  // 3. Calculate pH using the standard slope formula (assuming 25°C water)
  float phValue = 7.0 - ((originalVoltage - PH_VOLTAGE_PH7) / PH_SLOPE);

  // Print diagnostics
  Serial.println("\n--- pH Reading ---");
  Serial.print("Raw ADC Value (0-4095): "); Serial.println(avgRaw);
  Serial.print("ESP32 Pin Voltage   : "); Serial.print(espVoltage, 3); Serial.println(" V (Must stay under 3.3V!)");
  Serial.print("Sensor Output Voltage: "); Serial.print(originalVoltage, 3); Serial.println(" V");
  Serial.print("Calculated pH       : "); Serial.println(phValue, 2);

  delay(2000);
}
