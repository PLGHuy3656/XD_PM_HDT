# INT03-R1 — FCM Web Push: kiểm thử local trên Chrome (chờ TV4 cấu hình)

**Trạng thái: NOT VERIFIED.** Repo chưa có cấu hình Firebase, nên chưa thể kiểm thử FCM thật.
Không có kết quả PASS giả lập nào cho FCM.

## Hiện trạng code (kiểm tra read-only ngày 21/11/2026)

| Thành phần | Hiện trạng |
|---|---|
| Notification Service: gửi FCM (`app/delivery.py`, `send_fcm`) | Có code. Cần `FIREBASE_SERVICE_ACCOUNT_PATH` và `FIREBASE_PROJECT_ID`, hiện chưa được truyền vào `docker-compose.int03.yml` |
| Đăng ký token: `POST /api/v1/devices` / `DELETE /api/v1/devices/{id}` (qua Gateway, kiểm tra danh tính người gọi) | Có code (CP13/INT03) |
| Vòng đời token: bảng `notification_fcm_tokens`, `token UNIQUE`, gắn với `user_id` của JWT | Có code |
| Frontend: Firebase JS SDK, `firebase-messaging-sw.js`, VAPID key, lấy token | **Chưa có** |
| `.env.int03`: biến Firebase | **Chưa có** |

## Việc TV4 cần làm trên Firebase Console

1. Tạo Firebase project (hoặc dùng project có sẵn) → Project settings → General → Add app → Web.
   Ghi lại `apiKey`, `authDomain`, `projectId`, `messagingSenderId`, `appId`. Đây là cấu hình public, không phải bí mật.
2. Project settings → Cloud Messaging → Web Push certificates → Generate key pair.
   Lấy **public VAPID key**.
3. Project settings → Service accounts → Generate new private key (file JSON).
   **Đây là bí mật**:
   - Lưu ngoài repo, ví dụ `D:\Development\Secrets\swiftletcare-fcm.json`.
   - Tuyệt đối không commit file này.
4. Chrome: cho phép Notifications với `http://127.0.0.1:33000`.
   Chrome coi `127.0.0.1`/`localhost` là secure context nên service worker chạy được mà không cần HTTPS hay domain public.

## Template cấu hình (không chứa giá trị thật)

Thêm vào `.env.int03` (file này đã được gitignore):

```
FIREBASE_PROJECT_ID=<project-id>
FIREBASE_SERVICE_ACCOUNT_HOST_PATH=D:/Development/Secrets/swiftletcare-fcm.json
VITE_FIREBASE_API_KEY=<apiKey>
VITE_FIREBASE_AUTH_DOMAIN=<project-id>.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=<project-id>
VITE_FIREBASE_MESSAGING_SENDER_ID=<senderId>
VITE_FIREBASE_APP_ID=<appId>
VITE_FIREBASE_VAPID_KEY=<public VAPID key>
```

## Phần code còn phải làm sau khi có cấu hình (chưa làm ở R1)

- Compose:
  - Mount file service account read-only vào `notification-service`.
  - Truyền `FIREBASE_SERVICE_ACCOUNT_PATH` và `FIREBASE_PROJECT_ID`.
  - Truyền các biến `VITE_FIREBASE_*` làm build args cho frontend.
- Frontend:
  - Thêm `firebase` SDK.
  - Thêm `public/firebase-messaging-sw.js` để nhận thông báo khi tab ở background.
  - Sau đăng nhập: xin quyền, gọi `getToken({ vapidKey })`, rồi `POST /api/v1/devices {token, platform:"web"}`.
  - Khi đăng xuất: `DELETE` token.
  - Khi tab đang mở (foreground): dùng `onMessage`.

## Kịch bản nghiệm thu FCM (khi có cấu hình)

1. Đăng nhập Owner A trên Chrome → cho phép Notifications → token được lưu (`notification_fcm_tokens`).
2. Foreground: phát sự kiện IoT của Farm A → thông báo hiện ngay trong tab.
3. Background: thu nhỏ tab → thông báo hệ điều hành hiển thị qua service worker.
4. Đăng xuất → token bị xoá → không nhận thông báo nữa.
5. Owner B (Farm B) đăng nhập trên profile Chrome khác → không nhận thông báo của Farm A.
6. Token hết hạn/thu hồi → FCM trả `UNREGISTERED` → delivery chuyển `failed`. In-app notification vẫn hoạt động.
