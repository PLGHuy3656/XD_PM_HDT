#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include "DHT.h"

// ============================================================================
// SWIFTLETCARE - IOT SUBSYSTEM: INDUSTRIAL EDGE CONTROLLER
// Microcontroller: ESP32-WROOM-32
// Tasks: Sensors Acquisition, Telemetry, Local Hysteresis Control, Manual Override & Ack
// ============================================================================

// --- 1. HARDWARE PIN CONFIGURATION ---
#define DHTPIN              15
#define DHTTYPE             DHT22
#define SOUND_ADC_PIN       34   // ADC1_CH6 (Safe with Wi-Fi)

#define PIN_MISTING         25   // Relay 1: Ultrasonic Humidifier / Misting Pump
#define PIN_FAN             26   // Relay 2: Exhaust Ventilation Fan
#define PIN_HEATER          27   // Relay 3: Ceramic Heater Lamp
#define PIN_ALARM           33   // Relay 4: Siren / Strobe Alert

#define RELAY_ACTIVE        HIGH
#define RELAY_INACTIVE      LOW

// --- 2. NETWORK & MQTT CONFIGURATION ---
const char* WIFI_SSID       = "Wokwi-GUEST";
const char* WIFI_PASSWORD   = "";

const char* MQTT_BROKER     = "broker.emqx.io";
const int   MQTT_PORT       = 1883;
const char* DEVICE_ID       = "swc-node-01";

// MQTT Topics Taxonomy
const char* TOPIC_TELEMETRY = "swiftlet/telemetry/swc-node-01";
const char* TOPIC_COMMAND   = "swiftlet/command/swc-node-01";
const char* TOPIC_ACK       = "swiftlet/ack/swc-node-01";
const char* TOPIC_STATUS    = "swiftlet/status/swc-node-01";

// --- 3. OBJECTS & NON-VOLATILE MEMORY (NVS) ---
DHT dht(DHTPIN, DHTTYPE);
WiFiClient espClient;
PubSubClient mqttClient(espClient);
Preferences prefs;

// Control Thresholds & State Management
float targetTemp     = 29.0; // Optimal Swiftlet Nesting Temp: 28.5 - 29.5 °C
float tempDeadband   = 1.5;  // Fan triggers ON when temp > 30.5 °C
float targetHum      = 80.0; // Optimal Swiftlet Nesting Hum: 75.0 - 85.0 %
float humDeadband    = 3.0;  // Misting triggers ON when hum < 77.0 %
bool  isAutoMode     = true; // Default: Autonomous closed-loop control

// Timing Intervals
unsigned long lastTelemetryMillis = 0;
const unsigned long TELEMETRY_INTERVAL_MS = 5000;
unsigned long lastReconnectAttempt = 0;

// Struct for filtered sensor readings
struct SensorReadings {
  float temp;
  float hum;
  int   soundRaw;
  bool  soundOk;
  bool  tempValid;
  bool  humValid;
} currentSensors;

// --- 4. TASK 1: SENSOR ACQUISITION & OUT-OF-RANGE FILTERING ---
void readSensors() {
  float rawT = dht.readTemperature();
  float rawH = dht.readHumidity();
  int rawSound = analogRead(SOUND_ADC_PIN);

  // Validation: Check NaN and physical operational boundaries
  bool tValid = (!isnan(rawT) && rawT >= 10.0 && rawT <= 55.0);
  bool hValid = (!isnan(rawH) && rawH >= 20.0 && rawH <= 99.9);

  if (tValid) {
    currentSensors.temp = rawT;
    currentSensors.tempValid = true;
  } else {
    currentSensors.tempValid = false;
    Serial.println("[WARN] Invalid temperature reading detected!");
  }

  if (hValid) {
    currentSensors.hum = rawH;
    currentSensors.humValid = true;
  } else {
    currentSensors.humValid = false;
    Serial.println("[WARN] Invalid humidity reading detected!");
  }

  currentSensors.soundRaw = rawSound;
  currentSensors.soundOk = (rawSound > 1000); // Threshold indicating nesting audio track is active
}

