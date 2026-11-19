# SwiftletCare IoT Service — Local E2E Demo Runbook (CP4.6A)

This runbook demonstrates the end-to-end SwiftletCare IoT Service (`services/iot-service`) locally using its own dedicated virtual environment (`services/iot-service/.venv`), without depending on `swiftletcare-backend/.venv`, `broker.emqx.io`, hardware ESP32 devices, PostgreSQL, or Frontend/API Gateway.

## Overview of Demo Terminals

| Terminal | Component | Default Address / Topic |
| :--- | :--- | :--- |
| **Terminal 1** | Local MQTT Broker (`demo/local_broker.py` or Mosquitto) | `127.0.0.1:1883` |
| **Terminal 2** | SwiftletCare IoT Service (`uvicorn app.main:app`) | `http://127.0.0.1:8002` |
| **Terminal 3** | Realtime WebSocket Observer (`demo/ws_observer.py`) | `ws://localhost:8002/ws/iot` |
| **Terminal 4** | Simulated ESP32 Node (`demo/device_simulator.py`) | `SWC-NODE-001` |
| **Terminal 5** | Operator REST CLI (PowerShell `Invoke-RestMethod`) | `http://localhost:8002/api/iot/...` |

---

## One-Time Local Virtual Environment Setup

If `services/iot-service/.venv` has not been created yet:

```powershell
cd D:\Development\Projects\XD_PM_HDT\services\iot-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## Step-by-Step Terminal Setup

### Terminal 1 — Start Local MQTT Broker (`127.0.0.1:1883`)

Option A (Recommended — Zero-dependency pure-Python local broker included in `demo/`):
```powershell
cd D:\Development\Projects\XD_PM_HDT\services\iot-service
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="."
python demo/local_broker.py
```

Option B (If local Mosquitto or Docker is installed):
```powershell
mosquitto -v -p 1883
# OR via Docker:
docker run --rm -it -p 1883:1883 eclipse-mosquitto:2 mosquitto -c /mosquitto-no-auth.conf
```

---

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

Expected log in Terminal 2:
- Connects to `127.0.0.1:1883`
- Subscribes to `swiftlet/telemetry/+`, `swiftlet/heartbeat/+`, `swiftlet/status/+`, `swiftlet/ack/+`

---

### Terminal 3 — Start WebSocket Observer (`ws://localhost:8002/ws/iot`)

Start the WebSocket observer before starting the device simulator so you can watch the initial `presence.updated` (`ONLINE`) and `telemetry.updated` events arrive live:

```powershell
cd D:\Development\Projects\XD_PM_HDT\services\iot-service
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="."
python demo/ws_observer.py
```

---

### Terminal 4 — Start Simulated ESP32 Device (`SWC-NODE-001`)

```powershell
cd D:\Development\Projects\XD_PM_HDT\services\iot-service
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="."
python demo/device_simulator.py --device-id SWC-NODE-001 --telemetry-interval 5 --heartbeat-interval 15
```

What `device_simulator.py` does automatically:
1. Configures MQTT Last Will and Testament (LWT) on `swiftlet/status/SWC-NODE-001` $\rightarrow$ `{"status":"offline"}` (`qos=1, retain=True`).
2. Connects to `127.0.0.1:1883`.
3. Publishes retained `{"status":"online"}` to `swiftlet/status/SWC-NODE-001`.
4. Subscribes to `swiftlet/command/SWC-NODE-001` (`qos=1`).
5. Publishes initial heartbeat (`swiftlet/heartbeat/SWC-NODE-001`) and telemetry (`swiftlet/telemetry/SWC-NODE-001`), then repeats every 5s / 15s.

---

## Terminal 5 — Operator REST Commands (PowerShell-Native)

Open a 5th PowerShell terminal to inspect state and send commands using PowerShell-native `Invoke-RestMethod` and `ConvertTo-Json` (avoiding `curl.exe` quote-escaping issues).

### 1. Check Service Health
```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8002/health" | ConvertTo-Json -Depth 5
```

### 2. Inspect Device Presence (`ONLINE`)
```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8002/api/iot/devices/SWC-NODE-001/presence" | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Get -Uri "http://localhost:8002/api/iot/devices/presence" | ConvertTo-Json -Depth 5
```

### 3. Inspect Latest Telemetry
```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8002/api/iot/devices/SWC-NODE-001/telemetry/latest" | ConvertTo-Json -Depth 5
```

### 4. Inspect Telemetry History (`limit=5`)
```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8002/api/iot/devices/SWC-NODE-001/telemetry?limit=5" | ConvertTo-Json -Depth 5
```

