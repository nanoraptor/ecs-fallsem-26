#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// Set the LCD address to 0x27 for a 16 chars and 2 line display
// If the screen stays blank, try changing 0x27 to 0x3F!
LiquidCrystal_I2C lcd(0x27, 16, 2);

void setup() {
  Serial.begin(115200);
  Serial.println("Initializing LCD Test...");

  // Initialize the LCD
  lcd.init();
  
  // Turn on the backlight (if not already on)
  lcd.backlight();

  // Print a message to the LCD
  lcd.setCursor(0, 0); // (Column 0, Row 0)
  lcd.print("LCD Test OK!");
  
  lcd.setCursor(0, 1); // (Column 0, Row 1)
  lcd.print("SoilSage Ready");
}

void loop() {
  // Blinking backlight effect to confirm it's not frozen
  static bool showAltScreen = false;
  
  lcd.clear();
  if (!showAltScreen) {
    lcd.setCursor(0, 0);
    lcd.print("LCD Test OK!");
    lcd.setCursor(0, 1);
    lcd.print("SoilSage Ready");
  } else {
    lcd.setCursor(0, 0);
    lcd.print("Sol Temp: 23.4C");
    lcd.setCursor(0, 1);
    lcd.print("Humidity: 55.0%");
  }
  showAltScreen = !showAltScreen;
  
  delay(3000);
  lcd.noBacklight(); // Turn off backlight
  delay(500);
  lcd.backlight();   // Turn on backlight
}