// --- 5. TASK 3: LOCAL AUTOMATIC CONTROL ENGINE (OFFLINE RESILIENCY) ---
void executeLocalAutomation() {
  if (!isAutoMode) return; // Do not alter states when in MANUAL override mode

  // If sensors fail, enter safe fallback: Turn off actuators to prevent flooding/overheating
  if (!currentSensors.tempValid || !currentSensors.humValid) {
    digitalWrite(PIN_MISTING, RELAY_INACTIVE);
    digitalWrite(PIN_HEATER, RELAY_INACTIVE);
    return;
  }

  // 1. Humidity Closed-Loop Control (Ultrasonic Misting Pump)
  if (currentSensors.hum < (targetHum - humDeadband)) {
    digitalWrite(PIN_MISTING, RELAY_ACTIVE);
  } else if (currentSensors.hum >= targetHum) {
    digitalWrite(PIN_MISTING, RELAY_INACTIVE);
  }

  // 2. Temperature Closed-Loop Control (Exhaust Ventilation Fan)
  if (currentSensors.temp > (targetTemp + tempDeadband)) {
    digitalWrite(PIN_FAN, RELAY_ACTIVE);
  } else if (currentSensors.temp <= targetTemp) {
    digitalWrite(PIN_FAN, RELAY_INACTIVE);
  }

  // 3. Low-Temperature Protection (Heater)
  if (currentSensors.temp < 26.0) {
    digitalWrite(PIN_HEATER, RELAY_ACTIVE);
  } else if (currentSensors.temp >= 27.5) {
    digitalWrite(PIN_HEATER, RELAY_INACTIVE);
  }
}

// --- 6. TASK 4: MANUAL CONTROL, VALIDATION & COMMAND ACKNOWLEDGEMENT ---
void sendAck(const char* cmdId, const char* status, const char* errorCode, const char* message) {
  StaticJsonDocument<300> ack;
  ack["commandId"] = cmdId;
  ack["nodeId"] = DEVICE_ID;
  ack["status"] = status; // "SUCCESS" or "FAILED"
  ack["mode"] = isAutoMode ? "AUTO" : "MANUAL";
  if (errorCode != NULL) ack["errorCode"] = errorCode;
  if (message != NULL) ack["message"] = message;
  ack["timestamp"] = millis() / 1000;

  char ackBuf[300];
  serializeJson(ack, ackBuf);
  mqttClient.publish(TOPIC_ACK, ackBuf);
  Serial.print("[MQTT ACK] Dispatched: ");
  Serial.println(ackBuf);
}

void handleMqttMessage(char* topic, byte* payload, unsigned int length) {
  Serial.print("\n[MQTT INGRESS] Topic: ");
  Serial.println(topic);

  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    sendAck("unknown", "FAILED", "MALFORMED_JSON", "Payload is not valid JSON");
    return;
  }

  const char* cmdId = doc["commandId"] | "unassigned-id";
  const char* action = doc["action"];

  if (!action) {
    sendAck(cmdId, "FAILED", "MISSING_ACTION", "Field 'action' is required");
    return;
  }

  // Action A: Manual Override of Actuators
  if (strcmp(action, "SET_RELAY") == 0) {
    const char* target = doc["target"];
    if (!target) {
      sendAck(cmdId, "FAILED", "MISSING_TARGET", "Target actuator required");
      return;
    }

    if (!doc.containsKey("state") || (doc["state"] != 0 && doc["state"] != 1)) {
      sendAck(cmdId, "FAILED", "INVALID_STATE", "State must be 0 (OFF) or 1 (ON)");
      return;
    }

    int state = doc["state"];
    int pinVal = (state == 1) ? RELAY_ACTIVE : RELAY_INACTIVE;
    bool targetFound = true;

    if (strcmp(target, "misting") == 0) digitalWrite(PIN_MISTING, pinVal);
    else if (strcmp(target, "fan") == 0) digitalWrite(PIN_FAN, pinVal);
    else if (strcmp(target, "heater") == 0) digitalWrite(PIN_HEATER, pinVal);
    else if (strcmp(target, "alarm") == 0) digitalWrite(PIN_ALARM, pinVal);
    else targetFound = false;

    if (!targetFound) {
      sendAck(cmdId, "FAILED", "INVALID_TARGET", "Unknown target actuator specified");
      return;
    }

    // Switch system to MANUAL mode upon direct override
    isAutoMode = false;
    sendAck(cmdId, "SUCCESS", NULL, "Actuator switched successfully; mode changed to MANUAL");
  }
  // Action B: Update Environmental Setpoints & Restore AUTO Mode
  else if (strcmp(action, "UPDATE_THRESHOLDS") == 0) {
    if (doc.containsKey("targetTemp")) targetTemp = doc["targetTemp"];
    if (doc.containsKey("targetHum")) targetHum = doc["targetHum"];
    if (doc.containsKey("isAutoMode")) isAutoMode = doc["isAutoMode"];

    // Persist configuration to Non-Volatile Flash Memory (NVS)
    prefs.begin("swc_cfg", false);
    prefs.putFloat("temp", targetTemp);
    prefs.putFloat("hum", targetHum);
    prefs.putBool("auto", isAutoMode);
    prefs.end();

    sendAck(cmdId, "SUCCESS", NULL, "Thresholds persisted to NVS; mode updated");
  }
  else {
    sendAck(cmdId, "FAILED", "UNKNOWN_ACTION", "Action not supported");
  }
}

