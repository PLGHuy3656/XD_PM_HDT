# SwiftletCare

**SwiftletCare: An Automated Environmental Control and Multi-Modal Health Monitoring System for Swiftlet Farming**

**SwiftletCare: Hệ thống tự động hóa điều khiển môi trường và giám sát sức khỏe nhà yến đa phương thức**

## Overview

SwiftletCare là hệ thống hỗ trợ giám sát và tự động hóa vận hành nhà yến thông qua IoT, Computer Vision, AI và các dịch vụ phần mềm.

Hệ thống hướng đến việc giải quyết các vấn đề chính trong quá trình vận hành nhà yến:

- Giám sát nhiệt độ, độ ẩm và các thông số môi trường.
- Điều khiển thiết bị môi trường ở chế độ tự động và thủ công.
- Theo dõi trạng thái và tình trạng hoạt động của thiết bị IoT.
- Đếm số lượng chim yến ra/vào bằng Computer Vision.
- Phát hiện các mối đe dọa như động vật săn mồi.
- Phân tích tín hiệu âm thanh và các bất thường.
- Cảnh báo và gửi thông báo đến người dùng.
- Lưu trữ dữ liệu lịch sử và hỗ trợ phân tích xu hướng.
- Hỗ trợ Technician cài đặt, cấu hình, chẩn đoán và xử lý các vấn đề kỹ thuật của hệ thống.

## System Actors

Hệ thống xác định ba nhóm người dùng chính:

| Actor | Responsibility |
|---|---|
| Farm Owner | Theo dõi và quản lý hoạt động nhà yến, môi trường, thiết bị, cảnh báo và dữ liệu giám sát |
| Technician | Cài đặt, cấu hình, kiểm tra, chẩn đoán và hỗ trợ vận hành thiết bị tại các nhà yến được phân công |
| Administrator | Quản lý người dùng, nhà yến, thiết bị, phân công Technician và cấu hình hệ thống |

## Main Modules

SwiftletCare được tổ chức thành các nhóm chức năng chính:

- **Frontend / Mobile** — Web dashboard và ứng dụng phục vụ Farm Owner, Technician và Administrator.
- **Backend** — API, business logic, authentication/authorization, realtime communication, data management và các service nghiệp vụ.
- **Technician Service** — Backend phục vụ nghiệp vụ Technician, bao gồm assigned farm access, device installation/configuration, diagnostics, technical alerts, work requests và tích hợp dữ liệu kỹ thuật từ IoT/AI.
- **IoT / Firmware** — Sensor acquisition, actuator control, device telemetry, local automatic control và offline operation.
- **AI Pipeline** — Swiftlet detection, object tracking, entry/exit counting, threat/anomaly detection và AI event processing.
- **Integration** — Kết nối Frontend, Backend, IoT và AI thông qua API, MQTT và các event/data contracts.
- **Documentation** — SRS, Use Case, UML, architecture, integration contracts và các tài liệu thiết kế.

## System Integration

Luồng tích hợp tổng quát của hệ thống:

```text
IoT / ESP32 ──────┐
                  │
                  ▼
             Backend Services
                  │
AI Pipeline ──────┤
                  │
                  ▼
          API / Realtime Layer
                  │
                  ▼
          Web / Mobile Frontend
```

Đối với nghiệp vụ Technician, Technician Service đóng vai trò xử lý business logic và tổng hợp dữ liệu kỹ thuật từ IoT và AI để phục vụ Device Management, Installation, Diagnostics, Technical Alerts và Work Requests.

## Repository Structure

```text
XD_PM_HDT/
├── ai-pipeline/            # AI / Computer Vision pipeline
│   ├── src/
│   ├── tests/
│   └── ...
│
├── backend/                # Backend services and APIs
│   ├── src/
│   └── ...
│
├── firmware/               # ESP32 / IoT firmware
│   ├── src/
│   └── ...
│
├── frontend/               # React Web application
│   ├── src/
│   ├── public/
│   └── ...
│
├── docs/                   # Project documentation
│   ├── requirements/
│   ├── uml/
│   └── ...
│
├── mobile/                 # React Native application
│
└── README.md
```

Các module chính của hệ thống đã được khởi tạo và đang được phát triển song song bởi các thành viên trong nhóm:

- `frontend/` — Web Frontend cho Farm Owner, Technician và Administrator.
- `backend/` — Backend services, API, business logic và các thành phần tích hợp hệ thống.
- `firmware/` — Firmware cho ESP32, sensor, actuator và giao tiếp IoT.
- `ai-pipeline/` — Computer Vision/AI processing, detection, tracking và event processing.
- `mobile/` — Ứng dụng Mobile của hệ thống.
- `docs/` — Requirement, SRS, Use Case, UML, architecture và tài liệu kỹ thuật.

