#include <HardwareSerial.h>

#define RE_DE_PIN 4
#define RX_PIN 16
#define TX_PIN 17

const byte npkRequest[] = {0x01, 0x03, 0x00, 0x1E, 0x00, 0x03, 0x65, 0xCD};
byte npkResponse[20];

long baudRates[] = {4800, 9600, 19200, 38400};
int baudIndex = 0;

void setup() {
  Serial.begin(115200);
  Serial.println("Starting NPK Auto-Baud Sweep...");
  pinMode(RE_DE_PIN, OUTPUT);
}

void loop() {
  long currentBaud = baudRates[baudIndex];
  Serial.print("\n--- Testing Baud Rate: ");
  Serial.print(currentBaud);
  Serial.println(" ---");
  
  Serial2.begin(currentBaud, SERIAL_8N1, RX_PIN, TX_PIN);
  delay(100);

  // Clear buffer
  while (Serial2.available()) Serial2.read();

  // Transmit
  digitalWrite(RE_DE_PIN, HIGH);
  delay(10);
  Serial2.write(npkRequest, sizeof(npkRequest));
  Serial2.flush();
  digitalWrite(RE_DE_PIN, LOW);
  
  // Wait
  delay(500); 

  int bytesAvailable = Serial2.available();
  
  if (bytesAvailable > 0) {
    Serial.print("Bytes received: ");
    Serial.println(bytesAvailable);
    Serial.print("Raw Hex Data: ");
    for (int i = 0; i < bytesAvailable; i++) {
      byte b = Serial2.read();
      if (b < 0x10) Serial.print("0");
      Serial.print(b, HEX);
      Serial.print(" ");
    }
    Serial.println();
  } else {
    Serial.println("Silence (0 bytes).");
  }

  // Move to next baud rate
  baudIndex++;
  if (baudIndex >= 4) {
    baudIndex = 0;
    Serial.println("\n*** SWEEP COMPLETE. If all returned junk/silence, SWAP YELLOW AND BLUE WIRES NOW! ***\n");
    delay(5000); // Give user time to read
  }

  delay(2000);
}
