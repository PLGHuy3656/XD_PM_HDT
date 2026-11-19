# SwiftletCare — Standalone Web Deployment Guide (Management V1)

Hướng dẫn này giúp bạn clone sạch repository và khởi chạy độc lập **Web Frontend, API Gateway, Management Service, PostgreSQL và Redis** bằng Docker, không yêu cầu cài đặt Python, Node.js, PostgreSQL hay Redis trên máy host và không cần chạy các dịch vụ AI, IoT, Notification hay Analytics.

---

## 1. Phạm vi Standalone vs Full Integrated

| Thành phần | Standalone Management V1 | Full Integrated (`docker-compose.yml`) |
|---|---|---|
| **Web Frontend (Nginx, same-origin `/api/*`)** | Có (`:13000`) | Có |
| **API Gateway (Auth, RBAC, Proxy)** | Có (`:18000`) | Có |
| **Management Service (Users, Farms, Zones, Devices, Technicians, Approval)** | Có (`:18001`) | Có |
| **PostgreSQL (`swiftletcare_standalone`) & Redis** | Có (`:15432`, `:16379`) | Có |
| **IoT Service (ESP32 telemetry, heartbeat, actuator ACK)** | Chưa chạy (Gateway trả `503`, UI hiển thị trạng thái chưa kết nối) | Có |
| **Notification Service (cảnh báo thời gian thực)** | Chưa chạy (Gateway trả `503`) | Có |
| **AI Vision / Camera Service (đếm chim, sự kiện AI)** | Chưa chạy (Gateway trả `503`) | Có |
| **Analytics Service (báo cáo dài hạn)** | Chưa chạy (Gateway trả `503`) | Có |

> Khi các dịch vụ ngoài phạm vi Standalone (IoT, Notification, AI, Analytics) được triển khai và trả HTTP `200`, giao diện tự động gỡ bỏ banner không khả dụng và nạp dữ liệu thực tế theo `src/api/serviceStatus.js`.

---

## 2. Yêu cầu hệ thống

- **Git**
- **Docker** và **Docker Compose v2** (`docker compose version`)

---

## 3. Clone repository

```bash
git clone https://github.com/PLGHuy3656/XD_PM_HDT.git
cd XD_PM_HDT
```

---

## 4. Cấu hình biến môi trường (`.env.standalone`)

Tạo file cấu hình từ template `.env.standalone.example`:

```bash
cp .env.standalone.example .env.standalone
```

> **Windows PowerShell:** `Copy-Item .env.standalone.example .env.standalone`

### Danh sách biến môi trường bắt buộc

| Biến | Mô tả |
|---|---|
| `ENVIRONMENT` | Chế độ vận hành (`standalone`) |
| `STANDALONE_FRONTEND_PORT` | Cổng host Web Frontend (mặc định `13000`) |
| `STANDALONE_GATEWAY_PORT` | Cổng host API Gateway (mặc định `18000`) |
| `STANDALONE_MANAGEMENT_PORT` | Cổng host Management Service (mặc định `18001`) |
| `STANDALONE_POSTGRES_PORT` | Cổng host PostgreSQL (mặc định `15432`) |
| `STANDALONE_REDIS_PORT` | Cổng host Redis (mặc định `16379`) |
| `POSTGRES_USER`, `POSTGRES_DB` | Tài khoản & tên database PostgreSQL |
| `POSTGRES_PASSWORD` | Mật khẩu PostgreSQL (dùng chuỗi hex/alphanumeric an toàn cho URL) |
| `REDIS_PASSWORD` | Mật khẩu Redis (dùng chuỗi hex/alphanumeric an toàn cho URL) |
| `JWT_SECRET` | Khóa ký JWT (tối thiểu 32 ký tự ngẫu nhiên) |
| `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Thuật toán (`HS256`) và thời hạn token (`60`) |
| `INTERNAL_SERVICE_TOKEN` | Token nội bộ giữa Gateway và Management Service (tối thiểu 32 ký tự hex) |
| `ALLOWED_ORIGINS` | Origin được phép CORS (khớp với `STANDALONE_FRONTEND_PORT`) |

Tạo chuỗi ngẫu nhiên an toàn bằng OpenSSL (Linux/macOS/Git Bash):

```bash
openssl rand -hex 16   # POSTGRES_PASSWORD
openssl rand -hex 16   # REDIS_PASSWORD
openssl rand -hex 32   # JWT_SECRET
openssl rand -hex 32   # INTERNAL_SERVICE_TOKEN
```

> **Bảo mật:** `.env.standalone` đã được `.gitignore` loại trừ. Không commit file `.env.standalone` hoặc bất kỳ mật khẩu/secret thật nào lên Git.

---

## 5. Khởi động Standalone Stack

```bash
docker compose -f docker-compose.standalone.yml --env-file .env.standalone up -d --build
docker compose -f docker-compose.standalone.yml --env-file .env.standalone ps
```

Cả 5 service (`postgres`, `redis`, `management-service`, `gateway`, `frontend`) phải đạt trạng thái `healthy`.

### URL truy cập mặc định

| Thành phần | URL |
|---|---|
| **Web Frontend (Nginx same-origin)** | `http://localhost:13000` |
| **API Gateway** | `http://localhost:18000` |
| **Management Service (Direct)** | `http://localhost:18001` |

