BEGIN;

CREATE TABLE IF NOT EXISTS public.bird_track_points (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    point_key CHAR(64) NOT NULL UNIQUE,
    camera_id VARCHAR(100) NOT NULL,
    track_id BIGINT NOT NULL CHECK (track_id >= 0),
    object_class VARCHAR(80) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL
        CHECK (confidence >= 0 AND confidence <= 1),
    observed_at TIMESTAMPTZ NOT NULL,
    center_x DOUBLE PRECISION NOT NULL CHECK (center_x >= 0),
    center_y DOUBLE PRECISION NOT NULL CHECK (center_y >= 0),
    bbox JSONB NOT NULL,
    farm_id UUID NOT NULL,
    farm_name VARCHAR(255) NOT NULL,
    zone_id UUID,
    zone_name VARCHAR(255),
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bird_track_points_camera_time
    ON public.bird_track_points (camera_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_bird_track_points_track_time
    ON public.bird_track_points (camera_id, track_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_bird_track_points_farm_time
    ON public.bird_track_points (farm_id, observed_at DESC);

COMMIT;
