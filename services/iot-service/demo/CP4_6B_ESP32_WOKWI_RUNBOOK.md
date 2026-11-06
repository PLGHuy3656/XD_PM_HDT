# SwiftletCare IoT Service — CP4.6B Real ESP32 / Wokwi Integration Runbook

This runbook guides the end-to-end integration of the aligned TV1 ESP32 firmware ([`firmware/esp32/sketch.ino`](../../../firmware/esp32/sketch.ino)) with the local SwiftletCare IoT Service (`services/iot-service`).

---

## 1. Hardware / Wokwi Setup Overview

```text
ESP32 Hardware / Wokwi (Private Gateway)
        │  Wi-Fi (STA)
        ▼
Windows Host LAN IPv4:1883  (Local MQTT Broker bound to 0.0.0.0:1883)
        │
        ▼
SwiftletCare IoT Service    (http://127.0.0.1:8002)
        ├── REST API        (/api/iot/...)
        └── WebSocket       (ws://localhost:8002/ws/iot)
```

### Important Networking Note (Physical ESP32 vs. Wokwi)
- **Physical ESP32 on the same Wi-Fi LAN (Recommended):** Connects directly to the Windows host's LAN IPv4 address on TCP port `1883` when the local broker binds to `0.0.0.0:1883`.
- **VS Code Wokwi Extension / Wokwi Private IoT Gateway:** Can reach the host's LAN IPv4 address (`192.168.x.x:1883`) when the Wokwi Private Gateway is active.
- **Public Browser Wokwi (`wokwi.com` without Private Gateway):** Runs inside an isolated cloud/WebAssembly virtual network (`10.13.37.x`) and **cannot** route directly to `127.0.0.1:1883` or an unbridged private LAN IP (`192.168.x.x:1883`) unless Wokwi IoT Gateway or a tunnel is active. Do **not** silently fall back to `broker.emqx.io` for canonical validation.

---

## 2. GPIO Mapping (`firmware/esp32/sketch.ino` & `diagram.json`)

| Component | ESP32 GPIO | Direction | Logic Level | Canonical Field / Target |
| :--- | :--- | :--- | :--- | :--- |
| **DHT22 Sensor** | `GPIO 15` | Input (Digital) | Digital | `metrics.temperature`, `metrics.humidity` |
| **Sound Sensor (ADC / Pot)** | `GPIO 34` | Input (ADC1_CH6) | `0..4095` | `metrics.audioRms`, `metrics.audioHealthy` |
| **Relay 1 — Misting (Blue LED)** | `GPIO 25` | Output | `HIGH` = ON (`1`), `LOW` = OFF (`0`) | `actuators.misting` / `target: "misting"` |
| **Relay 2 — Exhaust Fan (Green LED)** | `GPIO 26` | Output | `HIGH` = ON (`1`), `LOW` = OFF (`0`) | `actuators.fan` / `target: "fan"` |
| **Relay 3 — Heater (Red LED)** | `GPIO 27` | Output | `HIGH` = ON (`1`), `LOW` = OFF (`0`) | `actuators.heater` / `target: "heater"` |
| **Relay 4 — Alarm (Orange LED)** | `GPIO 33` | Output | `HIGH` = ON (`1`), `LOW` = OFF (`0`) | `actuators.alarm` / `target: "alarm"` |

---

## 3. Finding Windows Host LAN IPv4

In PowerShell on the Windows host, run:
```powershell
ipconfig
```
Look under your active **Wireless LAN adapter Wi-Fi** (or Ethernet adapter) for **IPv4 Address**, for example:
```text
IPv4 Address. . . . . . . . . . . : 192.168.1.100
```

---

## 4. Windows Firewall Requirement (TCP Port 1883)

For a physical ESP32 on the LAN to reach the Windows host on port `1883`, ensure TCP port `1883` is allowed on the Private/LAN profile (run in an elevated PowerShell if blocked):
```powershell
New-NetFirewallRule `
    -DisplayName "SwiftletCare Local MQTT Broker (TCP 1883)" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 1883 `
    -Action Allow `
    -Profile Private
