
-- Seed Demo Users
INSERT INTO users (id, email, full_name, phone, status, password_hash) VALUES
('574e1fc8-85f3-4a1e-972b-18aaf31e1044', 'admin.demo@nestmate.dev', 'Quản trị viên Demo', NULL, 'ACTIVE', '$argon2id$v=19$m=65536,t=3,p=4$BU1jY4U4Hf3BxB/5t5K2PA$QWzZeqcBxPNTl0ajQHU/LCTPh1kyh5I83h1dKcz2ReM'),
('d632d08d-2a47-46f0-8798-83fd733024c3', 'owner.a.demo@nestmate.dev', 'Chủ trại Demo A', NULL, 'ACTIVE', '$argon2id$v=19$m=65536,t=3,p=4$LdqkCCy8EnAZazzb8JKRWA$k+PoXzMUdV9KARN6+SEREI7B1pqsYTuuyACw3hOrp2o'),
('19072e30-d339-4ac8-8715-01340462aca1', 'owner.b.demo@nestmate.dev', 'Chủ trại Demo B', NULL, 'ACTIVE', '$argon2id$v=19$m=65536,t=3,p=4$P+BDfRJ0hDxbyV8wr4PagQ$JpOjl21iZl2W1PTZAOiRGI/RqmmuMZDuy7MVd7u1jhI'),
('15e6f30f-350a-4c66-b4be-e22ab03b85dc', 'tech.a.demo@nestmate.dev', 'Kỹ thuật viên Demo A', NULL, 'ACTIVE', '$argon2id$v=19$m=65536,t=3,p=4$T0iC0mX+/By9gL4eBTO0yA$EFJF8SqqjjxQ6ywpXCArCJxeGdxMpJiqAJcc289gByA')
ON CONFLICT (id) DO NOTHING;

-- Seed Roles
INSERT INTO roles (name, description) VALUES
('ADMIN', 'System Administrator'),
('FARM_OWNER', 'Farm Owner with full farm management access'),
('TECHNICIAN', 'Technician maintaining devices and operations')
ON CONFLICT (name) DO NOTHING;

-- Seed User Roles
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r WHERE u.email = 'admin.demo@nestmate.dev' AND r.name = 'ADMIN'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r WHERE u.email = 'owner.a.demo@nestmate.dev' AND r.name = 'FARM_OWNER'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r WHERE u.email = 'owner.b.demo@nestmate.dev' AND r.name = 'FARM_OWNER'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM users u, roles r WHERE u.email = 'tech.a.demo@nestmate.dev' AND r.name = 'TECHNICIAN'
ON CONFLICT DO NOTHING;

-- Seed Farms
INSERT INTO farms (id, farm_code, name, address, status, owner_id) VALUES
('a18d8eee-cb1a-4b00-b375-d505eb8128d7', 'DEMO-FARM-01', 'Nhà yến Demo 01', 'Địa chỉ demo 01', 'ACTIVE', 'd632d08d-2a47-46f0-8798-83fd733024c3'),
('f8fc4fa7-0d27-4e0b-89c0-e676e0e73469', 'DEMO-FARM-02', 'Nhà yến Demo 02', 'Địa chỉ demo 02', 'ACTIVE', '19072e30-d339-4ac8-8715-01340462aca1')
ON CONFLICT (id) DO NOTHING;

-- Seed Zones
INSERT INTO zones (id, farm_id, zone_code, name) VALUES
('7122bcb8-9ce9-46bc-a640-a1060788b809', 'a18d8eee-cb1a-4b00-b375-d505eb8128d7', 'Z01', 'Tầng 1'),
('11d1ea50-ed24-45b8-9eb7-d538a214fe72', 'a18d8eee-cb1a-4b00-b375-d505eb8128d7', 'Z02', 'Tầng 2'),
('d63e8782-023c-486a-a8fb-4127a70219f7', 'f8fc4fa7-0d27-4e0b-89c0-e676e0e73469', 'Z01', 'Tầng 1')
ON CONFLICT (id) DO NOTHING;

-- Seed Devices
INSERT INTO devices (id, node_id, farm_id, zone_id, name, device_type, is_active, metadata_version) VALUES
('e094d4f5-8b66-4ce4-85fe-4f0f765b2fd6', 'SWC-DEMO-NODE-001', 'a18d8eee-cb1a-4b00-b375-d505eb8128d7', '7122bcb8-9ce9-46bc-a640-a1060788b809', 'ESP32 môi trường Tầng 1', 'ENVIRONMENT_MONITOR', TRUE, 1),
('bd88fc1f-a528-4a29-8549-2c4411ac9135', 'SWC-DEMO-NODE-002', 'f8fc4fa7-0d27-4e0b-89c0-e676e0e73469', 'd63e8782-023c-486a-a8fb-4127a70219f7', 'ESP32 môi trường Demo 02', 'ENVIRONMENT_MONITOR', TRUE, 1),
('c0000001-0000-0000-0000-000000000001', 'CAM-01', 'a18d8eee-cb1a-4b00-b375-d505eb8128d7', NULL, 'Camera AI Lối Vào', 'CAMERA', TRUE, 1),
('c0000002-0000-0000-0000-000000000002', 'CAM-02', 'f8fc4fa7-0d27-4e0b-89c0-e676e0e73469', NULL, 'Camera AI Chuồng Lượn', 'CAMERA', TRUE, 1)
ON CONFLICT (id) DO NOTHING;

-- Seed Technician Profile & Assignments
INSERT INTO technicians (id, full_name, email, phone, status) VALUES
('15e6f30f-350a-4c66-b4be-e22ab03b85dc', 'Kỹ thuật viên Demo A', 'tech.a.demo@nestmate.dev', '0903333333', 'ACTIVE')
ON CONFLICT (id) DO NOTHING;

INSERT INTO technician_assignments (technician_id, farm_id) VALUES
('15e6f30f-350a-4c66-b4be-e22ab03b85dc', 'a18d8eee-cb1a-4b00-b375-d505eb8128d7'),
('15e6f30f-350a-4c66-b4be-e22ab03b85dc', 'f8fc4fa7-0d27-4e0b-89c0-e676e0e73469')
ON CONFLICT DO NOTHING;
