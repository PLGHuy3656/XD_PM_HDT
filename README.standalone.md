# SwiftletCare — Standalone Web Deployment Guide

Hướng dẫn này giúp bạn khởi chạy độc lập **Web Frontend, API Gateway, Management Service, PostgreSQL và Redis** bằng Docker trên một bản clone sạch, không yêu cầu cài đặt Python hay Node.js trên máy host và không cần chạy các dịch vụ AI, IoT, Notification hay Analytics.

---

## 1. Yêu cầu hệ thống

- **Git**
- **Docker** và **Docker Compose v2** (`docker compose version`)

*(Không cần cài Python, Node.js hoặc PostgreSQL/Redis trực tiếp trên máy host.)*

---

## 2. Clone repository

```bash
git clone https://github.com/PLGHuy3656/XD_PM_HDT.git
cd XD_PM_HDT
```

---

## 3. Cấu hình môi trường (`.env.standalone`)

Tạo file cấu hình từ template:

```bash
cp .env.standalone.example .env.standalone
```

> **Trên Windows PowerShell:** `Copy-Item .env.standalone.example .env.standalone`

### Tạo secret và mật khẩu ngẫu nhiên an toàn

Thay toàn bộ giá trị `replace_with_*` trong `.env.standalone` bằng chuỗi ngẫu nhiên an toàn. **Lưu ý:** dùng ký tự hex hoặc chữ/số (`openssl rand -hex ...`) để đảm bảo tương thích URL trong `DATABASE_URL` và `REDIS_URL`:

```bash
# Ví dụ tạo giá trị ngẫu nhiên bằng OpenSSL (Linux/macOS/Git Bash)
openssl rand -hex 16   # Dùng cho POSTGRES_PASSWORD
openssl rand -hex 16   # Dùng cho REDIS_PASSWORD
openssl rand -hex 32   # Dùng cho JWT_SECRET (tối thiểu 32 ký tự)
openssl rand -hex 32   # Dùng cho INTERNAL_SERVICE_TOKEN
```

*(Hoặc trên PowerShell có thể tạo bằng `[Convert]::ToHexString((1..16 | ForEach-Object { Get-Random -Maximum 256 }))` hoặc dùng Docker `docker run --rm alpine sh -c "tr -dc A-Za-z0-9 </dev/urandom | head -c 32"`.)*

> **Bảo mật:** File `.env.standalone` đã được `.gitignore` loại trừ; không commit file này hoặc bất kỳ credential thật nào lên Git.

---

## 4. Khởi động Standalone Stack

```bash
docker compose -f docker-compose.standalone.yml --env-file .env.standalone up -d --build
```

Kiểm tra trạng thái các container:

```bash
docker compose -f docker-compose.standalone.yml --env-file .env.standalone ps
```

Tất cả 5 service (`postgres`, `redis`, `management-service`, `gateway`, `frontend`) phải đạt trạng thái `healthy`.

---

## 5. URL truy cập

| Thành phần | URL mặc định |
|---|---|
| **Web Frontend (Nginx)** | `http://localhost:13000` |
| **API Gateway** | `http://localhost:18000` |
| **Management Service (Direct)** | `http://localhost:18001` |

*(Cổng mặc định có thể điều chỉnh qua các biến `STANDALONE_*_PORT` trong `.env.standalone`.)*

---

## 6. Tài khoản kiểm thử & Seed dữ liệu

Khi database `swiftletcare_standalone` khởi tạo lần đầu (volume rỗng), PostgreSQL tự động nạp schema từ `services/management-service/database/schema.sql` và dữ liệu mẫu từ `infrastructure/postgres/sql/mgmt_seed.sql`.

> **Cảnh báo bảo mật:** Dữ liệu seed demo **chỉ dành cho môi trường thử nghiệm cục bộ**. Không sử dụng dữ liệu seed này cho môi trường production hoặc triển khai công khai.

### Cách tạo tài khoản kiểm thử riêng (khuyên dùng)

Bạn có thể tạo tài khoản thử nghiệm với mật khẩu do chính bạn đặt thông qua container `management-service` (không cần cài Python trên host):

```bash
docker compose -f docker-compose.standalone.yml --env-file .env.standalone exec management-service python -c "
import os, uuid, psycopg
from app.core.security import hash_password

email = 'qa.admin@example.local'
password = '<your-test-password>'
pw_hash = hash_password(password)
uid = str(uuid.uuid4())

with psycopg.connect(os.environ['DATABASE_URL']) as conn:
    with conn.cursor() as cur:
        cur.execute(
            'INSERT INTO users (id, email, full_name, status, password_hash) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (email) DO NOTHING',
            (uid, email, 'QA Admin', 'ACTIVE', pw_hash),
        )
        cur.execute(
            'INSERT INTO user_roles (user_id, role_id) SELECT u.id, r.id FROM users u, roles r WHERE u.email = %s AND r.name = %s ON CONFLICT DO NOTHING',
            (email, 'ADMIN'),
        )
        conn.commit()
print('Created test ADMIN:', email)
"
```

*(Thay `'ADMIN'` bằng `'FARM_OWNER'` hoặc `'TECHNICIAN'` tùy vai trò cần kiểm thử, và đổi `email`/`password` trước khi chạy.)*

---

## 7. Kiểm tra Health & CRUD cơ bản

### Kiểm tra Health

```bash
curl -s http://localhost:13000/health
curl -s http://localhost:18000/health
curl -s http://localhost:18001/health
```

### Kiểm tra đăng nhập & Farm CRUD qua API Gateway

```bash
# 1. Đăng nhập lấy JWT
TOKEN=$(curl -s -X POST http://localhost:18000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"qa.admin@example.local","password":"<your-test-password>"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Tạo Farm mới
curl -s -X POST http://localhost:18000/api/farms \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"farm_code":"TEST-01","farm_name":"Test Swiftlet House","address":"Test Address"}'

# 3. Đọc danh sách Farms
curl -s http://localhost:18000/api/farms -H "Authorization: Bearer $TOKEN"
```

---

## 8. Dừng và dọn dẹp

### Dừng stack (giữ nguyên dữ liệu PostgreSQL và Redis)

```bash
docker compose -f docker-compose.standalone.yml --env-file .env.standalone down
```

### Reset toàn bộ dữ liệu kiểm thử (Xóa volumes)

> **Cảnh báo mất dữ liệu:** Lệnh `-v` sẽ **xóa vĩnh viễn** toàn bộ dữ liệu trong các volume PostgreSQL (`swiftletcare_standalone_pg_data`) và Redis (`swiftletcare_standalone_redis_data`) của stack standalone. Chỉ chạy khi muốn khởi tạo lại database sạch từ đầu.

```bash
docker compose -f docker-compose.standalone.yml --env-file .env.standalone down -v
```