```

---

## 5. Broker Host Configuration in Firmware

Open [`firmware/esp32/sketch.ino`](../../../firmware/esp32/sketch.ino) (lines 32–49) and set:
- `WIFI_SSID_CFG`: `"Wokwi-GUEST"` (for Wokwi) or your 2.4 GHz Wi-Fi SSID (for physical ESP32)
- `WIFI_PASSWORD_CFG`: `""` (for Wokwi) or your Wi-Fi password
- `MQTT_BROKER_HOST`: Your Windows host LAN IPv4 from `ipconfig` (e.g. `"192.168.1.100"`)
- `DEVICE_ID`: `"SWC-NODE-001"`

---

## 6. Terminal Startup Sequence

### Terminal 1 — Start Local MQTT Broker Bound to `0.0.0.0:1883`
```powershell
cd D:\Development\Projects\XD_PM_HDT\services\iot-service
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="."
$env:IOT_DEMO_BROKER_HOST="0.0.0.0"
$env:IOT_DEMO_BROKER_PORT="1883"
python demo/local_broker.py
```
Expected output:
```text
INFO demo.broker: Local MQTT broker listening on 0.0.0.0:1883
```

### Terminal 2 — Start IoT Service (`http://127.0.0.1:8002`)
```powershell
cd D:\Development\Projects\XD_PM_HDT\services\iot-service
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="."
$env:IOT_MQTT_AUTO_START="true"
$env:IOT_MQTT_BROKER_HOST="127.0.0.1"
$env:IOT_MQTT_BROKER_PORT="1883"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002
```

### Terminal 3 — Start Realtime WebSocket Observer
```powershell
cd D:\Development\Projects\XD_PM_HDT\services\iot-service
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="."
python demo/ws_observer.py
```

### Terminal 4 — Upload / Start ESP32 Firmware & Open Serial Monitor (`115200` baud)
1. Flash `firmware/esp32/sketch.ino` to ESP32 (or start Wokwi with Private Gateway).
2. Open Serial Monitor at `115200` baud.

Expected Serial Monitor output:
```text
=======================================================
  SWIFTLETCARE - ENTERPRISE FIRMWARE SKELETON (ESP32)  
=======================================================
[MODE] >>> DANG KICH HOAT MOCK SENSOR ABSTRACTION LAYER <<<
[MQTT] Connected and subscribed to commands.
[TELEMETRY] {"deviceId":"SWC-NODE-001","metrics":{"temperature":29.21,"humidity":78.10,"lux":0.14,"co2":525.0,"audioRms":0.45,"audioHealthy":true},"actuators":{"misting":false,"fan":false,"heater":false,"alarm":false},"state":{"mode":"AUTO","networkRssi":-52,"freeHeap":183420}}
[HEARTBEAT] {"deviceId":"SWC-NODE-001","uptime":30,"ip":"192.168.1.55","freeHeap":183100,"mockMode":true}
```

---

## 7. Terminal 5 — E2E Verification Suite (Tests A–G)

### Test A — Device ONLINE
```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8002/api/iot/devices/SWC-NODE-001/presence" | ConvertTo-Json -Depth 5
```
Expected: `status = "ONLINE"`, `lastStatusAt` populated.

### Test B — Canonical V1 Telemetry
```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8002/api/iot/devices/SWC-NODE-001/telemetry/latest" | ConvertTo-Json -Depth 5
```
Expected:
- `deviceId = "SWC-NODE-001"`
- `metrics`: `temperature`, `humidity`, `lux`, `co2`, `audioRms`, `audioHealthy`
- `actuators`: `misting`, `fan`, `heater`, `alarm`
- `state`: `mode = "AUTO"`, `networkRssi`, `freeHeap`
- WebSocket Observer (Terminal 3) prints `telemetry.updated`.

### Test C — Canonical V1 Heartbeat
Wait up to 30 seconds for the heartbeat cycle, then run:
```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8002/api/iot/devices/SWC-NODE-001/presence" | ConvertTo-Json -Depth 5
```
Expected: `status = "ONLINE"`, `lastHeartbeatAt` updated, `uptime >= 0`, `ip` populated, `mockMode = true`.

### Test D — Manual Fan Control (`SET_RELAY`: `fan` $\rightarrow$ `1`)
```powershell
$body = @{
    target = "fan"
    state  = 1
} | ConvertTo-Json

$cmd = Invoke-RestMethod `
    -Method Post `
    -Uri "http://localhost:8002/api/iot/devices/SWC-NODE-001/commands/relay" `
    -ContentType "application/json" `
    -Body $body

$cmd | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Get -Uri "http://localhost:8002/api/iot/commands/$($cmd.commandId)" | ConvertTo-Json -Depth 5
```
Expected:
1. ESP32 sets `PIN_FAN` (`GPIO 26`, Green LED) `HIGH` and `sysConfig.isAutoMode = false`.
2. ESP32 Serial Monitor prints:
   `[ACK] {"commandId":"...","deviceId":"SWC-NODE-001","status":"SUCCESS","mode":"MANUAL","message":"Actuator switched; mode changed to MANUAL"}`
