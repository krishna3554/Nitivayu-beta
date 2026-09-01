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
    status VARCHAR(50) DEFAULT 'INGESTED', -- INGESTED, TRIAGING, OFFICER_REVIEW, ROUTED, REJECTED, MERGED, COMPLETED
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
