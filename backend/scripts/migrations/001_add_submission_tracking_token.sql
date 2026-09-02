ALTER TABLE submissions
  ADD COLUMN IF NOT EXISTS tracking_token VARCHAR(64) UNIQUE;

CREATE INDEX IF NOT EXISTS idx_submissions_tracking_token
  ON submissions(tracking_token);
