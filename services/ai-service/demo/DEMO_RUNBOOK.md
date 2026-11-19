# SwiftletCare AI Service V1 — Manual & Automated E2E Runbook (CP5.3 & CP5.4)

> **LOCAL REFERENCE PROTOTYPE ONLY — DO NOT COMMIT / DO NOT PUSH**
> `ai-pipeline/` and `AI Service` belong to **TV2**. This local prototype validates the canonical REST V1 + WebSocket V1 integration boundary.

---

## 1. CP5.4 Four-Terminal Manual E2E Validation (`127.0.0.1:8003`)

Follow this exact startup order (`Terminal 1` $\rightarrow$ `Terminal 2` $\rightarrow$ `Terminal 3` $\rightarrow$ `Terminal 4`).

### Terminal 1 — Start AI Service on `127.0.0.1:8003`
```powershell
cd D:\Development\Projects\XD_PM_HDT
$env:PYTHONPATH = "services/ai-service;ai-pipeline/src"
.\services\ai-service\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8003
```

### Terminal 2 — Start Realtime WebSocket Observer (`ws://127.0.0.1:8003/ws/ai`)
```powershell
cd D:\Development\Projects\XD_PM_HDT
$env:PYTHONPATH = "services/ai-service;ai-pipeline/src"
.\services\ai-service\.venv\Scripts\python.exe services/ai-service/demo/ws_observer.py --url ws://127.0.0.1:8003/ws/ai
```

### Terminal 3 — Run AI Runtime with Real TV2 Model (`ai-pipeline/models/best.pt`) and Real Repository Media
```powershell
cd D:\Development\Projects\XD_PM_HDT
$env:PYTHONPATH = "services/ai-service;ai-pipeline/src"
.\services\ai-service\.venv\Scripts\python.exe services/ai-service/demo/runtime_runner.py --camera CAM-01 --source "frontend/public/NestMate Swiftlet Flight Logo.png" --model ai-pipeline/models/best.pt --repeat 5 --fps 2.0
```
*(Note: If you later place a real video or predator sample folder into `ai-pipeline/data/samples/`, pass `--source ai-pipeline/data/samples/entrance.mp4` or `--source ai-pipeline/data/samples/predators --repeat 3`.)*

### Terminal 4 — Manual REST Operator Commands
```powershell
# 1. Health check
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8003/health" | ConvertTo-Json -Depth 5

# 2. List all cameras
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8003/api/v1/ai/cameras" | ConvertTo-Json -Depth 5

# 3. Get CAM-01 runtime status
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8003/api/v1/ai/cameras/CAM-01/status" | ConvertTo-Json -Depth 5

# 4. Get CAM-01 latest detections
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8003/api/v1/ai/cameras/CAM-01/detections/latest" | ConvertTo-Json -Depth 6

# 5. Get CAM-01 latest counts
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8003/api/v1/ai/cameras/CAM-01/counts/latest" | ConvertTo-Json -Depth 5

# 6. List recent AI events (predator alerts)
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8003/api/v1/ai/events" | ConvertTo-Json -Depth 5

# 7. If a predator event is produced, verify HTTP 200 JPEG on its snapshot URL:
$events = @(Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8003/api/v1/ai/events")
if ($events.Count -gt 0 -and $events[0].snapshot) {
    Invoke-WebRequest -Method Get -Uri ("http://127.0.0.1:8003" + $events[0].snapshot) | Select-Object StatusCode, @{Name="ContentType";Expression={$_.Headers["Content-Type"]}}, @{Name="Bytes";Expression={$_.RawContentLength}}
} else {
    Write-Host "PREDATOR MANUAL TEST PENDING SAMPLE MEDIA (no predator events in current run)"
}
```

---

## 2. Automated End-to-End Demo (Synthetic + Real `models/best.pt`)

From the repository root (`D:\Development\Projects\XD_PM_HDT`), run:

```powershell
$env:PYTHONPATH = "services/ai-service;ai-pipeline/src"
.\services\ai-service\.venv\Scripts\python.exe services/ai-service/demo/run_e2e_demo.py --mode both
```
