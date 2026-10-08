# Software Requirements Specification

## SwiftletCare

**Project:** SwiftletCare  
**Document:** Software Requirements Specification  
**Version:** 0.1  
**Status:** Draft – Ready for Review  
**Last Updated:** 07/10/2026  

---

# 1. Introduction

## 1.1 Purpose

Tài liệu Software Requirements Specification (SRS) mô tả các yêu cầu chức năng, yêu cầu phi chức năng, quy tắc nghiệp vụ và các giao diện bên ngoài của hệ thống SwiftletCare.

SwiftletCare được xây dựng nhằm hỗ trợ tự động hóa việc giám sát và điều khiển môi trường nhà yến, theo dõi hoạt động chim yến bằng Computer Vision và phát hiện các mối đe dọa hoặc bất thường thông qua dữ liệu hình ảnh, âm thanh và IoT.

Tài liệu này là cơ sở cho các giai đoạn tiếp theo bao gồm Use Case Analysis, UML Modeling, System Architecture, Integration Design, Implementation và Testing.

## 1.2 Problem Statement

| Problem | Proposed Solution |
|---|---|
| Việc theo dõi nhiệt độ, độ ẩm và các điều kiện môi trường trong nhà yến còn phụ thuộc nhiều vào kiểm tra thủ công hoặc các cảm biến rời rạc. | Thu thập dữ liệu môi trường thông qua IoT và cung cấp khả năng giám sát gần thời gian thực. |
| Điều kiện môi trường không phù hợp có thể ảnh hưởng đến hoạt động và môi trường sống của chim yến. | Sử dụng cơ chế điều khiển tự động và thủ công đối với các thiết bị như phun sương, quạt và sưởi. |
| Khó theo dõi chính xác số lượng chim ra/vào nhà yến theo thời gian. | Sử dụng Computer Vision kết hợp Object Detection và Multi-Object Tracking để theo dõi và đếm chim ra/vào. |
| Khó phát hiện sớm thiên địch hoặc các bất thường trong nhà yến. | Sử dụng AI xử lý hình ảnh và tín hiệu âm thanh để hỗ trợ phát hiện các sự kiện bất thường. |
| Người quản lý khó theo dõi đồng thời dữ liệu môi trường, thiết bị và cảnh báo. | Cung cấp Web/Mobile Application tập trung dữ liệu giám sát, điều khiển, cảnh báo và phân tích. |

## 1.3 Scope

### In Scope

SwiftletCare bao gồm:

- Authentication và Role-Based Access Control.
- Quản lý nhà yến, khu vực và thiết bị.
- Thu thập dữ liệu môi trường từ IoT nodes.
- Giám sát môi trường gần thời gian thực.
- Điều khiển môi trường ở chế độ AUTO và MANUAL.
- Local automatic control tại IoT node.
- Theo dõi trạng thái thiết bị.
- Camera/AI-based swiftlet detection.
- Multi-Object Tracking.
- Entry/Exit Counting.
- Predator Detection.
- Audio/Anomaly Processing.
- Alert Management.
- Mobile Push Notification.
- Historical Data và Analytics.
- Web Application và Mobile Application.

### Out of Scope

Phiên bản hiện tại không đặt mục tiêu cung cấp:

- Chẩn đoán bệnh cho từng cá thể chim.
- Nhận dạng danh tính từng cá thể chim yến.
- Phát hiện tất cả các loại thiên địch có thể tồn tại.
- Dự báo chính xác sản lượng tổ yến bằng AI.
- Marketplace hoặc hệ thống thương mại điện tử.
- Payment.
- Shipping.
- Buyer/Sales Staff workflow.

---

# 2. Overall Description

## 2.1 Product Functions

SwiftletCare cung cấp các nhóm chức năng chính:

1. User & Access Management.
2. Farm, House & Zone Management.
3. Device Management.
4. Environmental Monitoring.
5. Environmental Control.
6. Swiftlet Entry/Exit Monitoring.
7. Threat & Anomaly Detection.
8. Alert & Notification.
9. Historical Data & Analytics.

