# SWIFTLETCARE — TEAM TEST RUNBOOK (CP15)
**Sổ Tay Hướng Dẫn Cài Đặt, Vận Hành & Kiểm Thử Chéo Toàn Hệ Thống**

**Dành cho:** Toàn bộ thành viên đội ngũ SwiftletCare (**TV1, TV2, TV3, TV4**)  
**Gói phát hành:** `SwiftletCare_Full_System_Team_Test.zip`  
**Phiên bản mã nguồn:** Baseline CP14 (Git HEAD `58b757f`)  
**Tiêu chuẩn đóng gói:** Portable Container Architecture (Độc lập 100%, không phụ thuộc máy host)

---

## 1. YÊU CẦU HỆ THỐNG & PHẦN MỀM TIÊN QUYẾT

Bản phân phối này được thiết kế để chạy độc lập trên máy tính cá nhân của bất kỳ thành viên nào (Windows, macOS hoặc Linux):

- **Hệ điều hành:**
  - Windows 10/11 64-bit (bắt buộc bật **WSL 2 Backend** trong Docker Desktop).
  - macOS (hỗ trợ cả Apple Silicon M1/M2/M3 và chip Intel).
  - Linux (Ubuntu 20.04+, Debian 11+, Fedora 38+).
- **Phần mềm yêu cầu:**
  - **Docker Desktop** phiên bản `>= 4.25` hoặc **Docker Engine** `>= 24.0`.
  - **Docker Compose** plugin phiên bản `>= v2.20`.
  - **Git** (tùy chọn).
  - Trình duyệt web hiện đại: Google Chrome, Microsoft Edge, Firefox, hoặc Safari.
- **Cấu hình phần cứng khuyến nghị:**
  - **RAM:** Tối thiểu 8 GB (Khuyến nghị **16 GB** để chạy mượt mà 12 microservices và cụm quan sát Loki/Prometheus/Grafana).
  - **Dung lượng ổ đĩa:** Trống tối thiểu **10 GB** (cho Docker images và cache build).
  - **CPU:** 4 Cores trở lên.

---

## 2. QUY TRÌNH KHỞI ĐỘNG HỆ THỐNG TRÊN MÁY THÀNH VIÊN

Gói bàn giao sử dụng tệp cấu hình chuyên biệt `docker-compose.team.yml` với đường dẫn tương đối (`./...`) và mạng nội bộ tự quản lý, không gây xung đột với bất kỳ dự án Docker nào khác trên máy của bạn.

### Bước 1: Giải Nén Gói Bàn Giao
Giải nén tệp `SwiftletCare_Full_System_Team_Test.zip` vào một thư mục làm việc bất kỳ trên máy của bạn, ví dụ:
- Windows: `C:\Projects\SwiftletCare_Team`
- macOS / Linux: `~/Projects/SwiftletCare_Team`

### Bước 2: Thiết Lập Biến Môi Trường
Mở cửa sổ dòng lệnh (Terminal / PowerShell) tại thư mục vừa giải nén và tạo tệp `.env`:
- **Windows (PowerShell):**
  ```powershell
  Copy-Item .env.example .env
  ```
- **macOS / Linux / Bash:**
  ```bash
  cp .env.example .env
  ```

> *Mẹo xử lý xung đột cổng:* Nếu máy của bạn đang chạy PostgreSQL cục bộ ở cổng `5433` hoặc Redis ở cổng `6379`, hãy mở tệp `.env` và đổi các biến `PORT_POSTGRES`, `PORT_REDIS`, `PORT_FRONTEND` sang cổng khác theo nhu cầu.

### Bước 3: Khởi Chạy Toàn Bộ Cụm Container
Chạy lệnh khởi động với cờ build tự động:
```bash
docker compose -p swiftletcare-team -f docker-compose.team.yml up -d --build
```
*Thời gian build lần đầu:* Khoảng 3–5 phút tùy tốc độ mạng và CPU (tải base image Node 20, Python 3.11, Nginx, PostgreSQL, Redis, RabbitMQ).

### Bước 4: Kiểm Tra Trạng Thái Sẵn Sàng (Health Check)
```bash
docker compose -p swiftletcare-team -f docker-compose.team.yml ps
```
Khi toàn bộ các dịch vụ hiển thị trạng thái `Up ... (healthy)`, hệ thống đã sẵn sàng 100% để kiểm thử.

### Bước 5: Xem Nhật Ký Vận Hành (Logs)
- Xem log toàn bộ hệ thống:
  ```bash
  docker compose -p swiftletcare-team -f docker-compose.team.yml logs -f
  ```
- Xem log một dịch vụ cụ thể (ví dụ Gateway hoặc AI Service):
  ```bash
  docker compose -p swiftletcare-team -f docker-compose.team.yml logs -f gateway
  docker compose -p swiftletcare-team -f docker-compose.team.yml logs -f ai-service
  ```

