-- 005_civic_feed.sql
-- Likes backing the public civic feed (GET /feed, POST /feed/{id}/like).
-- Idempotent. voter_key is 'u:<sha256(sub)[:32]>' for signed-in accounts or
-- 'a:<uuid hex>' for anonymous browser tokens; the unique pair makes
-- like/unlike idempotent and blocks double-voting at the database level.

CREATE TABLE IF NOT EXISTS report_likes (
    like_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    problem_id UUID NOT NULL REFERENCES problems(problem_id) ON DELETE CASCADE,
    voter_key VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_report_likes_voter UNIQUE (problem_id, voter_key)
);

CREATE INDEX IF NOT EXISTS ix_report_likes_problem ON report_likes(problem_id);
