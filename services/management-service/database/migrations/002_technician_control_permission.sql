ALTER TABLE technician_assignments
ADD COLUMN control_permission VARCHAR(20) NOT NULL DEFAULT 'MONITOR'
CHECK (control_permission IN ('MONITOR', 'OPERATE'));