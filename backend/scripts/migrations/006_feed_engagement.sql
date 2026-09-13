-- 006_feed_engagement.sql
-- Civic engagement backing the public Reports Feed (/feed):
-- distinct "me too" (same-issue experience, feeds severity/dedup weight) and
-- "confirm" (third-party nearby verification, weighted separately), plus
-- moderated threaded comments. Idempotent.
--
-- Me-too reuses report_likes' voter identity contract
-- ('u:<sha256(sub)[:32]>' for signed-in accounts); anonymous 'a:' keys are
-- rejected on the new endpoints (read is free, acting needs an account).
-- The legacy report_likes table is kept for backwards compatibility.

CREATE TABLE IF NOT EXISTS report_confirmations (
    confirmation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    problem_id UUID NOT NULL REFERENCES problems(problem_id) ON DELETE CASCADE,
    voter_key VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_report_confirmations_voter UNIQUE (problem_id, voter_key)
);

CREATE INDEX IF NOT EXISTS ix_report_confirmations_problem ON report_confirmations(problem_id);

CREATE TABLE IF NOT EXISTS report_comments (
    comment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    problem_id UUID NOT NULL REFERENCES problems(problem_id) ON DELETE CASCADE,
    author_user_id VARCHAR(255) NOT NULL,
    author_name VARCHAR(255),
    body TEXT NOT NULL,
    parent_id UUID REFERENCES report_comments(comment_id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'visible',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_report_comments_problem ON report_comments(problem_id);
