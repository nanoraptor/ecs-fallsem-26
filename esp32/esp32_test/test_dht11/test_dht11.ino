#include <DHT.h>

#define DHT_PIN 18         // GPIO18 on ESP32
#define DHT_TYPE DHT11

DHT dht(DHT_PIN, DHT_TYPE);

void setup() {
  Serial.begin(115200);
  Serial.println("DHT11 Test Started!");
  
  dht.begin();
}

void loop() {
  // Wait a few seconds between measurements.
  delay(2000);

  // Reading temperature or humidity takes about 250 milliseconds!
  // Sensor readings may also be up to 2 seconds 'old' (its a very slow sensor)
  float h = dht.readHumidity();
  // Read temperature as Celsius (the default)
  float t = dht.readTemperature();

  // Check if any reads failed and exit early (to try again).
  if (isnan(h) || isnan(t)) {
    Serial.println("Failed to read from DHT sensor! Please check your wiring.");
    return;
  }

  Serial.print("Humidity: ");
  Serial.print(h);
  Serial.print("%  |  ");
  Serial.print("Temperature: ");
  Serial.print(t);
  Serial.println("°C");
}