## 2.2 User Classes and Actors

### Farm Owner

Farm Owner là người quản lý hoạt động của nhà yến.

Farm Owner có thể:

- Theo dõi tổng quan nhà yến.
- Theo dõi dữ liệu môi trường.
- Theo dõi trạng thái thiết bị.
- Cấu hình các tham số môi trường được phép.
- Điều khiển thiết bị theo quyền.
- Theo dõi số lượng chim ra/vào.
- Xem sự kiện AI và cảnh báo.
- Theo dõi dữ liệu lịch sử và phân tích.

### Technician

Technician chịu trách nhiệm giám sát và hỗ trợ vận hành các thiết bị IoT, cảm biến và thiết bị chấp hành trong nhà yến.

Technician có thể:

- Theo dõi trạng thái kết nối của thiết bị.
- Kiểm tra các sự cố kỹ thuật.
- Thực hiện các tác vụ cấu hình và bảo trì được phân quyền.
- Tiếp nhận và xử lý các cảnh báo liên quan.
- Thực hiện một số thao tác điều khiển nếu được RBAC cho phép.

Quyền truy cập của Technician được giới hạn theo vai trò và phạm vi nhà yến được phân công.

### Administrator

Administrator chịu trách nhiệm quản trị hệ thống.

Administrator có thể:

- Quản lý tài khoản người dùng.
- Quản lý vai trò và quyền truy cập.
- Quản lý tài nguyên hệ thống thuộc phạm vi quản trị.
- Quản lý cấu hình hệ thống.
- Theo dõi trạng thái tổng thể của hệ thống.

## 2.3 Background Components

Các thành phần xử lý nền có thể bao gồm:

- ESP32 Controller Node.
- Camera / AI Processing Node.
- Audio Processing Component.
- MQTT Broker.
- Backend Services.
- Telemetry Processing.
- Control Processing.
- Alert Processing.
- Notification Service.

Các thành phần trên không được xem là human actors trong Overall Use Case Diagram.

## 2.4 Operating Environment

Hệ thống dự kiến hoạt động trong môi trường:

- Web Application.
- Mobile Application.
- Backend Services.
- IoT/Edge devices.
- AI Processing Environment.
- Data Storage Services.
- MQTT infrastructure.
- Containerized deployment environment.

Các giao tiếp chính có thể bao gồm:

- HTTP/HTTPS.
- REST API.
- MQTT.
- WebSocket hoặc cơ chế realtime tương đương.

## 2.5 Constraints

| ID | Constraint |
|---|---|
| CON-01 | Hệ thống phải được thiết kế theo định hướng SOA và Microservices. |
| CON-02 | Hệ thống phải sử dụng API Gateway cho các Backend services phù hợp. |
| CON-03 | Backend API phải được tài liệu hóa bằng OpenAPI/Swagger. |
| CON-04 | Các thành phần server-side phải hỗ trợ triển khai bằng Docker. |
| CON-05 | Redis phải được sử dụng cho các use case cache/state phù hợp. |
| CON-06 | Hệ thống phải hỗ trợ Firebase Cloud Messaging cho Mobile Push Notification. |
| CON-07 | Apache NiFi phải được sử dụng cho các luồng đồng bộ dữ liệu được xác định trong thiết kế. |
| CON-08 | MQTT được sử dụng cho giao tiếp phù hợp giữa IoT subsystem và Backend. |
| CON-09 | IoT node phải tiếp tục local automatic control khi mất kết nối Cloud. |
| CON-10 | AI processing phải ưu tiên lightweight models phù hợp với định hướng Edge AI. |

---

# 3. Functional Requirements

## 3.1 User & Access Management

| ID | Requirement | Priority |
|---|---|---|
| FR-UAM-01 | Hệ thống phải cho phép người dùng đăng nhập bằng tài khoản hợp lệ. | Must |
| FR-UAM-02 | Hệ thống phải cho phép người dùng đăng xuất. | Must |
| FR-UAM-03 | Hệ thống phải hỗ trợ RBAC cho Farm Owner, Technician và Administrator. | Must |
| FR-UAM-04 | Hệ thống phải giới hạn quyền truy cập theo phạm vi nhà yến/tài nguyên được phân quyền. | Must |
| FR-UAM-05 | Administrator phải có khả năng quản lý người dùng và vai trò. | Must |

