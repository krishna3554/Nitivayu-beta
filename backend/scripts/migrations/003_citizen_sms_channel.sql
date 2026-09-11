-- 003_citizen_sms_channel.sql (WP-9)
-- Opt-in citizen SMS channel: Fernet-encrypted phone, written at OTP-verify
-- time only when PHONE_FERNET_KEY is configured. Idempotent.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS phone_enc BYTEA;
