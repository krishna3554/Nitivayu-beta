-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 1. Citizens Table
CREATE TABLE citizens (
    citizen_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_encrypted BYTEA NOT NULL,
    email_encrypted BYTEA,
    language_pref VARCHAR(10) DEFAULT 'hi', -- 'hi', 'en', 'hi-Latn'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Submissions Table (Raw intake)
CREATE TABLE submissions (
    submission_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    citizen_id UUID REFERENCES citizens(citizen_id) ON DELETE SET NULL,
    raw_text TEXT NOT NULL,
    photo_url VARCHAR(512),
    geo_lat DECIMAL(9, 6),
    geo_lng DECIMAL(9, 6),
    geo_district VARCHAR(100),
    geo_block VARCHAR(100),
    batch_id VARCHAR(100),
    tracking_token VARCHAR(64) UNIQUE,
    status VARCHAR(50) DEFAULT 'INGESTED', -- INGESTED, TRIAGING, OFFICER_REVIEW, ROUTED, REJECTED, MERGED, COMPLETED
    reporter_name VARCHAR(255), -- optional self-declared reporter name (visible on workspace views)
    contact_email VARCHAR(255), -- opt-in notification email (plaintext: required for delivery)
    contact_phone VARCHAR(32), -- opt-in notification phone (plaintext: required for delivery)
    notify_consent BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Problems Table (Structured, triaged challenges)
CREATE TABLE problems (
    problem_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID UNIQUE REFERENCES submissions(submission_id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL,
    category VARCHAR(100) NOT NULL, -- Water, Environment, Infrastructure, Health, Education, Livelihood, Energy, Agriculture, Sanitation, Governance
    severity_score INTEGER CHECK (severity_score BETWEEN 1 AND 5),
    confidence_score DECIMAL(4, 3),
    summary_embedding vector(384),
    assigned_officer_id UUID,
    temporal_workflow_id VARCHAR(255),
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_of_id UUID REFERENCES problems(problem_id),
    cluster_group_id VARCHAR(100),
    status VARCHAR(50) DEFAULT 'PENDING_OFFICER_REVIEW',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Universities Table (Jharkhand Academic Network)
CREATE TABLE universities (
    university_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    short_code VARCHAR(50) UNIQUE NOT NULL, -- BIT_MESRA, NIT_JSR, IIT_ISM, CUJ, RANCHI_UNIV, XLRI
    iic_code VARCHAR(100),
    district VARCHAR(100) NOT NULL,
    geo_lat DECIMAL(9, 6) NOT NULL,
    geo_lng DECIMAL(9, 6) NOT NULL,
    domain_specializations TEXT[] NOT NULL,
    active_capacity INTEGER DEFAULT 10,
    current_load INTEGER DEFAULT 0,
    capability_embedding vector(384),
    nodal_contact_email VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Route Assignments Table
CREATE TABLE route_assignments (
    assignment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    problem_id UUID REFERENCES problems(problem_id) ON DELETE CASCADE,
    university_id UUID REFERENCES universities(university_id) ON DELETE CASCADE,
    rank_order INTEGER NOT NULL, -- 1, 2, 3
    match_score DECIMAL(5, 4) NOT NULL,
    score_breakdown JSONB NOT NULL, -- {semantic: 0.91, theme: 1.0, capacity: 0.8, geo: 0.95}
    sla_deadline TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(50) DEFAULT 'OFFERED', -- OFFERED, ACCEPTED, DECLINED, EXPIRED, AUTO_REROUTED
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP WITH TIME ZONE
);

-- 6. Project Teams & Milestones
CREATE TABLE project_teams (
    team_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assignment_id UUID REFERENCES route_assignments(assignment_id) ON DELETE CASCADE,
    problem_id UUID REFERENCES problems(problem_id) ON DELETE CASCADE,
    university_id UUID REFERENCES universities(university_id) ON DELETE CASCADE,
    faculty_mentor_name VARCHAR(255) NOT NULL,
    student_lead_name VARCHAR(255) NOT NULL,
    team_members JSONB,
    proposal_title VARCHAR(255),
    proposal_document_url VARCHAR(512),
    status VARCHAR(50) DEFAULT 'TEAM_FORMED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE milestones (
    milestone_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID REFERENCES project_teams(team_id) ON DELETE CASCADE,
    milestone_num INTEGER CHECK (milestone_num IN (1, 2, 3)),
    title VARCHAR(255) NOT NULL, -- M1: Feasibility, M2: Prototype, M3: Field Validation
    due_date TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING', -- PENDING, SUBMITTED, VERIFIED, DELAYED
    evidence_url VARCHAR(512),
    verified_by UUID,
    verified_at TIMESTAMP WITH TIME ZONE
);

-- 7. Industries & CSR Links
CREATE TABLE industries (
    industry_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    sector VARCHAR(100) NOT NULL, -- Mining, Steel, Energy, IT, Healthcare
    csr_focus_areas TEXT[] NOT NULL,
    csr_budget_inr DECIMAL(15, 2),
    contact_person VARCHAR(255),
    contact_email VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE funding_links (
    link_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    problem_id UUID REFERENCES problems(problem_id) ON DELETE CASCADE,
    team_id UUID REFERENCES project_teams(team_id) ON DELETE SET NULL,
    industry_id UUID REFERENCES industries(industry_id) ON DELETE CASCADE,
    pledged_amount_inr DECIMAL(15, 2),
    status VARCHAR(50) DEFAULT 'PLEDGED', -- PLEDGED, DISBURSED, COMPLETED
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. Officers & Admins Table
CREATE TABLE officers (
    officer_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    department VARCHAR(150) NOT NULL,
    district VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL, -- district_officer, senior_officer, state_admin
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 9. Immutable System Audit Logs Table
CREATE TABLE audit_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    actor_id VARCHAR(255) NOT NULL,
    actor_role VARCHAR(50) NOT NULL,
    before_snapshot JSONB,
    after_snapshot JSONB,
    ip_address VARCHAR(50),
    request_id VARCHAR(100),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- High-Performance ANN Vector Indexing & Query Acceleration
CREATE INDEX idx_problems_vector ON problems USING ivfflat (summary_embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_universities_vector ON universities USING ivfflat (capability_embedding vector_cosine_ops) WITH (lists = 10);
CREATE INDEX idx_problems_status ON problems(status);
CREATE INDEX idx_submissions_district ON submissions(geo_district);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);

-- Phase-1 identity tables (nitivayu.md §6). Idempotent: safe to apply over
-- an existing database (all statements are IF NOT EXISTS / conditional).
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_encrypted BYTEA,
    email_encrypted BYTEA,
    password_hash VARCHAR(255),
    display_name VARCHAR(255), -- self-declared name (navbar, intake prefill; never auth)
    workspace_type VARCHAR(50) NOT NULL DEFAULT 'citizen',
    organization_id UUID,
    district VARCHAR(100),
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS otp_codes (
    otp_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    code_hash VARCHAR(255) NOT NULL,
    channel VARCHAR(20) NOT NULL DEFAULT 'sms',
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    consumed_at TIMESTAMP WITH TIME ZONE,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS media_assets (
    asset_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID NOT NULL REFERENCES submissions(submission_id) ON DELETE CASCADE,
    kind VARCHAR(20) NOT NULL,
    storage_url VARCHAR(1024) NOT NULL,
    thumbnail_url VARCHAR(1024),
    transcript TEXT,
    moderation_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    size_bytes INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS org_invites (
    invite_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID,
    organization_type VARCHAR(50) NOT NULL,
    organization_name VARCHAR(255),
    email VARCHAR(255) NOT NULL,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    invited_by VARCHAR(255),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_organization ON users(organization_id);
CREATE INDEX IF NOT EXISTS idx_otp_codes_user ON otp_codes(user_id);
CREATE INDEX IF NOT EXISTS idx_media_assets_submission ON media_assets(submission_id);
CREATE INDEX IF NOT EXISTS idx_org_invites_email ON org_invites(email);
CREATE INDEX IF NOT EXISTS idx_org_invites_status ON org_invites(status);

-- Minimum university network needed for routing in a fresh local deployment.
INSERT INTO universities (name, short_code, district, geo_lat, geo_lng, domain_specializations, active_capacity, nodal_contact_email)
VALUES
  ('Birla Institute of Technology (BIT), Mesra', 'BIT_MESRA', 'Ranchi', 23.4123, 85.4399, ARRAY['Infrastructure', 'Water', 'Environment'], 15, 'iic.head@bitmesra.ac.in'),
  ('National Institute of Technology (NIT), Jamshedpur', 'NIT_JSR', 'East Singhbhum', 22.7766, 86.1444, ARRAY['Infrastructure', 'Industry', 'IoT'], 12, 'iic.coord@nitjsr.ac.in')
ON CONFLICT (short_code) DO NOTHING;

-- Demo industry workspace used by the CSR portal's scoped login and pledges.
INSERT INTO industries (name, sector, csr_focus_areas, csr_budget_inr, contact_person, contact_email)
VALUES
  ('Nitivayu CSR Foundation', 'Civic Innovation', ARRAY['Infrastructure', 'Water', 'Environment'], 10000000, 'CSR Desk', 'csr@nitivayu.example')
ON CONFLICT DO NOTHING;

-- Casefile + P4 updates (idempotent).
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS geo_source VARCHAR(20) NOT NULL DEFAULT 'district';
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS language_pref VARCHAR(10);
UPDATE submissions SET geo_source = 'gps' WHERE geo_source = 'district' AND geo_lat IS NOT NULL AND geo_lng IS NOT NULL;

CREATE TABLE IF NOT EXISTS project_updates (
    update_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES project_teams(team_id) ON DELETE CASCADE,
    problem_id UUID REFERENCES problems(problem_id) ON DELETE CASCADE,
    author_user_id VARCHAR(255),
    author_name VARCHAR(255),
    note TEXT NOT NULL,
    milestone VARCHAR(50),
    photo_urls JSONB,
    notified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_project_updates_team ON project_updates(team_id);
CREATE INDEX IF NOT EXISTS idx_project_updates_problem ON project_updates(problem_id);

-- Batch-triage cadence + run history (§5.x batch control).
CREATE TABLE IF NOT EXISTS cadence_configs (
    id VARCHAR(100) PRIMARY KEY,
    active_cadence VARCHAR(50) NOT NULL DEFAULT 'weekly',
    cron_expression VARCHAR(100) NOT NULL DEFAULT '0 0 * * 0',
    monthly_macro_cron VARCHAR(100) NOT NULL DEFAULT '0 0 1 * *',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS batch_runs (
    batch_id VARCHAR(100) PRIMARY KEY,
    cadence VARCHAR(50) NOT NULL DEFAULT 'weekly',
    status VARCHAR(50) NOT NULL DEFAULT 'RUNNING',
    total INTEGER NOT NULL DEFAULT 0,
    processed INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    duplicates INTEGER NOT NULL DEFAULT 0,
    csv_path VARCHAR(512),
    pdf_path VARCHAR(512),
    error TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_batch_runs_started ON batch_runs(started_at DESC);

-- plan4 backend pipeline (idempotent): account-scoped submissions, citizen
-- profile prefs + opt-in SMS channel, monthly-macro tables.
-- Mirrors scripts/migrations/002, 003, 004 for fresh deployments.
ALTER TABLE submissions
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(user_id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_submissions_user_id ON submissions(user_id);

ALTER TABLE users ADD COLUMN IF NOT EXISTS language_pref VARCHAR(10);
ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_sms BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_enc BYTEA;

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

-- Civic feed likes (mirrors scripts/migrations/005_civic_feed.sql).
CREATE TABLE IF NOT EXISTS report_likes (
    like_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    problem_id UUID NOT NULL REFERENCES problems(problem_id) ON DELETE CASCADE,
    voter_key VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_report_likes_voter UNIQUE (problem_id, voter_key)
);
CREATE INDEX IF NOT EXISTS ix_report_likes_problem ON report_likes(problem_id);