## 3.2 Farm, House & Zone Management

| ID | Requirement | Priority |
|---|---|---|
| FR-FHM-01 | Farm Owner phải có khả năng quản lý thông tin nhà yến thuộc phạm vi được phép. | Must |
| FR-FHM-02 | Hệ thống phải hỗ trợ tổ chức nhà yến thành các Zone/Floor phù hợp. | Must |
| FR-FHM-03 | Hệ thống phải hỗ trợ liên kết IoT devices, sensors, actuators và cameras với nhà yến/khu vực tương ứng. | Must |
| FR-FHM-04 | Người dùng được phân quyền phải có khả năng xem thông tin và trạng thái của nhà yến/khu vực. | Must |

## 3.3 Device Management

| ID | Requirement | Priority |
|---|---|---|
| FR-DEV-01 | Hệ thống phải có khả năng đăng ký hoặc nhận dạng IoT nodes/devices. | Must |
| FR-DEV-02 | Thiết bị phải có khả năng được gán vào nhà yến/khu vực tương ứng. | Must |
| FR-DEV-03 | Hệ thống phải theo dõi trạng thái online/offline của thiết bị. | Must |
| FR-DEV-04 | Farm Owner và Technician phải có khả năng xem trạng thái thiết bị trong phạm vi được phân quyền. | Must |
| FR-DEV-05 | Technician nên có khả năng thực hiện các thao tác kiểm tra, cấu hình và chẩn đoán thiết bị phù hợp. | Should |
| FR-DEV-06 | Hệ thống nên hỗ trợ cấu hình từ xa các tham số phù hợp của IoT node. | Should |

## 3.4 Environmental Monitoring

| ID | Requirement | Priority |
|---|---|---|
| FR-ENV-01 | Hệ thống phải nhận dữ liệu môi trường từ IoT subsystem. | Must |
| FR-ENV-02 | Hệ thống phải hỗ trợ tối thiểu dữ liệu nhiệt độ và độ ẩm. | Must |
| FR-ENV-03 | Hệ thống nên hỗ trợ dữ liệu ánh sáng, chất lượng không khí và âm thanh khi phần cứng tương ứng được triển khai. | Should |
| FR-ENV-04 | Hệ thống phải hiển thị trạng thái môi trường hiện tại theo nhà yến/khu vực. | Must |
| FR-ENV-05 | Hệ thống phải cung cấp dữ liệu môi trường gần thời gian thực cho Web/Mobile. | Must |
| FR-ENV-06 | Hệ thống phải lưu dữ liệu cần thiết phục vụ lịch sử và phân tích xu hướng. | Must |
| FR-ENV-07 | Hệ thống phải thể hiện trạng thái stale/offline khi dữ liệu không còn được xác nhận là dữ liệu hiện tại. | Must |

## 3.5 Environmental Control

| ID | Requirement | Priority |
|---|---|---|
| FR-CTRL-01 | Hệ thống phải hỗ trợ chế độ AUTO và MANUAL. | Must |
| FR-CTRL-02 | Người dùng được phân quyền phải có khả năng gửi lệnh điều khiển từ xa tới thiết bị chấp hành. | Must |
| FR-CTRL-03 | Hệ thống phải cho phép cấu hình các threshold/control parameters phù hợp. | Must |
| FR-CTRL-04 | IoT node phải thực thi local control logic. | Must |
| FR-CTRL-05 | Local automatic control phải tiếp tục hoạt động khi kết nối Cloud không khả dụng. | Must |
| FR-CTRL-06 | IoT subsystem phải đồng bộ trạng thái actuator và control mode với Backend khi có kết nối. | Must |
| FR-CTRL-07 | Remote control phải tuân thủ authorization và các giới hạn an toàn được cấu hình. | Must |

