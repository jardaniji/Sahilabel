-- Persistent inspector review audit history.
CREATE TABLE IF NOT EXISTS inspector_reviews (
    id SERIAL PRIMARY KEY,
    inspection_id VARCHAR(64) NOT NULL,
    reviewer VARCHAR(128) NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL,
    automated_decision JSONB NOT NULL,
    inspector_decision VARCHAR(16) NOT NULL CHECK (inspector_decision IN ('CONFIRMED', 'OVERRIDDEN', 'PENDING')),
    reason TEXT,
    field_confirmations JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_inspector_reviews_inspection_id ON inspector_reviews(inspection_id);
