# INT03-R2 — FCM Web Push: Hướng dẫn cấu hình Firebase & nghiệm thu Chrome local

**Trạng thái hiện tại:** `CODE READY — CONFIGURATION REQUIRED` (`REAL CHROME PUSH: NOT VERIFIED` cho đến khi TV4 cấu hình Firebase project thật và chạy Chặng 2).

FCM Web Push chỉ là **kênh gửi bổ sung**. Notification persistence trong PostgreSQL (`notification_db`) vẫn là nguồn dữ liệu chính; khi Firebase chưa cấu hình hoặc tạm gián đoạn, in-app notifications vẫn hoạt động bình thường.

---

## 1. Kiến trúc INT03-R2 đã sẵn sàng trong code

| Thành phần | Trạng thái code |
|---|---|
| **API Gateway** (`gateway/app/routes.py`) | Đã mở `POST /api/v1/notifications/fcm-tokens` và `DELETE /api/v1/notifications/fcm-tokens` (bắt buộc JWT, chặn `userId`/`user_id` của người khác). |
| **Notification Service** (`app/routes.py`, `app/delivery.py`, `app/repositories.py`) | Gắn token theo user từ JWT (`notification_fcm_tokens.token UNIQUE`, upsert theo user mới nhất). Gửi **data-only FCM message** (`title`, `body`, `notification_id`, `event_id`, `event_type`, `link` nội bộ an toàn); tự xóa token hết hạn/không hợp lệ (`UnregisteredError`, `SenderIdMismatchError`, `InvalidArgumentError`); không log raw token/credentials. |
| **Frontend Firebase SDK & SW** (`fcmClient.js`, `fcmConfig.js`, `useWebPush.js`, `public/firebase-messaging-sw.js`) | Chỉ xin quyền khi người dùng bấm **"Bật thông báo trên trình duyệt"** (trong `Cài đặt tài khoản → Thông báo` hoặc `Trung tâm thông báo`). Hiển thị 6 trạng thái (`Chưa bật`, `Đang đăng ký`, `Đã bật`, `Bị trình duyệt chặn`, `Chưa cấu hình Firebase`, `Không khả dụng`). Foreground tự đồng bộ Bell/Center từ API (không trùng OS notification). Background hiển thị 1 OS notification với `tag = event_id || notification_id`. Click kiểm tra đường dẫn tương đối cùng origin, focus/mở tab trên `http://localhost:33000`. Logout tự hủy đăng ký token trước khi thu hồi JWT. |
| **Docker Compose Overlay** (`docker-compose.int03.fcm.yml`) | Bind-mount read-only (`:ro`) file Service Account JSON từ máy host vào `/run/secrets/firebase-service-account.json` trong `notification-service` — không copy vào Docker image, không commit vào Git. |

---

## 2. Việc TV4 cần làm trên Firebase Console (chỉ 1 lần)

1. Mở [Firebase Console](https://console.firebase.google.com/) → chọn hoặc tạo project (ví dụ `swiftletcare-local`).
2. **Tạo Web App (cấu hình client public):**
   - **Project settings → General → Your apps → Add app → Web (`</>`)**.
   - Ghi lại 5 giá trị:
     - `apiKey` → `VITE_FIREBASE_API_KEY`
     - `authDomain` → `VITE_FIREBASE_AUTH_DOMAIN`
     - `projectId` → `VITE_FIREBASE_PROJECT_ID` (và `FIREBASE_PROJECT_ID`)
     - `messagingSenderId` → `VITE_FIREBASE_MESSAGING_SENDER_ID`
     - `appId` → `VITE_FIREBASE_APP_ID`
3. **Tạo Web Push Certificate (VAPID public key):**
   - **Project settings → Cloud Messaging → Web configuration → Web Push certificates → Generate key pair**.
   - Copy **Key pair (public key)** → `VITE_FIREBASE_VAPID_KEY`.
4. **Tạo Service Account Private Key (BÍ MẬT — chỉ dùng ở backend):**
   - **Project settings → Service accounts → Firebase Admin SDK → Generate new private key**.
   - Lưu file JSON **bên ngoài repo Git**, ví dụ:
     `D:\Development\Secrets\swiftletcare-fcm.json`
   - **Tuyệt đối không** copy file này vào thư mục repo, không gửi nội dung key lên chat, không commit lên Git.

---

## 3. Cấu hình vào `.env.int03` (file local đã được gitignore)

Mở `D:\Development\Projects\XD_PM_HDT_int03\.env.int03` và **bổ sung** (không xóa các biến sẵn có):

```env
# --- INT03-R2: Firebase Cloud Messaging (Local Chrome Web Push) ---
FIREBASE_PROJECT_ID=<project-id>
FIREBASE_SERVICE_ACCOUNT_HOST_PATH=D:/Development/Secrets/swiftletcare-fcm.json

VITE_FIREBASE_API_KEY=<apiKey>
VITE_FIREBASE_AUTH_DOMAIN=<project-id>.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=<project-id>
VITE_FIREBASE_MESSAGING_SENDER_ID=<messagingSenderId>
VITE_FIREBASE_APP_ID=<appId>
VITE_FIREBASE_VAPID_KEY=<public-vapid-key>
```

---

## 4. Lệnh triển khai Chặng 2 (chỉ rebuild 3 service liên quan, giữ nguyên DB/volumes/port 33000)

Sau khi TV4 hoàn tất bước 2 & 3 và cho phép chạy Chặng 2:

```powershell
Set-Location 'D:\Development\Projects\XD_PM_HDT_int03'
docker compose -p swiftletcare-int03 `
  -f docker-compose.int03.yml `
  -f docker-compose.int03.fcm.yml `
  --env-file .env.int03 `
  up -d --build --no-deps gateway notification-service frontend
```

Sau đó kiểm thử trực tiếp trên Chrome tại `http://localhost:33000` (hoặc `http://127.0.0.1:33000` — lưu ý Chrome phân tách quyền Notification và Service Worker giữa `localhost` và `127.0.0.1`, nên chọn thống nhất `http://localhost:33000` trong toàn bộ phiên test!).