## 3.6 Swiftlet Entry/Exit Monitoring

| ID | Requirement | Priority |
|---|---|---|
| FR-AI-01 | AI subsystem phải có khả năng nhận hình ảnh/video từ camera source. | Must |
| FR-AI-02 | AI subsystem phải có khả năng phát hiện chim yến trong dữ liệu hình ảnh. | Must |
| FR-AI-03 | AI subsystem phải hỗ trợ Multi-Object Tracking để duy trì thông tin đối tượng theo thời gian. | Must |
| FR-AI-04 | Hệ thống phải xác định hướng di chuyển của chim qua khu vực đếm được cấu hình. | Must |
| FR-AI-05 | Hệ thống phải tính số lượng chim vào và ra. | Must |
| FR-AI-06 | Kết quả đếm phải được liên kết với camera/node và timestamp tương ứng. | Must |
| FR-AI-07 | Farm Owner phải có khả năng xem số lượng và thống kê hoạt động chim theo thời gian. | Must |
| FR-AI-08 | Hệ thống phải hỗ trợ Live Camera/Image khi camera source và điều kiện triển khai cho phép. | Must |

## 3.7 Threat & Anomaly Detection

| ID | Requirement | Priority |
|---|---|---|
| FR-THR-01 | AI subsystem phải có khả năng phát hiện đối tượng thiên địch thuộc tập class được hệ thống hỗ trợ. | Must |
| FR-THR-02 | Hệ thống phải tạo anomaly event khi detection đáp ứng confidence threshold được cấu hình. | Must |
| FR-THR-03 | Detection event phải chứa thông tin cần thiết như object class, confidence, bounding box, timestamp và camera/node identifier. | Must |
| FR-THR-04 | Hệ thống phải hỗ trợ lưu snapshot/frame làm bằng chứng cho AI event. | Must |
| FR-THR-05 | Web/Mobile phải có khả năng hiển thị AI event, snapshot, bounding box và confidence khi dữ liệu có sẵn. | Must |
| FR-THR-06 | Hệ thống nên hỗ trợ phân tích biến động bất thường của số lượng chim. | Should |
| FR-THR-07 | Hệ thống phải hỗ trợ xử lý tín hiệu âm thanh nhằm phát hiện các bất thường hoặc sự cố hệ thống âm thanh; phương pháp và tiêu chí cụ thể được xác định trong giai đoạn thiết kế. | Must |

## 3.8 Alert & Notification

| ID | Requirement | Priority |
|---|---|---|
| FR-ALT-01 | Hệ thống phải tạo alert đối với các điều kiện bất thường được cấu hình. | Must |
| FR-ALT-02 | Alert phải chứa thông tin phù hợp như loại, thời gian, nguồn và mức độ nghiêm trọng. | Must |
| FR-ALT-03 | Hệ thống phải hỗ trợ environmental, device và AI alerts. | Must |
| FR-ALT-04 | Farm Owner và Technician phải có khả năng xem danh sách và chi tiết alert trong phạm vi được phân quyền. | Must |
| FR-ALT-05 | Người dùng được phân quyền phải có khả năng cập nhật trạng thái xử lý alert. | Must |
| FR-ALT-06 | Hệ thống phải hỗ trợ Mobile Push Notification. | Must |
| FR-ALT-07 | Predator event phù hợp phải có khả năng kích hoạt Backend gửi command tới IoT node để thực hiện hành động cảnh báo/xua đuổi được cấu hình. | Must |

## 3.9 Historical Data & Analytics

| ID | Requirement | Priority |
|---|---|---|
| FR-ANA-01 | Người dùng được phân quyền phải có khả năng truy vấn dữ liệu môi trường lịch sử theo khoảng thời gian. | Must |
| FR-ANA-02 | Hệ thống phải hiển thị xu hướng dữ liệu môi trường. | Must |
| FR-ANA-03 | Hệ thống phải lưu và truy vấn lịch sử Entry/Exit Counting. | Must |
| FR-ANA-04 | Hệ thống phải cung cấp thống kê hoạt động chim theo thời gian. | Must |
| FR-ANA-05 | Hệ thống phải lưu và truy vấn lịch sử anomaly/alert. | Must |
| FR-ANA-06 | Hệ thống nên hỗ trợ tổng hợp dữ liệu phục vụ đánh giá xu hướng hoạt động của nhà yến. | Should |

