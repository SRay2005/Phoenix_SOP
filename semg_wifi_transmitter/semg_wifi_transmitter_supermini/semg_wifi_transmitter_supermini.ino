/*
semg_wifi_transmitter_c3.ino
  ESP32-C3 SuperMini: reads the Patchy signal on GPIO3 and streams it to
  the laptop over WiFi (UDP).

  Arduino IDE settings:
    Board:             ESP32C3 Dev Module
    USB CDC On Boot:   Enabled

  BLUE LED STATUS (works even with no Serial Monitor, e.g. on battery):
    very fast blinking  = connecting to WiFi
    3 slow blinks, pause = could not connect (it keeps retrying)
    slow steady blink (1 per second) = connected and streaming data
*/

#include <WiFi.h>
#include <WiFiUdp.h>

const char *WIFI_SSID = "personal";
const char *WIFI_PASSWORD = "12345678";
IPAddress LAPTOP_IP(172, 20, 10, 5); // laptop's IPv4 address on the hotspot (ipconfig)

const int UDP_PORT = 4210;

const int SEMG_PIN = 3; // Patchy signal (through the 10k/10k divider)
const int LED_PIN = 8;  // SuperMini blue LED, lit when the pin is LOW

const int SAMPLE_RATE_HZ = 1000;
const unsigned long SAMPLE_INTERVAL_US = 1000000UL / SAMPLE_RATE_HZ;

WiFiUDP udp;
unsigned long lastSampleTime = 0;
unsigned long lastReconnect = 0;
uint32_t sampleCounter = 0;
bool ledState = false;

void led(bool on) { digitalWrite(LED_PIN, on ? LOW : HIGH); }

void blinkPattern(int times, int onMs, int offMs) {
  for (int i = 0; i < times; i++) {
    led(true);
    delay(onMs);
    led(false);
    delay(offMs);
  }
}

bool connectWiFi(unsigned long timeoutMs) {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  // Some SuperMini boards have a weak antenna design; lower TX power makes
  // them connect more reliably.
  WiFi.setTxPower(WIFI_POWER_8_5dBm);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < timeoutMs) {
    blinkPattern(1, 50, 50);
    if (Serial)
      Serial.print(".");
  }
  if (Serial)
    Serial.println();
  return WiFi.status() == WL_CONNECTED;
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  led(false);

  // On this board the USB serial port disappears and reappears at every
  // reset. Wait (up to 5 s) for the Serial Monitor so the first messages
  // are not lost.
  unsigned long t0 = millis();
  while (!Serial && millis() - t0 < 5000) {
    delay(10);
  }
  delay(500);

  Serial.println();
  Serial.println("ESP32-C3 sEMG WiFi transmitter");

  analogReadResolution(12);
  analogSetPinAttenuation(SEMG_PIN, ADC_11db); // widest range, about 0 to 2.5 V
  Serial.print("sEMG pin: GPIO ");
  Serial.println(SEMG_PIN);

  // Show nearby networks (confirms the hotspot is visible).
  WiFi.mode(WIFI_STA);
  Serial.println("Scanning WiFi...");
  int n = WiFi.scanNetworks();
  Serial.print("Found ");
  Serial.print(n);
  Serial.println(" networks:");
  for (int i = 0; i < n; i++) {
    Serial.print("  ");
    Serial.print(WiFi.SSID(i));
    Serial.print("  RSSI ");
    Serial.print(WiFi.RSSI(i));
    Serial.print("  ch ");
    Serial.println(WiFi.channel(i));
  }

  Serial.print("Connecting to ");
  Serial.println(WIFI_SSID);

  while (!connectWiFi(20000)) {
    Serial.print("Could not connect. WiFi.status() = ");
    Serial.println(WiFi.status());
    Serial.println(
        "Check: hotspot on, Maximize Compatibility ON, SSID/password correct.");
    Serial.println("Retrying...");
    WiFi.disconnect();
    delay(500);
    blinkPattern(3, 300, 300);
    delay(1000);
  }

  Serial.println("WIFI CONNECTED!");
  Serial.print("ESP32 IP address: ");
  Serial.println(WiFi.localIP());
  Serial.print("Laptop destination IP: ");
  Serial.println(LAPTOP_IP);
  Serial.print("UDP port: ");
  Serial.println(UDP_PORT);
  Serial.println("Starting sEMG transmission...");

  udp.begin(UDP_PORT);
  lastSampleTime = micros();
}

void loop() {
  unsigned long now = micros();

  if (now - lastSampleTime >= SAMPLE_INTERVAL_US) {
    lastSampleTime += SAMPLE_INTERVAL_US;

    int rawValue = analogRead(SEMG_PIN);

    if (WiFi.status() == WL_CONNECTED) {
      char packet[32];
      snprintf(packet, sizeof(packet), "%lu,%d\n", (unsigned long)sampleCounter,
               rawValue);
      udp.beginPacket(LAPTOP_IP, UDP_PORT);
      udp.write((const uint8_t *)packet, strlen(packet));
      udp.endPacket();
    }

    sampleCounter++;

    // Every 500 samples (0.5 s): toggle the LED and print a status line.
    if (sampleCounter % 500 == 0) {
      ledState = !ledState;
      led(ledState);
      if (Serial) {
        Serial.print("Sample ");
        Serial.print(sampleCounter);
        Serial.print(" | ADC = ");
        Serial.println(rawValue);
      }
    }
  }

  // If WiFi drops, try to reconnect every 5 seconds.
  if (WiFi.status() != WL_CONNECTED && millis() - lastReconnect > 5000) {
    lastReconnect = millis();
    WiFi.reconnect();
  }
}
