#define PH_PIN 34 // Must be an input-only pin on ESP32

// Calibration values (Calibrated with SDFCL pH 4.0, 7.0, and 9.2 buffers with DS18B20 at ~30.5°C)
const float PH_VOLTAGE_PH7 = 1.114;
const float PH_SLOPE_ACID = 0.1805;    // V/pH for pH < 7 (normalized to 25°C)
const float PH_SLOPE_ALKALINE = 0.1438; // V/pH for pH >= 7 (normalized to 25°C)
const float PH_SLOPE = PH_SLOPE_ACID;

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

  // 2. Direct connection with 10kΩ series protection resistor (no voltage divider)
  float originalVoltage = espVoltage;

  // 3. Calculate pH using calibrated dual-slope formula (assuming ~25-30°C reference)
  float slope = (originalVoltage > PH_VOLTAGE_PH7) ? PH_SLOPE_ACID : PH_SLOPE_ALKALINE;
  float phValue = 7.0 - ((originalVoltage - PH_VOLTAGE_PH7) / slope);

  // Print diagnostics
  Serial.println("\n--- pH Reading ---");
  Serial.print("Raw ADC Value (0-4095): "); Serial.println(avgRaw);
  Serial.print("ESP32 Pin Voltage   : "); Serial.print(espVoltage, 3); Serial.println(" V (Must stay under 3.3V!)");
  Serial.print("Sensor Output Voltage: "); Serial.print(originalVoltage, 3); Serial.println(" V");
  Serial.print("Calculated pH       : "); Serial.println(phValue, 2);

  delay(2000);
}