---

## 6. Database Schema, Migrations & Quy tắc nghiệp vụ cốt lõi

### Khởi tạo mới vs Nâng cấp database hiện có
- **Volume mới (clean clone):** PostgreSQL tự động chạy `services/management-service/database/schema.sql` (đã bao gồm đầy đủ bảng, ràng buộc và các cột phê duyệt `approval_status`, `approved_by`, `approved_at`, `rejection_reason`) và nạp dữ liệu mẫu từ `infrastructure/postgres/sql/mgmt_seed.sql`.
- **Nâng cấp database Standalone tạo từ phiên bản trước:** Chạy migration idempotent `003_add_farm_approval.sql` (không làm mất dữ liệu cũ; các nhà yến hiện hữu mặc định là `APPROVED`):

```bash
docker compose -f docker-compose.standalone.yml --env-file .env.standalone exec -T postgres \
  psql -U swiftlet_standalone -d swiftletcare_standalone \
  < services/management-service/database/migrations/003_add_farm_approval.sql
```

Danh sách migrations trong `services/management-service/database/migrations/`:
1. `001_add_farm_owner.sql` — liên kết `farms.owner_id`.
2. `002_add_device_metadata_version.sql` — bổ sung `devices.metadata_version`.
3. `003_add_farm_approval.sql` — bổ sung quy trình phê duyệt nhà yến (`approval_status`, `approved_by`, `approved_at`, `rejection_reason`).

### Quy trình Farm Approval & Tự sinh mã
- **Farm Owner tạo nhà yến (`POST /api/farms`):** Trạng thái khởi tạo luôn là `PENDING`. Nhà yến chưa được duyệt (`PENDING` / `REJECTED`) bị chặn tạo Khu vực (Zone), đăng ký Thiết bị (Device) và gán Kỹ thuật viên (`HTTP 403/409`).
- **Admin phê duyệt / từ chối:** `POST /api/farms/{farm_id}/approve` (`APPROVED`) hoặc `POST /api/farms/{farm_id}/reject` với `{"rejection_reason": "..."}` (`REJECTED`). Admin tạo nhà yến trực tiếp có trạng thái `APPROVED`.
- **Tự sinh mã:** `farm_code` (định dạng `FARM-XXXXXX`) và `zone_code` (định dạng `Z-XXXXXX`) được backend tự sinh tự động nếu không truyền trong request.
- **Kỹ thuật viên & Thiết bị:** Admin gán Technician vào nhà yến `APPROVED` (`POST /api/technicians/{tech_id}/farms/{farm_id}/assign`). Technician được phân công có quyền đăng ký thiết bị thật (`POST /api/devices` với `node_id` phần cứng duy nhất) và gán/đổi khu vực (`PATCH /api/devices/{device_id}/zone`), không có quyền xóa thiết bị (`DELETE` trả `403`).

---

## 7. Tạo tài khoản kiểm thử (`ADMIN`, `FARM_OWNER`, `TECHNICIAN`)

> **Lưu ý bảo mật:** Không sử dụng mật khẩu mẫu cho môi trường công khai. Luôn thay `<your-test-password>` bằng mật khẩu thử nghiệm cục bộ của bạn.

Chạy lệnh sau qua container `management-service` để tạo đủ 3 tài khoản (lưu ý tài khoản `TECHNICIAN` cần có bản ghi tương ứng trong bảng `technicians` để Admin có thể phân công nhà yến):

