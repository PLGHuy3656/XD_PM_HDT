export const initialAdminUsers = [
  {
    id: 'USR-001',
    name: 'Nguyễn Văn Minh',
    email: 'minh.owner@nestmate.vn',
    phone: '090 123 4567',
    role: 'FARM_OWNER',
    status: 'ACTIVE',
    joinedAt: '12/08/2026',
    lastActive: 'Hôm nay, 09:42',
  },
  {
    id: 'USR-002',
    name: 'Trần Hoàng Nam',
    email: 'nam.owner@nestmate.vn',
    phone: '091 245 7812',
    role: 'FARM_OWNER',
    status: 'ACTIVE',
    joinedAt: '18/08/2026',
    lastActive: 'Hôm nay, 08:15',
  },
  {
    id: 'USR-003',
    name: 'Nguyễn Minh Khang',
    email: 'tech@swiftletcare.dev',
    phone: '090 345 6789',
    role: 'TECHNICIAN',
    status: 'ACTIVE',
    joinedAt: '22/08/2026',
    lastActive: 'Hôm nay, 10:03',
  },
  {
    id: 'USR-004',
    name: 'Trần Quốc Huy',
    email: 'huy.technician@swiftletcare.dev',
    phone: '091 456 7820',
    role: 'TECHNICIAN',
    status: 'ACTIVE',
    joinedAt: '27/08/2026',
    lastActive: 'Hôm qua, 17:26',
  },
  {
    id: 'USR-005',
    name: 'Lê Thanh Hà',
    email: 'ha.owner@nestmate.vn',
    phone: '093 882 1190',
    role: 'FARM_OWNER',
    status: 'LOCKED',
    joinedAt: '04/09/2026',
    lastActive: '18/10/2026',
  },
  {
    id: 'USR-006',
    name: 'Phạm Lê Gia Huy',
    email: 'admin@swiftletcare.dev',
    phone: '090 888 3656',
    role: 'ADMIN',
    status: 'ACTIVE',
    joinedAt: '01/08/2026',
    lastActive: 'Đang hoạt động',
  },
]

export const userRoleLabels = {
  FARM_OWNER: 'Farm Owner',
  TECHNICIAN: 'Technician',
  ADMIN: 'Administrator',
}

export const userStatusLabels = {
  ACTIVE: 'Đang hoạt động',
  LOCKED: 'Đã khóa',
}
