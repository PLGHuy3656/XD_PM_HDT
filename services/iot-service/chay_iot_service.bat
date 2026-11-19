@echo off
title SwiftletCare - IoT Microservice (FastAPI + MQTT)
cd /d "%~dp0"
echo ==============================================================
echo   SWIFTLETCARE - IOT MICROSERVICE (PORT 8002 + MQTT BROKER)   
echo ==============================================================
set PYTHONPATH=.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
pause
