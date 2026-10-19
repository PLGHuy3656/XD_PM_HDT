#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "DHT.h"

// ============================================================================
// SWIFTLETCARE - IOT SUBSYSTEM: ENVIRONMENTAL CONTROLLER NODE
// Hardware: ESP32 DevKit V4 / NodeMCU-32S
// Protocol: MQTT (Telemetry, Command, Ack, LWT)
// ============================================================================

// --- 1. HARDWARE PIN DEFINITIONS ---
#define DHTPIN              15
#define DHTTYPE             DHT22
#define SOUND_ADC_PIN       34

#define PIN_MISTING         25  // LED Blue: Ultrasonic Humidifier / Misting Pump
#define PIN_FAN             26  // LED Green: Ventilation / Exhaust Fan
#define PIN_HEATER          27  // LED Red: Heating Lamp / Ceramic Heater
#define PIN_ALARM           33  // LED Orange: Siren / Predator Strobe Alarm

// --- 2. NETWORK & MQTT CONFIGURATION ---
const char* WIFI_SSID       = "Wokwi-GUEST";
const char* WIFI_PASSWORD   = "";

const char* MQTT_BROKER     = "broker.emqx.io";
const int   MQTT_PORT       = 1883;
const char* DEVICE_ID       = "swc-node-01";

// Topic Taxonomy
const char* TOPIC_TELEMETRY = "swiftlet/telemetry/swc-node-01";
const char* TOPIC_COMMAND   = "swiftlet/command/swc-node-01";
const char* TOPIC_ACK       = "swiftlet/ack/swc-node-01";
const char* TOPIC_STATUS    = "swiftlet/status/swc-node-01";

// --- 3. OBJECTS & CONTROL SETPOINTS ---
DHT dht(DHTPIN, DHTTYPE);
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// Optimal Swiftlet Farming Setpoints (Domain Knowledge)
float targetTemp     = 29.0; // Optimal: 28.5 - 29.5 °C
float tempDeadband   = 1.5;  // Fan triggers ON when temp > 30.5 °C
float targetHum      = 80.0; // Optimal: 75.0 - 85.0 %
float humDeadband    = 3.0;  // Misting triggers ON when hum < 77.0 %
bool  isAutoMode     = true; // Default: Autonomous closed-loop control

unsigned long lastTelemetryMillis = 0;
const unsigned long TELEMETRY_INTERVAL_MS = 5000;

// --- 4. LOCAL AUTOMATIC CONTROL ENGINE (OFFLINE RESILIENCY) ---
void executeLocalAutomation(float temp, float hum) {
  if (!isAutoMode) return; // Do not override if operator set to MANUAL mode

  // 1. Humidity Regulation (Ultrasonic Misting Pump)
  if (hum < (targetHum - humDeadband)) {
    digitalWrite(PIN_MISTING, HIGH);
  } else if (hum >= targetHum) {
    digitalWrite(PIN_MISTING, LOW);
  }

  // 2. Temperature Regulation (Exhaust Ventilation Fan)
  if (temp > (targetTemp + tempDeadband)) {
    digitalWrite(PIN_FAN, HIGH);
  } else if (temp <= targetTemp) {
    digitalWrite(PIN_FAN, LOW);
  }

  // 3. Low-Temperature Protection (Heater)
  if (temp < 26.0) {
    digitalWrite(PIN_HEATER, HIGH);
  } else if (temp >= 27.5) {
    digitalWrite(PIN_HEATER, LOW);
  }
}

// --- 5. DOWNLINK COMMAND PARSER & ACKNOWLEDGEMENT ---
void handleMqttMessage(char* topic, byte* payload, unsigned int length) {
  Serial.print("\n[MQTT INGRESS] Received on: ");
  Serial.println(topic);

  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    Serial.println("[ERROR] Failed to parse JSON command payload!");
    return;
  }

  const char* cmdId = doc["commandId"] | "unknown-cmd";
  const char* action = doc["action"];

  // Action 1: Manual Override of Actuator Relays
  if (strcmp(action, "SET_RELAY") == 0) {
    isAutoMode = false;
    const char* target = doc["target"];
    int state = doc["state"];
    int pinVal = (state == 1) ? HIGH : LOW;

    if (strcmp(target, "misting") == 0) digitalWrite(PIN_MISTING, pinVal);
    else if (strcmp(target, "fan") == 0) digitalWrite(PIN_FAN, pinVal);
    else if (strcmp(target, "heater") == 0) digitalWrite(PIN_HEATER, pinVal);
    else if (strcmp(target, "alarm") == 0) digitalWrite(PIN_ALARM, pinVal);

    // Send ACK back to Backend
    StaticJsonDocument<256> ack;
    ack["commandId"] = cmdId;
    ack["nodeId"] = DEVICE_ID;
    ack["status"] = "SUCCESS";
    ack["mode"] = "MANUAL";
    ack["target"] = target;
    ack["state"] = state;

    char ackBuf[256];
    serializeJson(ack, ackBuf);
    mqttClient.publish(TOPIC_ACK, ackBuf);
    Serial.println("[MQTT ACK] Dispatched command acknowledgement.");
  }
  // Action 2: Update Environmental Setpoints & Restore AUTO Mode
  else if (strcmp(action, "UPDATE_THRESHOLDS") == 0) {
    if (doc.containsKey("targetTemp")) targetTemp = doc["targetTemp"];
    if (doc.containsKey("targetHum")) targetHum = doc["targetHum"];
    if (doc.containsKey("isAutoMode")) isAutoMode = doc["isAutoMode"];

    StaticJsonDocument<256> ack;
    ack["commandId"] = cmdId;
    ack["nodeId"] = DEVICE_ID;
    ack["status"] = "SUCCESS";
    ack["mode"] = isAutoMode ? "AUTO" : "MANUAL";
    ack["targetTemp"] = targetTemp;
    ack["targetHum"] = targetHum;

    char ackBuf[256];
    serializeJson(ack, ackBuf);
    mqttClient.publish(TOPIC_ACK, ackBuf);
    Serial.println("[MQTT ACK] Setpoints updated and acknowledged.");
  }
}

