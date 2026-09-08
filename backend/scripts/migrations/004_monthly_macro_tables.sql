-- 004_monthly_macro_tables.sql (WP-11)
-- Tables backing the repaired MonthlyMacroTriageWorkflow. Idempotent.
-- pgvector extension + init_db.sql already provide VECTOR support.

CREATE TABLE IF NOT EXISTS theme_centroids (
    category VARCHAR(100) PRIMARY KEY,
    embedding VECTOR(384) NOT NULL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS seasonal_weights (
    month INTEGER PRIMARY KEY CHECK (month BETWEEN 1 AND 12),
    theme_weights JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