---

# 4. Non-Functional Requirements

## 4.1 Performance

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| NFR-PER-01 | Hệ thống phải cung cấp dữ liệu cảm biến với độ trễ phù hợp cho giám sát gần thời gian thực. | Dữ liệu mới được hiển thị trên Dashboard trong vòng ≤ 2 giây trong điều kiện vận hành bình thường. |
| NFR-PER-02 | Kết quả AI quan trọng phải được chuyển tới người dùng trong thời gian gần thực. | Count metrics và camera anomaly alerts có khả năng đến Mobile trong khoảng 3–5 giây. |
| NFR-PER-03 | Remote control phải cung cấp phản hồi trạng thái sau khi lệnh được xử lý. | Giao diện nhận được trạng thái thực thi/kết quả sau khi Backend và IoT xử lý. |

## 4.2 Reliability & Offline Resiliency

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| NFR-REL-01 | IoT node phải tiếp tục local automatic control khi mất Internet hoặc Backend/Cloud. | AUTO control tiếp tục hoạt động trong thời gian cloud connection bị gián đoạn. |
| NFR-REL-02 | IoT node phải có khả năng tự reconnect sau khi Wi-Fi/MQTT bị gián đoạn. | Node tự thực hiện reconnect mà không yêu cầu restart thủ công. |
| NFR-REL-03 | Việc mất Cloud connection không được làm dừng control loop đang thực thi tại IoT node. | Local control hoạt động độc lập với trạng thái cloud connection. |
| NFR-REL-04 | Hệ thống phải có khả năng nhận biết trạng thái online/offline của IoT node. | Backend/UI có khả năng xác định thiết bị mất kết nối. |

## 4.3 Security

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| NFR-SEC-01 | Các chức năng được bảo vệ phải yêu cầu authentication. | Người dùng chưa xác thực không truy cập được chức năng yêu cầu đăng nhập. |
| NFR-SEC-02 | Hệ thống phải kiểm soát quyền dựa trên role và resource scope. | Farm Owner, Technician và Administrator chỉ thực hiện được thao tác được cấp quyền. |
| NFR-SEC-03 | Backend phải thực thi authorization cho các API được bảo vệ. | Frontend visibility không phải cơ chế authorization duy nhất. |
| NFR-SEC-04 | Network communication trong production phải hỗ trợ cơ chế truyền dữ liệu an toàn phù hợp. | Public API/device communication nhạy cảm hỗ trợ HTTPS/TLS hoặc cơ chế tương đương. |
| NFR-SEC-05 | Sensitive authentication credentials không được lưu ở dạng plaintext. | Password/credential được bảo vệ bằng cơ chế phù hợp trước khi lưu. |

## 4.4 Resource & Bandwidth Efficiency

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| NFR-EFF-01 | AI pipeline phải ưu tiên lightweight models phù hợp với Edge AI. | Model có khả năng triển khai trên môi trường Edge mục tiêu hoặc môi trường mô phỏng tương ứng. |
| NFR-EFF-02 | Hệ thống phải hạn chế truyền video liên tục lên Cloud khi không cần thiết. | Ưu tiên aggregated counts, AI events và snapshots. |
| NFR-EFF-03 | Multimedia data phải được quản lý nhằm hạn chế bandwidth/storage không cần thiết. | Image/video/audio chỉ được truyền và lưu theo nhu cầu chức năng. |

