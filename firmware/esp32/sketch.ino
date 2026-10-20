#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include "DHT.h"

// ============================================================================
// SWIFTLETCARE - INDUSTRIAL IOT EDGE CONTROLLER SKELETON (ESP32)
// Architecture: FreeRTOS Dual-Core SMP + Mock Sensor Abstraction Layer
// Features: Local Rule-Based Automation, MQTT Telemetry, Heartbeat, Auto-Reconnect
// ============================================================================

// CỜ CHUYỂN ĐỔI CHẾ ĐỘ MOCK SENSOR:
// 1 = Sử dụng Mock Sensor Layer (Chạy mô phỏng theo yêu cầu của Leader)
// 0 = Sử dụng Cảm biến phần cứng vật lý thật
#define USE_MOCK_SENSORS    1

// --- 1. PHẦN CỨNG & CHÂN ĐIỀU KHIỂN ---
#define DHTPIN              15
#define DHTTYPE             DHT22
#define SOUND_ADC_PIN       34

#define PIN_MISTING         25   // Relay 1: Máy phun sương tạo ẩm (Blue)
#define PIN_FAN             26   // Relay 2: Quạt hút thông gió (Green)
#define PIN_HEATER          27   // Relay 3: Đèn sưởi / Máy sưởi (Red)
#define PIN_ALARM           33   // Relay 4: Còi / Đèn chớp báo động (Orange)

#define RELAY_ACTIVE        HIGH
#define RELAY_INACTIVE      LOW

// --- 2. CẤU HÌNH ĐỊNH DANH & MQTT TOPIC TAXONOMY ---
const char* WIFI_SSID       = "Wokwi-GUEST";
const char* WIFI_PASSWORD   = "";
const char* MQTT_BROKER     = "broker.emqx.io";
const int   MQTT_PORT       = 1883;

// Định danh thiết bị chuẩn: swc-{houseId}-{floorZone}-{nodeId}
const char* DEVICE_ID       = "swc-h01-f01-node01";

// Cây Topic MQTT
const char* TOPIC_TELEMETRY = "swiftlet/telemetry/swc-h01-f01-node01";
const char* TOPIC_HEARTBEAT = "swiftlet/heartbeat/swc-h01-f01-node01";
const char* TOPIC_COMMAND   = "swiftlet/command/swc-h01-f01-node01";
const char* TOPIC_ACK       = "swiftlet/ack/swc-h01-f01-node01";
const char* TOPIC_STATUS    = "swiftlet/status/swc-h01-f01-node01";

// --- 3. CẤU TRÚC DỮ LIỆU CẢM BIẾN ---
struct SensorData {
  float temperature; // °C
  float humidity;    // % RH
  float co2_ppm;     // ppm
  float light_lux;   // Lux
  int   soundRaw;    // ADC Raw
  bool  soundHealthy;
  bool  isValid;
};

// --- 4. MOCK SENSOR ABSTRACTION LAYER (OOP INTERFACE) ---
class ISensorModule {
public:
  virtual bool init() = 0;
  virtual bool read(SensorData& data) = 0;
};

// Lớp 1: Cảm biến vật lý (Hardware Sensors)
class PhysicalSensorModule : public ISensorModule {
private:
  DHT dht;
public:
  PhysicalSensorModule() : dht(DHTPIN, DHTTYPE) {}
  bool init() override {
    dht.begin();
    return true;
  }
  bool read(SensorData& data) override {
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    int sound = analogRead(SOUND_ADC_PIN);

    if (isnan(t) || isnan(h) || t < 5.0 || t > 60.0 || h < 10.0 || h > 100.0) {
      data.isValid = false;
      return false;
    }
    data.temperature  = t;
    data.humidity     = h;
    data.co2_ppm      = 450.0; // Dự phòng
    data.light_lux    = 0.10;
    data.soundRaw     = sound;
    data.soundHealthy = (sound > 800);
    data.isValid      = true;
    return true;
  }
};

// Lớp 2: Cảm biến giả lập sinh học (Mock Sensor Module)
class MockSensorModule : public ISensorModule {
private:
  float currentTemp;
  float currentHum;
  float currentCO2;
  float currentLux;
  int   stepCounter;

public:
  MockSensorModule() : currentTemp(29.0), currentHum(78.5), currentCO2(520.0), currentLux(0.12), stepCounter(0) {}

  bool init() override {
    randomSeed(analogRead(0));
    return true;
  }

