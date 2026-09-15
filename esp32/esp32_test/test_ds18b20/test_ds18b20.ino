#include <OneWire.h>
#include <DallasTemperature.h>

// GPIO5 on ESP32
#define WATER_TEMP_PIN 5

OneWire oneWire(WATER_TEMP_PIN);
DallasTemperature waterTempSensor(&oneWire);

void setup() {
  Serial.begin(115200);
  Serial.println("DS18B20 Water Temperature Test Started!");
  
  waterTempSensor.begin();
}

void loop() {
  Serial.print("Requesting temperatures...");
  waterTempSensor.requestTemperatures(); // Send the command to get temperatures
  Serial.println("DONE");
  
  float tempC = waterTempSensor.getTempCByIndex(0);
  
  // Check if reading was successful
  if (tempC != DEVICE_DISCONNECTED_C) {
    Serial.print("Temperature is: ");
    Serial.print(tempC);
    Serial.println(" °C");
  } else {
    Serial.println("Error: Could not read temperature data. Check wiring and 4.7k pull-up resistor!");
  }
  
  delay(2000);
}