## 4.5 Maintainability & Modularity

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| NFR-MNT-01 | Hệ thống phải được tổ chức theo định hướng SOA/Microservices. | Backend capabilities chính được phân chia thành các service/component có trách nhiệm rõ ràng. |
| NFR-MNT-02 | Detection, Tracking, Counting và Anomaly Processing phải được modular hóa ở mức hợp lý. | AI model có thể retrain/thay thế mà không yêu cầu thay đổi Frontend nếu contract không thay đổi. |
| NFR-MNT-03 | Interface giữa các subsystem phải được định nghĩa rõ ràng. | API, MQTT messages và event contracts được tài liệu hóa trước Integration. |
| NFR-MNT-04 | Backend API phải được tài liệu hóa bằng OpenAPI/Swagger. | API contract có OpenAPI documentation phục vụ integration. |

## 4.6 Compatibility & Deployment

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| NFR-COM-01 | Web Application phải hỗ trợ các trình duyệt hiện đại phổ biến. | Các chức năng chính hoạt động trên các trình duyệt mục tiêu của nhóm. |
| NFR-COM-02 | Hệ thống phải hỗ trợ Web và Mobile Application. | Backend cung cấp interface phù hợp cho cả hai client. |
| NFR-COM-03 | Các server-side components phải có khả năng triển khai bằng Docker. | Các service cần thiết có container configuration phục vụ development/deployment. |
| NFR-COM-04 | Client-facing Backend services phải được tổ chức thông qua API Gateway theo kiến trúc được thiết kế. | Web/Mobile truy cập service thông qua interface/gateway được xác định. |

## 4.7 AI Quality

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| NFR-AIQ-01 | Object Detection model phải được đánh giá trên test data độc lập. | Báo cáo ít nhất Precision và Recall. |
| NFR-AIQ-02 | Entry/Exit Counting phải được đánh giá với verified ground truth. | Kết quả hệ thống được so sánh với số đếm thực tế/thủ công. |
| NFR-AIQ-03 | AI pipeline phải ghi nhận đủ thông tin cần thiết để đánh giá detection result. | Result chứa class, confidence và object location information. |
| NFR-AIQ-04 | Các AI metrics bổ sung phải được xác định trong AI Design/Evaluation. | Có thể bao gồm mAP, MAE/counting accuracy, tracking metrics và inference latency. |

---

# 5. Business Rules

| ID | Business Rule |
|---|---|
| BR-01 | Mỗi người dùng phải được gán một role phù hợp gồm Farm Owner, Technician hoặc Administrator; quyền truy cập được xác định theo role và resource scope. |
| BR-02 | Farm Owner chỉ được quản lý/giám sát các nhà yến thuộc phạm vi được cấp quyền; Technician chỉ truy cập các nhà yến/thiết bị được phân công. |
| BR-03 | Mỗi IoT node, camera hoặc managed device phải có identifier duy nhất và được liên kết với nhà yến/khu vực tương ứng trước khi dữ liệu được sử dụng chính thức. |
| BR-04 | Environmental Control phải hỗ trợ AUTO và MANUAL. Trong AUTO, IoT node thực thi local control logic; trong MANUAL, authorized remote commands được Backend chuyển tới IoT node. |
| BR-05 | Mất Backend/Cloud connection không được làm mất local automatic control tại IoT node. |
| BR-06 | Remote control command chỉ được thực hiện bởi authorized user và phải tuân thủ configured safety limits. |
| BR-07 | Telemetry, AI result và anomaly event phải được liên kết với source identifier và timestamp để có thể truy vết. |
| BR-08 | AI detection chỉ tạo predator alert khi đối tượng thuộc supported class và confidence đáp ứng configured threshold. |
| BR-09 | Predator event đủ điều kiện có thể kích hoạt Backend gửi command tới IoT node để thực hiện configured alarm/deterrent action. |
| BR-10 | Alert phải duy trì trạng thái xử lý để phân biệt cảnh báo mới và cảnh báo đã được xử lý. |
| BR-11 | Dữ liệu từ thiết bị mất kết nối không được hiển thị như dữ liệu hiện tại mà không có stale/offline indication. |
| BR-12 | Environmental thresholds, AI confidence thresholds và control parameters được xem là configurable values và không hard-code thành business rule cố định trừ khi được team xác nhận. |

