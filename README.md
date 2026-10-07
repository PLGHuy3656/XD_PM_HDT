# SwiftletCare

**SwiftletCare: An Automated Environmental Control and Multi-Modal Health Monitoring System for Swiftlet Farming**

**SwiftletCare: Hệ thống tự động hóa điều khiển môi trường và giám sát sức khỏe nhà yến đa phương thức**

## Overview

SwiftletCare là hệ thống hỗ trợ giám sát và tự động hóa vận hành nhà yến thông qua IoT, Computer Vision, AI và các dịch vụ phần mềm.

Hệ thống hướng đến việc giải quyết các vấn đề chính trong quá trình vận hành nhà yến:

- Giám sát nhiệt độ, độ ẩm và các thông số môi trường.
- Điều khiển thiết bị môi trường ở chế độ tự động và thủ công.
- Theo dõi trạng thái thiết bị IoT.
- Đếm số lượng chim yến ra/vào bằng Computer Vision.
- Phát hiện các mối đe dọa như động vật săn mồi.
- Phân tích tín hiệu âm thanh và các bất thường.
- Cảnh báo và gửi thông báo đến người dùng.
- Lưu trữ dữ liệu lịch sử và hỗ trợ phân tích xu hướng.

## System Actors

Hệ thống hiện xác định ba nhóm người dùng chính:

| Actor | Responsibility |
|---|---|
| Farm Owner | Theo dõi và quản lý hoạt động nhà yến |
| Technician | Quản lý, kiểm tra và hỗ trợ vận hành thiết bị IoT |
| Administrator | Quản lý người dùng, phân quyền và cấu hình hệ thống |

## Main Modules

SwiftletCare được tổ chức thành các nhóm chức năng chính:

- **Frontend / Mobile** — Web dashboard và ứng dụng cho người dùng.
- **Backend** — API, business logic, authentication, realtime communication và data management.
- **IoT / Firmware** — Sensor acquisition, actuator control và local automatic control.
- **AI Pipeline** — Swiftlet detection, object tracking, entry/exit counting và anomaly detection.
- **Documentation** — SRS, Use Case, UML, architecture và các tài liệu thiết kế.

## Repository Structure

```text
XD_PM_HDT/
├── docs/
│   ├── requirements/
│   │   └── SRS.md
│   └── uml/
│       └── use-case/
│           ├── README.md
│           └── overall-use-case.puml
│
├── frontend/
│
├── backend/          # Planned
├── firmware/         # Planned
├── ai-pipeline/      # Planned
├── mobile/           # Planned
│
└── README.md
```

Các module đang ở trạng thái planned sẽ được bổ sung khi quá trình implementation bắt đầu.

## Documentation

Các tài liệu hiện tại:

- [Software Requirements Specification](docs/requirements/SRS.md)
- [Use Case Documentation](docs/uml/use-case/README.md)
- [Overall Use Case Diagram](docs/uml/use-case/overall-use-case.puml)

Tài liệu sẽ tiếp tục được bổ sung trong quá trình phân tích và thiết kế hệ thống.

## Development Team

| Member | Responsibility |
|---|---|
| TV1 | Project Leader, Frontend/Mobile, Testing & Thesis |
| TV2 | Backend |
| TV3 | Embedded IoT / Hardware |
| TV4 | AI Pipeline |

## Development Workflow

Project sử dụng:

- **Confluence** — Requirement analysis và project documentation.
- **Jira** — Planning, backlog và task management.
- **GitHub** — Source code, version control và collaboration.

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
Implementation
    ↓
Testing
    ↓
Integration
```

## Current Status

Project hiện đang trong giai đoạn:

**Requirements Analysis → SRS → Use Case Modeling**

Frontend prototype được phát triển song song bằng mock data để hỗ trợ quá trình xác định giao diện và luồng người dùng.

> SRS và các tài liệu thiết kế hiện vẫn ở trạng thái Draft và sẽ tiếp tục được cập nhật sau quá trình review của nhóm.