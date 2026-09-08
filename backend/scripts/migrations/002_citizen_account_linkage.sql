-- 002_citizen_account_linkage.sql (WP-1, WP-9)
-- Account-scoped submission ownership + citizen profile/notification prefs.
-- Idempotent: safe to run repeatedly on an existing database.

ALTER TABLE submissions
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(user_id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_submissions_user_id ON submissions(user_id);

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS language_pref VARCHAR(10);
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS notify_sms BOOLEAN NOT NULL DEFAULT FALSE;