// --- 7. TASK 2: MQTT TELEMETRY PIPELINE & RECONNECTION ---
void ensureMqttConnected() {
  if (mqttClient.connected()) return;

  unsigned long now = millis();
  if (now - lastReconnectAttempt > 3000) {
    lastReconnectAttempt = now;
    Serial.print("[MQTT] Attempting connection to Broker: ");
    Serial.println(MQTT_BROKER);

    // Register Last Will and Testament (LWT)
    if (mqttClient.connect(DEVICE_ID, TOPIC_STATUS, 1, true, "{\"status\":\"offline\"}")) {
      Serial.println("[MQTT] Connected successfully!");
      mqttClient.publish(TOPIC_STATUS, "{\"status\":\"online\"}", true);
      mqttClient.subscribe(TOPIC_COMMAND);
      Serial.print("[MQTT] Subscribed to command topic: ");
      Serial.println(TOPIC_COMMAND);
    } else {
      Serial.print("[MQTT ERROR] rc=");
      Serial.println(mqttClient.state());
    }
  }
}

void publishTelemetry() {
  StaticJsonDocument<512> doc;
  doc["nodeId"] = DEVICE_ID;
  doc["timestamp"] = millis() / 1000;

  JsonObject metrics = doc.createNestedObject("metrics");
  metrics["temp"] = currentSensors.temp;
  metrics["humidity"] = currentSensors.hum;
  metrics["soundRaw"] = currentSensors.soundRaw;
  metrics["soundOk"] = currentSensors.soundOk;
  metrics["tempValid"] = currentSensors.tempValid;
  metrics["humValid"] = currentSensors.humValid;

  JsonObject relays = doc.createNestedObject("actuators");
  relays["misting"] = (digitalRead(PIN_MISTING) == RELAY_ACTIVE);
  relays["fan"] = (digitalRead(PIN_FAN) == RELAY_ACTIVE);
  relays["heater"] = (digitalRead(PIN_HEATER) == RELAY_ACTIVE);
  relays["alarm"] = (digitalRead(PIN_ALARM) == RELAY_ACTIVE);

  JsonObject state = doc.createNestedObject("state");
  state["mode"] = isAutoMode ? "AUTO" : "MANUAL";
  state["wifiRssi"] = WiFi.RSSI();
  state["freeHeap"] = ESP.getFreeHeap();

  char buffer[512];
  serializeJson(doc, buffer);
  mqttClient.publish(TOPIC_TELEMETRY, buffer);
  Serial.print("[TELEMETRY PUBLISHED] ");
  Serial.println(buffer);
}

// --- 8. INITIALIZATION & MAIN EXECUTION LOOP ---
void setup() {
  Serial.begin(115200);
  Serial.println("\n=============================================");
  Serial.println("  SWIFTLETCARE - INDUSTRIAL CONTROLLER BOOT  ");
  Serial.println("=============================================");

  // Initialize Actuator GPIOs to safe initial state
  pinMode(PIN_MISTING, OUTPUT);
  pinMode(PIN_FAN, OUTPUT);
  pinMode(PIN_HEATER, OUTPUT);
  pinMode(PIN_ALARM, OUTPUT);
  digitalWrite(PIN_MISTING, RELAY_INACTIVE);
  digitalWrite(PIN_FAN, RELAY_INACTIVE);
  digitalWrite(PIN_HEATER, RELAY_INACTIVE);
  digitalWrite(PIN_ALARM, RELAY_INACTIVE);

  dht.begin();

  // Load Persisted Thresholds from Flash NVS
  prefs.begin("swc_cfg", true);
  targetTemp = prefs.getFloat("temp", 29.0);
  targetHum  = prefs.getFloat("hum", 80.0);
  isAutoMode = prefs.getBool("auto", true);
  prefs.end();

  Serial.printf("[NVS LOADED] TargetTemp: %.1f | TargetHum: %.1f | Mode: %s\n",
                targetTemp, targetHum, isAutoMode ? "AUTO" : "MANUAL");

  // Initialize Wi-Fi
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[WIFI] Connecting to: ");
  Serial.println(WIFI_SSID);

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(handleMqttMessage);
}

void loop() {
  // Maintain Network Connection (Non-blocking)
  if (WiFi.status() == WL_CONNECTED) {
    ensureMqttConnected();
    mqttClient.loop();
  }

  // Periodic Sensor Read & Control Execution (Every 2 seconds)
  static unsigned long lastSenseMillis = 0;
  if (millis() - lastSenseMillis >= 2000) {
    lastSenseMillis = millis();
    readSensors();
    executeLocalAutomation(); // Runs completely independent of Wi-Fi / MQTT
  }

  // Periodic Telemetry Publishing (Every 5 seconds)
  if (millis() - lastTelemetryMillis >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryMillis = millis();
    if (mqttClient.connected()) {
      publishTelemetry();
    }
  }
}