---

# 6. External Interface Requirements

## 6.1 User Interfaces

| ID | Interface Requirement |
|---|---|
| UI-01 | Hệ thống phải cung cấp Login Interface cho Farm Owner, Technician và Administrator. |
| UI-02 | UI phải hiển thị chức năng và dữ liệu phù hợp với role/resource scope. |
| UI-03 | Farm Owner phải có Dashboard thể hiện trạng thái chính của nhà yến, môi trường, thiết bị, hoạt động chim và cảnh báo. |
| UI-04 | Hệ thống phải cung cấp UI giám sát temperature, humidity và các environmental parameters được hỗ trợ theo house/zone. |
| UI-05 | Hệ thống phải cung cấp UI hiển thị device status và các control operation được phân quyền. |
| UI-06 | Hệ thống phải cung cấp UI theo dõi Entry/Exit Counts và các AI results liên quan. |
| UI-07 | Hệ thống phải hiển thị AI anomaly event, snapshot, bounding box và confidence khi dữ liệu có sẵn. |
| UI-08 | Hệ thống phải cung cấp UI xem và xử lý alerts. |
| UI-09 | Hệ thống phải cung cấp history/charts phục vụ environmental và bird activity analytics. |
| UI-10 | Technician phải có UI phù hợp để theo dõi, kiểm tra và chẩn đoán assigned devices. |
| UI-11 | Administrator phải có UI quản lý users, roles/access và system resources thuộc phạm vi quản trị. |
| UI-12 | UI phải thể hiện rõ loading, error, offline và stale states. |

## 6.2 Hardware Interfaces

| ID | Interface Requirement |
|---|---|
| HW-01 | Hệ thống phải hỗ trợ IoT controller dựa trên ESP32 hoặc phần cứng tương đương được lựa chọn. |
| HW-02 | IoT node phải giao tiếp với temperature/humidity sensors được triển khai. |
| HW-03 | IoT node nên hỗ trợ light, air-quality và audio sensors khi được triển khai. |
| HW-04 | IoT node phải có khả năng điều khiển các actuators phục vụ environmental control như misting, ventilation fan và heater. |
| HW-05 | IoT node phải hỗ trợ configured alarm/deterrent device khi chức năng tương ứng được triển khai. |
| HW-06 | AI subsystem phải có khả năng nhận image/video từ camera tại khu vực giám sát. |
| HW-07 | Camera/node phải có identifier để AI result có thể liên kết với data source. |
| HW-08 | Hardware deployment phải cho phép IoT node tiếp tục local automatic control khi Cloud không khả dụng. |

## 6.3 Software Interfaces

| ID | Interface | Requirement |
|---|---|---|
| SW-01 | Web/Mobile ↔ Backend | Web và Mobile phải giao tiếp với Backend thông qua API. |
| SW-02 | Realtime Interface | Backend phải cung cấp cơ chế truyền dữ liệu/trạng thái gần thời gian thực tới client. |
| SW-03 | Backend ↔ IoT | Backend phải nhận telemetry và gửi command/configuration tới IoT subsystem. |
| SW-04 | AI ↔ Backend | AI subsystem phải cung cấp counting results, detection results và anomaly events cho Backend. |
| SW-05 | Backend ↔ Notification | Backend phải tích hợp Mobile Push Notification. |
| SW-06 | Backend ↔ Cache | Redis phải được sử dụng cho các cache/state use cases phù hợp. |
| SW-07 | API Documentation | Backend API phải được mô tả bằng OpenAPI/Swagger. |
| SW-08 | Data Synchronization | Apache NiFi phải được sử dụng cho data synchronization flows được xác định trong architecture. |
| SW-09 | AI Model Interface | AI pipeline phải duy trì interface ổn định để model có thể retrain/thay thế mà không phá vỡ Backend/Frontend contract. |
| SW-10 | API Gateway | Client-facing Backend services phải được tổ chức thông qua API Gateway. |

## 6.4 Communication Interfaces

