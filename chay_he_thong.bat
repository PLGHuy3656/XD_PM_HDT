@echo off
title Khoi Chay He Thong SwiftletCare (Docker Compose)
chcp 65001 > nul
cd /d "%~dp0"

echo ====================================================================
echo      SWIFTLETCARE - KHOI DONG HE THONG MICROSERVICES & IOT
echo ====================================================================
echo.

if not exist ".env" (
    echo [*] Phat hien chua co tep .env, dang tu dong tao tu .env.example...
    copy .env.example .env > nul
    echo [OK] Da tao tep .env thanh cong!
)

echo [*] Dang kiem tra trang thai Docker Engine...
docker info > nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo [X] LOI: Docker Engine chua duoc bat hoac Docker Desktop chua chay!
    echo     Vui long bat Docker Desktop truoc khi chay script nay.
    echo.
    pause
    exit /b 1
)

echo.
echo [*] Dang khoi chay toan bo cum 15 containers (Port 3000, 8000, 1883...)...
set COMPOSE_PARALLEL_LIMIT=2
docker compose -p swiftletcare-team -f docker-compose.team.yml up -d

if %ERRORLEVEL% equ 0 (
    echo.
    echo ====================================================================
    echo   [THANH CONG] HE THONG DA DUOC KHOI DONG SAN SANG!
    echo ====================================================================
    echo   - Giao dien Web (Frontend):    http://localhost:3000
    echo   - Tai khoan Admin:             admin.demo@nestmate.dev / admin_demo_password_2026
    echo   - Tai khoan Chu trai (Owner):  owner.a.demo@nestmate.dev / owner_demo_password_2026
    echo   - Tai khoan Ky thuat vien:     tech.a.demo@nestmate.dev / tech_demo_password_2026
    echo   - API Gateway / Swagger Docs:  http://localhost:8000/docs
    echo   - MQTT Broker:                 localhost:1883
    echo.
    echo [Huong dan ket noi ESP32]:
    echo   1. Mo trinh duyet vao http://localhost:3000 dang nhap Chu trai.
    echo   2. Chay file: firmware\chay_esp32_ao.bat de gia lap ESP32 gui so lieu that!
    echo   3. Vao menu 'Moi truong' de xem so lieu cap nhat truc tiep thoi gian thuc.
    echo ====================================================================
) else (
    echo.
    echo [X] Co loi xay ra trong qua trinh khoi chay Docker Compose!
)

pause