### Bước 6: Dừng Hệ Thống & Reset Dữ Liệu Demo
- **Dừng tạm thời (giữ nguyên dữ liệu demo đã tạo):**
  ```bash
  docker compose -p swiftletcare-team -f docker-compose.team.yml stop
  ```
- **Reset hoàn toàn về trạng thái xuất xưởng ban đầu:**
  ```bash
  docker compose -p swiftletcare-team -f docker-compose.team.yml down -v
  ```
  *(Cờ `-v` sẽ xóa volume dữ liệu tạm và buộc PostgreSQL khởi tạo lại dữ liệu mẫu sạch từ `01_init_all.sh` ở lần chạy kế tiếp).*

---

## 3. DANH MỤC URL & THÔNG TIN KẾT NỐI HỆ THỐNG

| Dịch Vụ | Địa Chỉ Truy Cập (URL) | Tài Khoản Đăng Nhập | Mật Khẩu Mặc Định Demo |
| :--- | :--- | :--- | :--- |
| **Giao Diện Website (Frontend)** | [http://localhost:3000](http://localhost:3000) | Xem mục 4 bên dưới | Xem mục 4 bên dưới |
| **API Gateway / Swagger Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | N/A (Xem tài liệu API) | Không yêu cầu |
| **RabbitMQ Management** | [http://localhost:15672](http://localhost:15672) | `swiftlet` | `swiftlet123` |
| **Grafana Monitoring Dashboard**| [http://localhost:3001](http://localhost:3001) | `admin` (hoặc xem tự do) | `swiftletcare_admin` |
| **Prometheus Metrics Explorer** | [http://localhost:9090](http://localhost:9090) | N/A (Mạng nội bộ) | Không yêu cầu |
| **PostgreSQL Demo Cluster** | `localhost:5433` (pgAdmin / DBeaver) | `postgres` | `postgres_demo_2026` |

### Hướng Dẫn Kết Nối pgAdmin 4 Vào CSDL Demo:
- **Host name/address:** `localhost` (hoặc `127.0.0.1`)
- **Port:** `5433` *(Lưu ý: Không dùng cổng 5432 để tránh nhầm với Postgres cài trên máy)*
- **Maintenance database:** `postgres`
- **Username:** `postgres` (Superuser) hoặc `management_user` (kết nối DB `management_db`)
- **Password:** `postgres_demo_2026` (hoặc `mgmt_password_2026`)
- **SSL mode:** `Prefer` hoặc `Disable`

---

## 4. TÀI KHOẢN THỬ NGHIỆM CHUẨN & HƯỚNG DẪN KIỂM THỬ TỪNG ROLE

Toàn bộ tài khoản đã được nạp sẵn vào cơ sở dữ liệu với mật khẩu đồng nhất cho môi trường demo:

### 4.1 Administrator (`admin.demo@nestmate.dev` / `admin_demo_password_2026`)
- **Kịch bản kiểm thử:**
  1. Đăng nhập tại [http://localhost:3000/login](http://localhost:3000/login).
  2. Hệ thống chuyển hướng vào `/admin/dashboard`. Kiểm tra số lượng nhà yến, cảm biến và trạng thái hệ sinh thái.
  3. Vào menu **Quản lý người dùng** (`/admin/users`):
     - Kiểm tra danh sách hiển thị đủ 4 tài khoản seed từ CSDL.
     - Nhấn nút **Thêm người dùng**, điền thông tin và tạo một tài khoản mới.
     - Thử tìm kiếm theo email hoặc lọc theo vai trò.
     - Nhấn nút Bật/Tắt trạng thái hoạt động (Active/Inactive).
  4. Vào menu **Trạng thái hệ thống** (`/admin/system`): Quan sát tình trạng sức khỏe của Gateway và các microservices.
  5. Nhấn nút **Đăng xuất**: Kiểm tra hệ thống thu hồi token trên Redis và chuyển hướng an toàn về màn hình đăng nhập.

### 4.2 Farm Owner (`owner.a.demo@nestmate.dev` / `owner_demo_password_2026`)
- **Kịch bản kiểm thử:**
  1. Đăng nhập tài khoản Chủ trại A.
  2. Hệ thống chuyển hướng vào `/owner/dashboard`. Quan sát các widget nhiệt độ, độ ẩm và biểu đồ diễn biến môi trường trong ngày của Nhà yến Demo 01.
  3. Vào menu **Môi trường & Telemetry** (`/owner/environment`): Kiểm tra các chỉ số nhiệt ẩm, độ sáng và cường độ âm học `audioRms`.
  4. Vào menu **Điều khiển thiết bị** (`/owner/devices`): Bật/tắt thử nghiệm máy phun sương hoặc quạt thông gió.
  5. Vào menu **AI & Đếm chim** (`/owner/swiftlets`): Quan sát danh sách camera chuồng yến và số lượng chim ra/vào.
  6. Vào menu **Cảnh báo** (`/owner/alerts`): Xem danh sách các cảnh báo nhiệt độ vượt ngưỡng an toàn.

### 4.3 Technician (`tech.a.demo@nestmate.dev` / `tech_demo_password_2026`)
- **Kịch bản kiểm thử:**
  1. Đăng nhập tài khoản Kỹ thuật viên A.
  2. Hệ thống chuyển hướng vào `/technician/dashboard`.
  3. Vào menu **Quản lý thiết bị** (`/technician/devices`): Xem danh sách các node cảm biến ESP32, gateway phần cứng và tình trạng firmware.
  4. Vào menu **Chẩn đoán mạng** (`/technician/diagnostics`): Kiểm tra cường độ tín hiệu sóng RSSI, dung lượng pin còn lại của từng node và thời gian phản hồi cuối cùng (Last ping).

---

## 5. GIẢI PHÁP KIỂM THỬ KHI KHÔNG CÓ THIẾT BỊ PHẦN CỨNG THẬT

### 5.1 Giả Lập Dữ Liệu Cảm Biến IoT (Khi Không Có Mạch ESP32 Thật)
Nếu TV1 hoặc thành viên khác muốn gửi dữ liệu cảm biến giả lập vào hệ thống:
Sử dụng công cụ MQTT Client (như **MQTTX**, **Mosquitto CLI** hoặc script Python):
- **Broker Host:** `localhost` | **Port:** `1883`
- **Topic:** `farm/a18d8eee-cb1a-4b00-b375-d505eb8128d7/sensor/NODE-01/telemetry`
- **Payload mẫu (JSON):**
  ```json
  {
    "timestamp": "2026-11-14T21:00:00Z",
    "temperature": 28.4,
    "humidity": 86.5,
    "light": 15.0,
    "audioRms": 45.2,
    "audioHealthy": true,
    "battery": 92.0,
    "rssi": -62
  }
  ```
Sau khi publish, mở lại màn hình `/owner/environment` trên website để thấy giá trị nhiệt ẩm cập nhật thời gian thực!

### 5.2 Kiểm Thử AI Service & Video Stream (Khi Không Có Camera RTSP Thật)
- AI Service được cấu hình sẵn chế độ PyTorch CPU nhẹ nhàng.
- Thư mục `services/ai-service/eval/fixtures/` có sẵn các video giả lập phục vụ chạy unit test và pipeline benchmark:
  ```bash
  # Chạy kiểm thử cô lập AI Service trong container:
  docker compose -p swiftletcare-team -f docker-compose.team.yml exec ai-service pytest tests/test_isolated_runner.py -v
  ```
- Nếu TV2 muốn nạp mô hình YOLO thật: Tải file trọng số `yolov8n.pt` và đặt vào thư mục `services/ai-service/models/`.

---

## 6. XỬ LÝ SỰ CỐ PHỔ BIẾN (TROUBLESHOOTING)

1. **Lỗi Xung Đột Cổng (`Bind for 0.0.0.0:XXXX failed: port is already allocated`):**
   - *Nguyên nhân:* Cổng đó đang bị chiếm dụng bởi một phần mềm khác trên máy bạn (ví dụ Skype, IIS, hoặc Postgres nội bộ).
   - *Khắc phục:* Mở tệp `.env`, đổi cổng bị trùng (ví dụ đổi `PORT_POSTGRES=5434`, `PORT_GATEWAY=8080`), sau đó chạy lại lệnh `up -d`.
2. **Lỗi Docker Daemon Không Khởi Động (`Cannot connect to the Docker daemon`):**
   - Đảm bảo ứng dụng **Docker Desktop** đã được mở và biểu tượng cá voi ở khay hệ thống hiển thị màu xanh lá cây (**Engine running**).
3. **Database Chưa Sẵn Sàng Khi Vừa Khởi Động:**
   - Ở lần chạy đầu tiên, container PostgreSQL cần khoảng 5-10 giây để chạy các script seed bảng và tài khoản. Nếu frontend báo lỗi kết nối trong 10 giây đầu, hãy chờ một lát và tải lại trang (`F5`).
4. **Không Thể Đăng Nhập Website (Lỗi 401 Unauthorized):**
   - Đảm bảo điền đúng đuôi email `@nestmate.dev` và mật khẩu tương ứng như đã liệt kê ở Mục 4.

---
*Chúc toàn đội ngũ kiểm thử thành công và sẵn sàng bước vào giai đoạn phát triển Mobile!*