| ID | Interface Requirement |
|---|---|
| COM-01 | Web/Mobile và Backend phải giao tiếp qua HTTP/HTTPS với structured data phù hợp, chủ yếu JSON. |
| COM-02 | Backend phải cung cấp REST API cho request/response operations của Web/Mobile. |
| COM-03 | Hệ thống phải hỗ trợ WebSocket hoặc realtime mechanism tương đương được nhóm thống nhất. |
| COM-04 | IoT subsystem và Backend phải sử dụng MQTT cho telemetry, device status, commands và configuration messages phù hợp. |
| COM-05 | MQTT messages phải chứa đủ source identifier, timestamp và data cần thiết cho processing/tracing. |
| COM-06 | AI subsystem và Backend phải sử dụng defined interface cho counting results và anomaly events. |
| COM-07 | Các subsystem interfaces phải thống nhất cách biểu diễn timestamp, identifiers, units và event types. |
| COM-08 | Production connections chứa sensitive information hoặc commands phải sử dụng transport protection phù hợp như HTTPS/TLS và MQTT over TLS. |
| COM-09 | Endpoint, MQTT topic, payload schema, error code và event contract chi tiết phải được tài liệu hóa trong Technical & Integration Design. |

---

# 7. Open Questions

| ID | Open Question | Target Phase |
|---|---|---|
| OQ-01 | AI inference sẽ triển khai tại Edge, Server/Cloud hay theo Hybrid Architecture? | System Architecture |
| OQ-02 | Camera hardware chính thức là ESP32-CAM, IP Camera hay phương án khác? | Hardware & AI Design |
| OQ-03 | Entry/Exit Counting sử dụng Virtual Line hay Zone/Polygon Counting? | AI Design |
| OQ-04 | Audio Processing sử dụng phương pháp/model nào và tiêu chí đánh giá cụ thể là gì? | AI Design |
| OQ-05 | Danh sách predator classes bắt buộc cuối cùng gồm những đối tượng nào dựa trên khả năng dataset? | AI Design |
| OQ-06 | Các environmental default thresholds chính thức là bao nhiêu và nguồn xác nhận là gì? | IoT/Domain Design |
| OQ-07 | Technician được phép thực hiện những Manual Control operations nào? | RBAC / Use Case Design |
| OQ-08 | OTA Firmware, PDF/Excel Report, Email/SMS và Health Score có thuộc implementation scope hay chỉ là future enhancement? | Backlog Refinement |

---

# 8. Requirement Review Status

SRS v0.1 đã tổng hợp yêu cầu từ các module Frontend/Mobile, Backend, IoT/Hardware và AI Pipeline.

Các nguyên tắc đã được thống nhất trong bản draft:

- Human actors gồm Farm Owner, Technician và Administrator.
- `Operator` được chuẩn hóa thành `Technician`.
- Backend chịu trách nhiệm configuration, authorization, remote commands, monitoring và history.
- IoT node chịu trách nhiệm sensor acquisition, actuator execution, local control và offline operation.
- Environmental thresholds được cấu hình thay vì hard-code trong Main SRS.
- Audio Processing vẫn thuộc phạm vi hệ thống.
- Optional features chưa được team phê duyệt không được xem là Must requirements.
- Các quyết định implementation chưa được chốt được duy trì trong Open Questions.

Tài liệu vẫn ở trạng thái **Draft – Ready for Review** cho đến khi hoàn thành Team Requirement Review.

---

# 9. Traceability Direction

Các artifact tiếp theo phải duy trì traceability theo hướng:

```text
Requirement
    ↓
Use Case
    ↓
Acceptance Criteria
    ↓
UML / Design
    ↓
Jira Story / Task
    ↓
Git Branch / Pull Request
    ↓
Test Case
```

Detailed Traceability Matrix sẽ được xây dựng sau khi Use Case Model và Product Backlog được hoàn thiện.

---

# Document History

| Version | Date | Status | Description |
|---|---|---|---|
| 0.1 | 07/10/2026 | Draft – Ready for Review | Initial consolidated SRS based on project requirements and module requirement analysis. |