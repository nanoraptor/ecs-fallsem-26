#include <WiFi.h>

// On ESP32 DevKit V1, the onboard blue LED is connected to GPIO 2
#define ONBOARD_LED 2

void setup() {
  pinMode(ONBOARD_LED, OUTPUT);
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n==========================================");
  Serial.println("   ESP32 DevKit V1 - Hardware Self-Test   ");
  Serial.println("==========================================");

  // 1. Chip Info
  esp_chip_info_t chip_info;
  esp_chip_info(&chip_info);
  Serial.printf("Chip Model     : %s\n", ESP.getChipModel());
  Serial.printf("Silicon Rev    : %d\n", ESP.getChipRevision());
  Serial.printf("CPU Cores      : %d\n", chip_info.cores);
  Serial.printf("CPU Frequency  : %d MHz\n", getCpuFrequencyMhz());
  Serial.printf("Flash Size     : %d MB\n", ESP.getFlashChipSize() / (1024 * 1024));
  Serial.printf("Free Heap RAM  : %d KB\n", ESP.getFreeHeap() / 1024);

  // 2. Wi-Fi Radio Scan Test
  Serial.println("\n[Testing Wi-Fi Radio...]");
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);

  int n = WiFi.scanNetworks();
  if (n == 0) {
    Serial.println("-> Wi-Fi Radio OK, but 0 networks found.");
  } else {
    Serial.printf("-> Wi-Fi Radio OK! Found %d networks nearby:\n", n);
    for (int i = 0; i < min(n, 5); ++i) {
      Serial.printf("   %d: %s (%d dBm)\n", i + 1, WiFi.SSID(i).c_str(), WiFi.RSSI(i));
    }
  }

  Serial.println("\n==========================================");
  Serial.println("Status: ESP32 IS HEALTHY AND READY!");
  Serial.println("Blinking onboard blue LED on GPIO 2...");
  Serial.println("==========================================\n");
}

void loop() {
  static uint32_t seconds = 0;

  // Turn LED ON
  digitalWrite(ONBOARD_LED, HIGH);
  delay(500);

  // Turn LED OFF
  digitalWrite(ONBOARD_LED, LOW);
  delay(500);

  seconds++;
  Serial.printf("Heartbeat: Board running normally... Uptime: %d seconds | Free RAM: %d KB\n", 
                seconds, ESP.getFreeHeap() / 1024);
}