  bool read(SensorData& data) override {
    stepCounter++;
    // Giả lập biến thiên sinh học tự nhiên (Random Walk + Sinusoidal Drift)
    currentTemp += (random(-5, 6) / 10.0) + (sin(stepCounter * 0.1) * 0.2);
    currentHum  += (random(-8, 9) / 10.0) - (sin(stepCounter * 0.1) * 0.3);
    currentCO2  += (random(-15, 20));
    currentLux  = 0.08 + (random(0, 10) / 100.0);

    // Giữ trong giới hạn vật lý có thể xảy ra trong nhà yến
    if (currentTemp < 25.0) currentTemp = 25.5;
    if (currentTemp > 33.0) currentTemp = 32.5;
    if (currentHum < 65.0)  currentHum = 68.0;
    if (currentHum > 92.0)  currentHum = 90.0;
    if (currentCO2 < 400.0) currentCO2 = 420.0;
    if (currentCO2 > 900.0) currentCO2 = 880.0;

    data.temperature  = currentTemp;
    data.humidity     = currentHum;
    data.co2_ppm      = currentCO2;
    data.light_lux    = currentLux;
    data.soundRaw     = random(1200, 2400);
    data.soundHealthy = true;
    data.isValid      = true;
    return true;
  }
};

// Khởi tạo đối tượng cảm biến thông qua Interface
#if USE_MOCK_SENSORS
  MockSensorModule sensorDriver;
#else
  PhysicalSensorModule sensorDriver;
#endif

// --- 5. TOÀN CỤC: THAM SỐ ĐIỀU KHIỂN & HÀNG ĐỢI FREERTOS ---
Preferences prefs;
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// Cấu hình ngưỡng vi khí hậu
struct ControlConfig {
  float targetTemp;     // 29.0 °C
  float tempDeadband;   // 1.5 °C (Bật quạt khi > 30.5°C)
  float targetHum;      // 80.0 %
  float humDeadband;    // 3.0 %  (Bật phun sương khi < 77.0%)
  float co2Threshold;   // 700.0 ppm (Bật quạt hút khi quá ngưỡng)
  bool  isAutoMode;     // true: AUTO, false: MANUAL
} sysConfig;

SensorData latestSensorState;
QueueHandle_t sensorQueue;

// --- 6. LOCAL RULE-BASED AUTOMATIC CONTROL ENGINE ---
void evaluateRuleBasedControl(const SensorData& data) {
  if (!sysConfig.isAutoMode) return; // Nếu chế độ MANUAL thì bỏ qua

  if (!data.isValid) {
    // Fail-Safe: Ngắt máy bơm và sưởi khi cảm biến lỗi
    digitalWrite(PIN_MISTING, RELAY_INACTIVE);
    digitalWrite(PIN_HEATER, RELAY_INACTIVE);
    return;
  }

  // RULE 1 & 2: Kiểm soát độ ẩm (Máy phun sương)
  if (data.humidity < (sysConfig.targetHum - sysConfig.humDeadband)) {
    digitalWrite(PIN_MISTING, RELAY_ACTIVE); // Bật phun sương
  } else if (data.humidity >= sysConfig.targetHum) {
    digitalWrite(PIN_MISTING, RELAY_INACTIVE); // Tắt phun sương
  }

  // RULE 3 & 4: Kiểm soát nhiệt độ & Nồng độ CO2 (Quạt hút thông gió)
  bool needCooling = (data.temperature > (sysConfig.targetTemp + sysConfig.tempDeadband));
  bool needVentilation = (data.co2_ppm > sysConfig.co2Threshold);

  if (needCooling || needVentilation) {
    digitalWrite(PIN_FAN, RELAY_ACTIVE); // Bật quạt thông gió
  } else if (data.temperature <= sysConfig.targetTemp && data.co2_ppm <= 550.0) {
    digitalWrite(PIN_FAN, RELAY_INACTIVE); // Tắt quạt
  }

  // RULE 5: Bảo vệ nhiệt độ thấp (Máy sưởi)
  if (data.temperature < 26.0) {
    digitalWrite(PIN_HEATER, RELAY_ACTIVE); // Bật sưởi
  } else if (data.temperature >= 27.5) {
    digitalWrite(PIN_HEATER, RELAY_INACTIVE);
  }

  // RULE 6: Báo động lọt sáng (Bảo vệ tổ chim)
  if (data.light_lux > 1.0) {
    digitalWrite(PIN_ALARM, RELAY_ACTIVE);
  } else {
    digitalWrite(PIN_ALARM, RELAY_INACTIVE);
  }
}