// --- 6. NETWORK CONNECTION & RECOVERY ---
void ensureMqttConnected() {
  while (!mqttClient.connected()) {
    Serial.print("[MQTT] Connecting to Broker: ");
    Serial.println(MQTT_BROKER);

    // Connect with Last Will and Testament (LWT)
    if (mqttClient.connect(DEVICE_ID, TOPIC_STATUS, 1, true, "{\"status\":\"offline\"}")) {
      Serial.println("[MQTT] Connection established!");
      mqttClient.publish(TOPIC_STATUS, "{\"status\":\"online\"}", true);
      mqttClient.subscribe(TOPIC_COMMAND);
      Serial.print("[MQTT] Subscribed to topic: ");
      Serial.println(TOPIC_COMMAND);
    } else {
      Serial.print("[MQTT FAILED] rc=");
      Serial.print(mqttClient.state());
      Serial.println(". Retrying in 3 seconds...");
      delay(3000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n=============================================");
  Serial.println("  SWIFTLETCARE - IOT EDGE CONTROLLER BOOTING  ");
  Serial.println("=============================================");

  // Initialize Actuator Pins
  pinMode(PIN_MISTING, OUTPUT);
  pinMode(PIN_FAN, OUTPUT);
  pinMode(PIN_HEATER, OUTPUT);
  pinMode(PIN_ALARM, OUTPUT);
  digitalWrite(PIN_MISTING, LOW);
  digitalWrite(PIN_FAN, LOW);
  digitalWrite(PIN_HEATER, LOW);
  digitalWrite(PIN_ALARM, LOW);

  dht.begin();

  // Connect Wi-Fi
  Serial.print("[WIFI] Connecting to: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n[WIFI] Connected! Assigned IP: " + WiFi.localIP().toString());

  // Configure MQTT
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(handleMqttMessage);
}

void loop() {
  if (!mqttClient.connected()) {
    ensureMqttConnected();
  }
  mqttClient.loop();

  // Periodic Telemetry Publishing Loop
  if (millis() - lastTelemetryMillis >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryMillis = millis();

    // 1. Acquire Sensor Readings
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    int soundRaw = analogRead(SOUND_ADC_PIN);
    bool soundDetected = (soundRaw > 1000);

    if (isnan(t) || isnan(h)) {
      Serial.println("[ERROR] Failed to read from DHT sensor!");
      return;
    }

    // 2. Execute Local Closed-Loop Control Logic
    executeLocalAutomation(t, h);

    // 3. Serialize Telemetry JSON
    StaticJsonDocument<512> doc;
    doc["nodeId"] = DEVICE_ID;
    doc["timestamp"] = millis() / 1000;

    JsonObject metrics = doc.createNestedObject("metrics");
    metrics["temp"] = t;
    metrics["humidity"] = h;
    metrics["soundRaw"] = soundRaw;
    metrics["soundOk"] = soundDetected;

    JsonObject relays = doc.createNestedObject("actuators");
    relays["misting"] = (digitalRead(PIN_MISTING) == HIGH);
    relays["fan"] = (digitalRead(PIN_FAN) == HIGH);
    relays["heater"] = (digitalRead(PIN_HEATER) == HIGH);
    relays["alarm"] = (digitalRead(PIN_ALARM) == HIGH);

    doc["mode"] = isAutoMode ? "AUTO" : "MANUAL";

    char buffer[512];
    serializeJson(doc, buffer);

    // 4. Publish Uplink Telemetry
    mqttClient.publish(TOPIC_TELEMETRY, buffer);
    Serial.print("[TELEMETRY PUBLISHED] ");
    Serial.println(buffer);
  }
}
