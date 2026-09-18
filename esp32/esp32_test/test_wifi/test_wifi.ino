#include "WiFi.h"

void setup() {
  Serial.begin(115200);
  
  // Set WiFi to station mode and disconnect from an AP if it was previously connected
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);

  Serial.println("\nSoilSage - WiFi Scanner Tool");
  Serial.println("Scanning for nearby 2.4GHz networks...");
}

void loop() {
  int n = WiFi.scanNetworks();
  
  Serial.println("Scan done.");
  if (n == 0) {
    Serial.println("No networks found.");
  } else {
    Serial.print(n);
    Serial.println(" networks found:");
    for (int i = 0; i < n; ++i) {
      // Print SSID and RSSI for each network found
      Serial.print(i + 1);
      Serial.print(": ");
      Serial.print(WiFi.SSID(i));
      Serial.print(" (");
      Serial.print(WiFi.RSSI(i));
      Serial.print(" dBm) ");
      Serial.println((WiFi.encryptionType(i) == WIFI_AUTH_OPEN) ? "[OPEN]" : "[SECURED]");
      delay(10);
    }
  }
  Serial.println("-----------------------------------");
  
  // Wait a bit before scanning again
  delay(5000);
}