// --- 7. TASK FREERTOS (CORE 1): SENSING & CONTROL ENGINE ---
void Task_ControlLoop(void *pvParameters) {
  SensorData localData;
  for (;;) {
    // 1. Đọc dữ liệu từ Sensor Layer (Mock hoặc Real)
    if (sensorDriver.read(localData)) {
      latestSensorState = localData;

      // 2. Thực thi hệ luật điều khiển cục bộ (Không phụ thuộc mạng)
      evaluateRuleBasedControl(localData);

      // 3. Gửi dữ liệu sang Task Mạng
      xQueueOverwrite(sensorQueue, &localData);
    }
    vTaskDelay(pdMS_TO_TICKS(2000)); // Chu kỳ 2 giây
  }
}

// --- 8. TASK FREERTOS (CORE 0): NETWORK, TELEMETRY, HEARTBEAT & MQTT ---
void sendAck(const char* cmdId, const char* status, const char* message) {
  StaticJsonDocument<256> ack;
  ack["commandId"] = cmdId;
  ack["nodeId"] = DEVICE_ID;
  ack["status"] = status;
  ack["mode"] = sysConfig.isAutoMode ? "AUTO" : "MANUAL";
  if (message != NULL) ack["message"] = message;
  ack["timestamp"] = millis() / 1000;

  char buf[256];
  serializeJson(ack, buf);
  mqttClient.publish(TOPIC_ACK, buf);
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, payload, length)) {
    sendAck("unknown", "FAILED", "Invalid JSON format");
    return;
  }

  const char* cmdId = doc["commandId"] | "unassigned";
  const char* action = doc["action"];

  if (strcmp(action, "SET_RELAY") == 0) {
    const char* target = doc["target"];
    int state = doc["state"];
    int pinState = (state == 1) ? RELAY_ACTIVE : RELAY_INACTIVE;

    if (strcmp(target, "misting") == 0) digitalWrite(PIN_MISTING, pinState);
    else if (strcmp(target, "fan") == 0) digitalWrite(PIN_FAN, pinState);
    else if (strcmp(target, "heater") == 0) digitalWrite(PIN_HEATER, pinState);
    else if (strcmp(target, "alarm") == 0) digitalWrite(PIN_ALARM, pinState);

    sysConfig.isAutoMode = false; // Chuyển sang MANUAL override
    sendAck(cmdId, "SUCCESS", "Actuator switched; mode changed to MANUAL");
  }
  else if (strcmp(action, "UPDATE_THRESHOLDS") == 0) {
    if (doc.containsKey("targetTemp")) sysConfig.targetTemp = doc["targetTemp"];
    if (doc.containsKey("targetHum")) sysConfig.targetHum = doc["targetHum"];
    if (doc.containsKey("isAutoMode")) sysConfig.isAutoMode = doc["isAutoMode"];

    // Lưu vào Flash NVS
    prefs.begin("swc_cfg", false);
    prefs.putFloat("temp", sysConfig.targetTemp);
    prefs.putFloat("hum", sysConfig.targetHum);
    prefs.putBool("auto", sysConfig.isAutoMode);
    prefs.end();

    sendAck(cmdId, "SUCCESS", "Thresholds updated in NVS; mode updated");
  }
}

