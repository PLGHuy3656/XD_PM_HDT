CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_telemetry_device_recorded_at
    ON public.telemetry (device_id, recorded_at DESC);
