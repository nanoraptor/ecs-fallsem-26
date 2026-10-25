#include <HardwareSerial.h>

// --- Pin Definitions for ESP32 (38-Pin NodeMCU) ---
#define RE_DE_PIN 4  // Connect to MAX485 DE and RE (tied together)
#define RX_PIN 16     // Connect to MAX485 RO
#define TX_PIN 17     // Connect to MAX485 DI

// Fixed 4800 Baud Rate for RS485 Soil NPK Sensor
const long NPK_BAUD_RATE = 4800;

// Modbus RTU Query Frame: Read 3 holding registers starting at 0x001E (N, P, K)
const byte npkRequest[] = {0x01, 0x03, 0x00, 0x1E, 0x00, 0x03, 0x65, 0xCD};
byte npkResponse[32];

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println("\n========================================");
  Serial.println(" SoilSage - Live NPK Sensor Reader");
  Serial.println("========================================");
  Serial.println("ESP32 Serial Monitor: 115200 baud");
  Serial.println("RS485 Sensor Baud   : 4800 baud");
  Serial.println("Reading pins: RX=GPIO16, TX=GPIO17, DE/RE=GPIO4");
  Serial.println("----------------------------------------\n");

  pinMode(RE_DE_PIN, OUTPUT);
  digitalWrite(RE_DE_PIN, LOW); // Start in Receive mode

  // Initialize HardwareSerial2
  Serial2.begin(NPK_BAUD_RATE, SERIAL_8N1, RX_PIN, TX_PIN);
}

void loop() {
  // 1. Clear any stale bytes in UART buffer
  while (Serial2.available()) {
    Serial2.read();
  }

  // 2. Transmit Modbus Query (Switch MAX485 to Transmit mode)
  digitalWrite(RE_DE_PIN, HIGH);
  delay(5);
  Serial2.write(npkRequest, sizeof(npkRequest));
  Serial2.flush(); // Ensure all bytes are physically pushed out
  digitalWrite(RE_DE_PIN, LOW); // Switch immediately back to Receive mode

  // 3. Wait for sensor response (up to 400ms timeout)
  unsigned long startTime = millis();
  while (Serial2.available() < 11 && (millis() - startTime) < 400) {
    delay(10);
  }

  int bytesReceived = Serial2.available();

  if (bytesReceived >= 11) {
    int readLen = (bytesReceived > (int)sizeof(npkResponse)) ? sizeof(npkResponse) : bytesReceived;
    for (int i = 0; i < readLen; i++) {
      npkResponse[i] = Serial2.read();
    }

    // 4. Find the Modbus header (0x01 0x03 0x06) to ignore line-transient glitch bytes (0x00 / 0xFF)
    int headerIndex = -1;
    for (int i = 0; i <= readLen - 9; i++) {
      if (npkResponse[i] == 0x01 && npkResponse[i + 1] == 0x03 && npkResponse[i + 2] == 0x06) {
        headerIndex = i;
        break;
      }
    }

    if (headerIndex != -1) {
      // Decode 16-bit integers
      int nitrogen   = (npkResponse[headerIndex + 3] << 8) | npkResponse[headerIndex + 4];
      int phosphorus = (npkResponse[headerIndex + 5] << 8) | npkResponse[headerIndex + 6];
      int potassium  = (npkResponse[headerIndex + 7] << 8) | npkResponse[headerIndex + 8];

      // Display directly in Serial Monitor
      Serial.println("+--------------------------------------+");
      Serial.println("|          SOIL NPK READINGS           |");
      Serial.println("+--------------------------------------+");
      Serial.print  ("|  Nitrogen   (N) : "); 
      if (nitrogen < 10) Serial.print("  "); else if (nitrogen < 100) Serial.print(" ");
      Serial.print(nitrogen); 
      Serial.println(" mg/kg            |");

      Serial.print  ("|  Phosphorus (P) : "); 
      if (phosphorus < 10) Serial.print("  "); else if (phosphorus < 100) Serial.print(" ");
      Serial.print(phosphorus); 
      Serial.println(" mg/kg            |");

      Serial.print  ("|  Potassium  (K) : "); 
      if (potassium < 10) Serial.print("  "); else if (potassium < 100) Serial.print(" ");
      Serial.print(potassium); 
      Serial.println(" mg/kg            |");
      Serial.println("+--------------------------------------+");

      // Optional compact CSV output
      Serial.print("CSV Format -> N:");
      Serial.print(nitrogen);
      Serial.print(", P:");
      Serial.print(phosphorus);
      Serial.print(", K:");
      Serial.println(potassium);
      Serial.println();
    } else {
      Serial.print("[Warning] Received ");
      Serial.print(bytesReceived);
      Serial.println(" bytes, but Modbus header 01 03 06 was not found.");
    }
  } else {
    Serial.println("[Error] Sensor timeout - No response received.");
    Serial.println("        -> Check 12V power supply to sensor.");
    Serial.println("        -> Check that sensor GND is connected to ESP32 GND.");
    Serial.println("        -> Ensure soil is moist and covering the prongs.");
    Serial.println();
  }

  // Clear any residual bytes before next loop
  while (Serial2.available()) {
    Serial2.read();
  }

  delay(2000); // Poll every 2 seconds
}
