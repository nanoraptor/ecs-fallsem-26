#include <Wire.h>

void setup() {
  Serial.begin(115200);
  while (!Serial);
  Serial.println("\n--- I2C Scanner Starting ---");
  Wire.begin(21, 22); // SDA = GPIO 21, SCL = GPIO 22
}

void loop() {
  byte error, address;
  int nDevices = 0;

  Serial.println("Scanning I2C bus...");

  for (address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();

    if (error == 0) {
      Serial.print("  [SUCCESS] I2C device found at address 0x");
      if (address < 16) Serial.print("0");
      Serial.print(address, HEX);
      Serial.println(" !");
      nDevices++;
    } else if (error == 4) {
      Serial.print("  [ERROR] Unknown error at address 0x");
      if (address < 16) Serial.print("0");
      Serial.println(address, HEX);
    }
  }

  if (nDevices == 0) {
    Serial.println("  [FAIL] No I2C devices found. Check wiring (VCC to VIN, GND to GND, SDA to D21, SCL to D22).\n");
  } else {
    Serial.printf("Done. Found %d device(s).\n\n", nDevices);
  }

  delay(3000);
}