### 5. Issue Manual Relay Command (`SET_RELAY`: `fan` $\rightarrow$ `1`)
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
```
Observe immediately:
- **REST Response (`202 Accepted`):** Returns `"commandId"` (stored in `$cmd.commandId`).
- **Terminal 4 (Simulator):** Logs `Received command on swiftlet/command/SWC-NODE-001`, switches `actuators["fan"]=True` and `mode="MANUAL"`, and publishes `ACK (status=SUCCESS, mode=MANUAL)` on `swiftlet/ack/SWC-NODE-001`.
- **Terminal 3 (WebSocket Observer):** Prints `command.updated` (`"status": "SUCCESS", "ackMode": "MANUAL"`), followed by subsequent `telemetry.updated` events showing `"fan": true` and `"mode": "MANUAL"`.

### 6. Inspect Specific Command Lifecycle State
```powershell
Invoke-RestMethod `
    -Method Get `
    -Uri "http://localhost:8002/api/iot/commands/$($cmd.commandId)" | ConvertTo-Json -Depth 5
```

### 7. Issue Threshold & Mode Configuration Command (`UPDATE_THRESHOLDS` $\rightarrow$ `AUTO`)
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
```
Observe immediately:
- **Terminal 4 (Simulator):** Updates `targetTemp=28.5`, `targetHum=82.0`, switches `mode=AUTO`, and returns `SUCCESS` ACK.
- **Terminal 3 (WebSocket Observer):** Prints `command.updated` (`status=SUCCESS`, `ackMode=AUTO`) and subsequent `telemetry.updated` with `"mode": "AUTO"`.

### 8. Verify Offline Presence Detection
Stop **Terminal 4 (Simulator)** with `Ctrl+C`:
- Graceful stop publishes `{"status":"offline"}` on `swiftlet/status/SWC-NODE-001` (or abrupt kill triggers the broker's LWT `{"status":"offline"}`).
- **Terminal 3 (WebSocket Observer):** Immediately prints `presence.updated` with `"status": "OFFLINE"`.
- Verify via REST:
```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8002/api/iot/devices/SWC-NODE-001/presence" | ConvertTo-Json -Depth 5
```

---

## Firmware Compatibility Checklist for TV1 (`firmware/esp32/sketch.ino`)

When TV1 updates the physical ESP32 sketch (`firmware/esp32/sketch.ino`) to connect to `services/iot-service`, the following contract adjustments are required to match **Canonical V1**:

| Area | Current `firmware/esp32/sketch.ino` | Canonical V1 (`services/iot-service`) | Required TV1 Firmware Action |
| :--- | :--- | :--- | :--- |
| **MQTT Topics** | 3-level `swiftlet/{channel}/{device_code}` | 3-level `swiftlet/{channel}/{device_code}` | **Already compatible** |
| **LWT & Status** | `swiftlet/status/{id}` with `{"status":"online"}` / `{"status":"offline"}` | Same | **Already compatible** |
| **Command Payloads** | `SET_RELAY` (`target`, `state: 0/1`) & `UPDATE_THRESHOLDS` (`targetTemp`, `targetHum`, `isAutoMode`) | Same | **Already compatible** |
| **Root Identifier** | Uses `"nodeId"` in telemetry, heartbeat, and ACK | Uses `"deviceId"` (`extra="forbid"`) | Rename `"nodeId"` $\rightarrow$ `"deviceId"` in all JSON payloads |
| **Telemetry Root** | Includes `"timestamp": millis()/1000` | Server assigns `received_at`; root allows only `deviceId`, `metrics`, `actuators`, `state` | Remove `"timestamp"` from telemetry payload |
| **Telemetry Metrics** | Uses `"temp"` and `"soundOk"` | Uses `"temperature"`, `"audioRms"`, `"audioHealthy"` | Rename `"temp"` $\rightarrow$ `"temperature"`; replace `"soundOk"` with `"audioRms"` (`float`) & `"audioHealthy"` (`bool`) |
| **Telemetry State** | Uses `"wifiRssi"` | Uses `"networkRssi"` | Rename `"wifiRssi"` $\rightarrow$ `"networkRssi"` |
| **Heartbeat Payload** | Includes `"nodeId"` and `"type": "HEARTBEAT"` | Strictly `{"deviceId", "uptime", "ip", "freeHeap", "mockMode"}` | Rename `"nodeId"` $\rightarrow$ `"deviceId"` and remove `"type"` |
| **ACK Payload** | Includes `"nodeId"` and `"timestamp"` | Strictly `{"commandId", "deviceId", "status", "mode", "message"}` | Rename `"nodeId"` $\rightarrow$ `"deviceId"` and remove `"timestamp"` |
| **Unknown Relay Target** | Falls through `if/else if`, still sets `isAutoMode=false` and sends `SUCCESS` | Expects `FAILED` ACK for unknown relay targets | Add `else` branch in `SET_RELAY` to return `sendAck(cmdId, "FAILED", ...)` |