3. IoT Service correlates ACK $\rightarrow$ `status = "SUCCESS"`, `ackMode = "MANUAL"`.
4. WebSocket Observer prints `command.updated` (`status = "SUCCESS"`).
5. Next `telemetry.updated` shows `"fan": true` and `"mode": "MANUAL"`.

### Test E — Return to AUTO (`UPDATE_THRESHOLDS`)
```powershell
$configBody = @{
    targetTemp = 28.5
    targetHum  = 82.0
    isAutoMode = $true
} | ConvertTo-Json

$cfgCmd = Invoke-RestMethod `
    -Method Post `
    -Uri "http://localhost:8002/api/iot/devices/SWC-NODE-001/commands/config" `
    -ContentType "application/json" `
    -Body $configBody

$cfgCmd | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Get -Uri "http://localhost:8002/api/iot/commands/$($cfgCmd.commandId)" | ConvertTo-Json -Depth 5
```
Expected:
1. ESP32 updates thresholds in RAM & NVS (`swc_cfg`), sets `isAutoMode = true`.
2. ESP32 publishes `SUCCESS` ACK with `"mode": "AUTO"`.
3. Next telemetry shows `"mode": "AUTO"`.

### Test F — Invalid Relay Target Rejection (Direct MQTT Publish Test)
Because the IoT REST API validates `target` before publishing (`422 Unprocessable Entity`), test the firmware's own defensive validation by publishing an invalid `SET_RELAY` target directly to `swiftlet/command/SWC-NODE-001`:
```powershell
cd D:\Development\Projects\XD_PM_HDT\services\iot-service
.\.venv\Scripts\Activate.ps1
python -c "
import json, uuid, paho.mqtt.publish as publish
cmd = {'commandId': str(uuid.uuid4()), 'action': 'SET_RELAY', 'target': 'invalid-relay', 'state': 1}
publish.single('swiftlet/command/SWC-NODE-001', json.dumps(cmd), qos=1, hostname='127.0.0.1', port=1883)
print('Published invalid target command:', cmd['commandId'])
"
```
Expected on ESP32 Serial Monitor:
```text
[ACK] {"commandId":"...","deviceId":"SWC-NODE-001","status":"FAILED","mode":"AUTO","message":"Unsupported relay target"}
```
Actuator states and `mode` remain unchanged.

### Test G — Offline / LWT Detection
Unplug/reset the ESP32 or stop the Wokwi simulation abruptly:
1. Broker detects TCP disconnect and broadcasts the registered LWT `{"status":"offline"}` on `swiftlet/status/SWC-NODE-001`.
2. WebSocket Observer prints `presence.updated` with `"status": "OFFLINE"`.
3. `Invoke-RestMethod -Method Get -Uri "http://localhost:8002/api/iot/devices/SWC-NODE-001/presence"` returns `"status": "OFFLINE"`.

---

## 8. Troubleshooting

| Symptom | Root Cause | Resolution |
| :--- | :--- | :--- |
| **ESP32 stuck before `[MQTT] Connected`** | Wi-Fi credentials mismatch or 5 GHz network | ESP32 only supports 2.4 GHz Wi-Fi; verify `WIFI_SSID_CFG` and `WIFI_PASSWORD_CFG` |
| **Wi-Fi connects, but MQTT reconnect loops every 3s** | Broker bound only to `127.0.0.1` or blocked by Windows Firewall | Start broker with `$env:IOT_DEMO_BROKER_HOST="0.0.0.0"`, verify host LAN IPv4 with `ipconfig`, and allow TCP `1883` in Windows Firewall |
| **MQTT connects, `[TELEMETRY]` prints on Serial, but nothing arrives at Broker** | `PubSubClient` 256-byte default buffer limit exceeded | Ensure `mqttClient.setBufferSize(512);` is present in `Task_NetworkManager` (already added in CP4.6B) |
| **`[TELEMETRY REJECTED]` in IoT Service logs** | Legacy field names (`nodeId`, `temp`, `soundOk`, `wifiRssi`, `timestamp`) | Flash the CP4.6B-updated `firmware/esp32/sketch.ino` |
| **ACK not correlated (`Unknown commandId`)** | Command sent outside IoT Service or `commandId` missing | Issue commands via `POST /api/iot/devices/SWC-NODE-001/commands/...` so IoT Service registers `commandId` before publishing |
| **Device transitions to `STALE`** | No heartbeat received within `IOT_DEVICE_STALE_TIMEOUT_SECONDS` (default 90s) | Ensure ESP32 remains connected and publishes `swiftlet/heartbeat/SWC-NODE-001` every 30s |