Cấu trúc chi tiết bên trong từng module được quản lý theo phạm vi kỹ thuật của thành viên phụ trách và tiếp tục được hoàn thiện trong quá trình Implementation & Integration.

## Documentation

Các tài liệu chính:

- [Software Requirements Specification](docs/requirements/SRS.md)
- [Use Case Documentation](docs/uml/use-case/README.md)
- [Overall Use Case Diagram](docs/uml/use-case/overall-use-case.puml)

Ngoài repository, project sử dụng Confluence để quản lý các tài liệu phân tích, kiến trúc và thiết kế trong quá trình phát triển.

## Development Team

| Member | Responsibility |
|---|---|
| TV1 – Phạm Lê Gia Huy | Team Leader, Frontend/Mobile, Technician Backend & Integration, Testing |
| TV2 | Backend Services & System Infrastructure |
| TV3 | Embedded IoT / Hardware / Firmware |
| TV4 | AI Pipeline |

### Responsibility Boundaries

**TV1 – Team Leader, Frontend/Mobile, Technician Backend & Integration**
- Phát triển Frontend Web/Mobile.
- Phát triển Technician Service và các API/business logic dành cho Technician.
- Tích hợp Technician Backend với IoT và AI.
- Thực hiện integration và End-to-End testing cho các luồng liên quan.
- Điều phối quá trình phát triển và tích hợp giữa các thành viên.

**TV2 – Backend Services & System Infrastructure**
- Phát triển các Backend Service còn lại của hệ thống.
- Authentication, authorization và data management.
- Realtime communication và các thành phần hạ tầng Backend.
- API Gateway, Redis, Firebase Messaging, Apache NiFi và các thành phần Backend liên quan.

**TV3 – Embedded IoT / Hardware / Firmware**
- ESP32, sensor và actuator.
- Firmware và device telemetry.
- Local automatic control.
- Device connectivity và offline operation.
- Phối hợp thống nhất MQTT/data contract với Backend.

**TV4 – AI Pipeline**
- Computer Vision và AI processing.
- Swiftlet detection và tracking bằng YOLO26 + ByteTrack.
- Entry/exit counting.
- Threat/anomaly detection.
- Cung cấp AI events và processing status cho Backend.

Việc tích hợp IoT và AI vào Backend được thực hiện phối hợp giữa TV1 với TV3 và TV4; ownership của firmware/hardware vẫn thuộc TV3 và AI model/pipeline vẫn thuộc TV4.

## Technology & Architecture

Các công nghệ và thành phần chính của hệ thống:

- **Frontend:** React, Vite, React Router.
- **Mobile:** React Native.
- **Backend:** Node.js / NestJS, Microservices.
- **Database:** MongoDB.
- **Cache:** Redis.
- **IoT:** ESP32, MQTT/HTTP.
- **AI/CV:** YOLO26, ByteTrack, OpenCV.
- **API Documentation:** OpenAPI / Swagger.
- **Notification:** Firebase Cloud Messaging.
- **Data Synchronization:** Apache NiFi.
- **API Management:** API Gateway.
- **Deployment:** Docker.

## Development Workflow

Project sử dụng:

- **Confluence** — Requirement analysis, architecture và project documentation.
- **Jira** — Planning, backlog, task assignment và progress tracking.
- **GitHub** — Source code, version control, branch management, Pull Request và collaboration.

Quy trình phát triển tổng quát:

```text
Requirements
    ↓
SRS
    ↓
Use Cases
    ↓
System Design & UML
    ↓
Architecture & Integration Contracts
    ↓
Product Backlog & Planning
    ↓
Implementation
    ↓
Testing
    ↓
Integration & Validation
```

Các module được phát triển theo branch và được tích hợp thông qua Pull Request sau khi hoàn thành các checkpoint chức năng và kiểm tra build.

## Current Status

Project hiện đang trong giai đoạn:

**Implementation → Integration → Testing**

Các tài liệu Requirement, SRS, Use Case và kiến trúc cơ bản đã được xây dựng và tiếp tục được cập nhật khi có thay đổi được nhóm thống nhất.

Frontend được phát triển theo từng actor và đang được tích hợp dần với Backend. Backend, IoT và AI Pipeline được phát triển song song theo phạm vi trách nhiệm của từng thành viên.

Các integration contract giữa Backend, IoT và AI tiếp tục được hoàn thiện trong quá trình triển khai và kiểm thử End-to-End.