```bash
docker compose -f docker-compose.standalone.yml --env-file .env.standalone exec management-service python -c "
import os, uuid, psycopg
from app.core.security import hash_password

accounts = [
    ('qa.admin@example.local', 'QA Admin', 'ADMIN', '<your-admin-password>'),
    ('qa.owner@example.local', 'QA Farm Owner', 'FARM_OWNER', '<your-owner-password>'),
    ('qa.tech@example.local', 'QA Technician', 'TECHNICIAN', '<your-tech-password>'),
]

with psycopg.connect(os.environ['DATABASE_URL']) as conn:
    with conn.cursor() as cur:
        for email, full_name, role, pwd in accounts:
            uid = str(uuid.uuid4())
            cur.execute(
                'INSERT INTO users (id, email, full_name, status, password_hash) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (email) DO NOTHING',
                (uid, email, full_name, 'ACTIVE', hash_password(pwd)),
            )
            cur.execute(
                'INSERT INTO user_roles (user_id, role_id) SELECT u.id, r.id FROM users u, roles r WHERE u.email = %s AND r.name = %s ON CONFLICT DO NOTHING',
                (email, role),
            )
            if role == 'TECHNICIAN':
                cur.execute(
                    'INSERT INTO technicians (id, full_name, email, phone, status) SELECT id, full_name, email, %s, %s FROM users WHERE email = %s ON CONFLICT (email) DO NOTHING',
                    ('0900000001', 'ACTIVE', email),
                )
        conn.commit()
print('Seeded ADMIN, FARM_OWNER, and TECHNICIAN accounts.')
"
```

---

## 8. Kiểm tra Health, CRUD & PostgreSQL Persistence

### Kiểm tra Health (Same-Origin & Direct)

```bash
curl -s http://localhost:13000/health
curl -s http://localhost:18000/health
curl -s http://localhost:18001/health
```

### Kiểm tra Đăng nhập & Tạo nhà yến qua Frontend Same-Origin

```bash
TOKEN=$(curl -s -X POST http://localhost:13000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"qa.owner@example.local","password":"<your-owner-password>"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# farm_code là tùy chọn (backend tự sinh FARM-XXXXXX nếu bỏ trống)
curl -s -X POST http://localhost:13000/api/farms \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"farm_name":"Nhà yến kiểm thử","address":"Quận 1"}'
```

### Kiểm tra PostgreSQL Persistence sau khi khởi động lại container

```bash
docker compose -f docker-compose.standalone.yml --env-file .env.standalone restart postgres management-service
curl -s http://localhost:13000/api/farms -H "Authorization: Bearer $TOKEN"
```

Dữ liệu Farm, Zone, Device và phân công Technician phải còn nguyên vẹn sau khi khởi động lại container.

---

## 9. Chạy bộ kiểm thử tự động (Frontend, Management, Gateway)

### Frontend Tests & Production Build (Node 20+)

```bash
cd frontend
npm ci
node scripts/test_environment_regression.js
node scripts/test_service_availability.js
node scripts/test_technician_devices_regression.js
npm test -- --run
npm run build
```

### Management Service & Gateway Pytest (qua Docker, không cần cài Python trên host)

```bash
# Management Service unit/service tests
docker run --rm -v "$(pwd)/services/management-service:/app" -w /app \
  $(docker compose -f docker-compose.standalone.yml images -q management-service) \
  sh -c "pip install -q pytest httpx && pytest -q tests/test_farm_approval.py tests/test_device_service.py tests/test_technician_service.py tests/test_farm_service.py tests/test_zone_service.py"

# Gateway Management proxy & RBAC tests
docker run --rm -v "$(pwd)/gateway:/app" -w /app \
  $(docker compose -f docker-compose.standalone.yml images -q gateway) \
  sh -c "pip install -q pytest httpx && pytest -q tests/test_management_crud_proxy.py"
```

---

## 10. Dừng và dọn dẹp

### Dừng stack (giữ nguyên dữ liệu PostgreSQL và Redis)

```bash
docker compose -f docker-compose.standalone.yml --env-file .env.standalone down
```

### Reset toàn bộ dữ liệu kiểm thử (Xóa volumes)

> **Cảnh báo mất dữ liệu:** Lệnh `-v` sẽ xóa vĩnh viễn dữ liệu trong các volume `swiftletcare_standalone_pg_data` và `swiftletcare_standalone_redis_data`. Chỉ chạy khi cần khởi tạo lại database sạch từ đầu.

```bash
docker compose -f docker-compose.standalone.yml --env-file .env.standalone down -v
```