void Task_NetworkManager(void *pvParameters) {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);

  SensorData sData;
  TickType_t lastTelemetryTick = 0;
  TickType_t lastHeartbeatTick = 0;

  for (;;) {
    // 1. Quản lý kết nối Wi-Fi & MQTT (Auto-Reconnect)
    if (WiFi.status() == WL_CONNECTED) {
      if (!mqttClient.connected()) {
        if (mqttClient.connect(DEVICE_ID, TOPIC_STATUS, 1, true, "{\"status\":\"offline\"}")) {
          mqttClient.publish(TOPIC_STATUS, "{\"status\":\"online\"}", true);
          mqttClient.subscribe(TOPIC_COMMAND);
          Serial.println("[MQTT] Connected and subscribed to commands.");
        } else {
          vTaskDelay(pdMS_TO_TICKS(3000));
          continue;
        }
      }
      mqttClient.loop();
    } else {
      vTaskDelay(pdMS_TO_TICKS(1000));
      continue;
    }

    TickType_t now = xTaskGetTickCount();

    // 2. Gửi Telemetry (Chu kỳ mỗi 5 giây)
    if (now - lastTelemetryTick >= pdMS_TO_TICKS(5000)) {
      lastTelemetryTick = now;
      if (xQueuePeek(sensorQueue, &sData, 0) == pdTRUE) {
        StaticJsonDocument<512> doc;
        doc["nodeId"] = DEVICE_ID;
        doc["timestamp"] = millis() / 1000;

        JsonObject metrics = doc.createNestedObject("metrics");
        metrics["temp"] = serialized(String(sData.temperature, 2));
        metrics["humidity"] = serialized(String(sData.humidity, 2));
        metrics["co2"] = round(sData.co2_ppm);
        metrics["lux"] = serialized(String(sData.light_lux, 2));
        metrics["soundOk"] = sData.soundHealthy;

        JsonObject relays = doc.createNestedObject("actuators");
        relays["misting"] = (digitalRead(PIN_MISTING) == RELAY_ACTIVE);
        relays["fan"] = (digitalRead(PIN_FAN) == RELAY_ACTIVE);
        relays["heater"] = (digitalRead(PIN_HEATER) == RELAY_ACTIVE);
        relays["alarm"] = (digitalRead(PIN_ALARM) == RELAY_ACTIVE);

        JsonObject state = doc.createNestedObject("state");
        state["mode"] = sysConfig.isAutoMode ? "AUTO" : "MANUAL";
        state["wifiRssi"] = WiFi.RSSI();
        state["freeHeap"] = ESP.getFreeHeap();

        char buf[512];
        serializeJson(doc, buf);
        mqttClient.publish(TOPIC_TELEMETRY, buf);
        Serial.print("[TELEMETRY] ");
        Serial.println(buf);
      }
    }

    // 3. Gửi Heartbeat riêng biệt (Chu kỳ mỗi 30 giây)
    if (now - lastHeartbeatTick >= pdMS_TO_TICKS(30000)) {
      lastHeartbeatTick = now;
      StaticJsonDocument<256> hb;
      hb["nodeId"] = DEVICE_ID;
      hb["type"] = "HEARTBEAT";
      hb["uptime"] = millis() / 1000;
      hb["ip"] = WiFi.localIP().toString();
      hb["freeHeap"] = ESP.getFreeHeap();
      hb["mockMode"] = USE_MOCK_SENSORS ? true : false;

      char hbBuf[256];
      serializeJson(hb, hbBuf);
      mqttClient.publish(TOPIC_HEARTBEAT, hbBuf);
      Serial.print("[HEARTBEAT] ");
      Serial.println(hbBuf);
    }

    vTaskDelay(pdMS_TO_TICKS(50));
  }
}

// --- 9. SETUP HỆ THỐNG ---
void setup() {
  Serial.begin(115200);
  Serial.println("\n=======================================================");
  Serial.println("  SWIFTLETCARE - ENTERPRISE FIRMWARE SKELETON (ESP32)  ");
  Serial.println("=======================================================");

  // Khởi tạo GPIO Actuators
  pinMode(PIN_MISTING, OUTPUT);
  pinMode(PIN_FAN, OUTPUT);
  pinMode(PIN_HEATER, OUTPUT);
  pinMode(PIN_ALARM, OUTPUT);
  digitalWrite(PIN_MISTING, RELAY_INACTIVE);
  digitalWrite(PIN_FAN, RELAY_INACTIVE);
  digitalWrite(PIN_HEATER, RELAY_INACTIVE);
  digitalWrite(PIN_ALARM, RELAY_INACTIVE);

  // Khởi tạo Sensor Driver (Mock hoặc Physical)
  sensorDriver.init();
#if USE_MOCK_SENSORS
  Serial.println("[MODE] >>> DANG KICH HOAT MOCK SENSOR ABSTRACTION LAYER <<<");
#else
  Serial.println("[MODE] >>> DANG DUNG PHYSICAL SENSOR DRIVER <<<");
#endif

  // Đọc cấu hình NVS Flash
  prefs.begin("swc_cfg", true);
  sysConfig.targetTemp   = prefs.getFloat("temp", 29.0);
  sysConfig.tempDeadband = 1.5;
  sysConfig.targetHum    = prefs.getFloat("hum", 80.0);
  sysConfig.humDeadband  = 3.0;
  sysConfig.co2Threshold = 700.0;
  sysConfig.isAutoMode   = prefs.getBool("auto", true);
  prefs.end();

  // Tạo Queue kết nối 2 Core
  sensorQueue = xQueueCreate(1, sizeof(SensorData));

  // Gán task vào Dual Core của ESP32
  xTaskCreatePinnedToCore(Task_ControlLoop, "Task_Control", 4096, NULL, 3, NULL, 1);     // Core 1 (Realtime)
  xTaskCreatePinnedToCore(Task_NetworkManager, "Task_Network", 4096, NULL, 2, NULL, 0); // Core 0 (Networking)
}

void loop() {
  vTaskDelete(NULL); // FreeRTOS nắm toàn quyền quản lý CPU
}
