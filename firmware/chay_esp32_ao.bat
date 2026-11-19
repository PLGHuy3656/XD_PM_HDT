@echo off
title SwiftletCare - ESP32 Hardware Simulator (TV1)
chcp 65001 > nul
cd /d "%~dp0"
echo =================================================================
echo   SWIFTLETCARE - BO GIA LAP PHAN CUNG ESP32 (KET NOI DOCKER)
echo =================================================================
echo Dang khoi dong ESP32 gia lap ket noi vao Mosquitto Broker...
python esp32_simulator.py
pause
