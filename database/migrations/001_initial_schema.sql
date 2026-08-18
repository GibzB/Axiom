-- Axiom v0.1
-- Initial CockroachDB schema

CREATE DATABASE IF NOT EXISTS axiom;
USE axiom;

CREATE TYPE IF NOT EXISTS decision_status AS ENUM (
    'DRAFT',
    'ACTIVE',
    'AT_RISK',
    'UNDER_REVIEW',
    'VALIDATED',
    'SUPERSEDED',
    'RETIRED'
);

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name STRING NOT NULL,
    description STRING,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    title STRING NOT NULL,
    statement STRING NOT NULL,
    rationale STRING,
    status decision_status NOT NULL DEFAULT 'DRAFT',
    confidence DECIMAL(5,4),
    supersedes_decision_id UUID REFERENCES decisions(id),
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS assumptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    statement STRING NOT NULL,
    validation_condition STRING,
    invalidation_condition STRING,
    status STRING NOT NULL DEFAULT 'UNTESTED',
    confidence DECIMAL(5,4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    content STRING NOT NULL,
    source STRING NOT NULL DEFAULT 'USER',
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS assumption_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assumption_id UUID NOT NULL REFERENCES assumptions(id),
    observation_id UUID NOT NULL REFERENCES observations(id),
    verdict STRING NOT NULL,
    confidence DECIMAL(5,4) NOT NULL,
    explanation STRING NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (assumption_id, observation_id)
);

CREATE TABLE IF NOT EXISTS memory_objects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    entity_type STRING NOT NULL,
    entity_id UUID NOT NULL,
    memory_type STRING NOT NULL,
    content STRING NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    run_type STRING NOT NULL,
    status STRING NOT NULL,
    model_id STRING,
    input_hash STRING,
    error_code STRING,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    agent_run_id UUID REFERENCES agent_runs(id),
    actor_type STRING NOT NULL,
    action STRING NOT NULL,
    entity_type STRING,
    entity_id UUID,
    before_state JSONB,
    after_state JSONB,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_decisions_project
ON decisions (project_id);

CREATE INDEX IF NOT EXISTS idx_decisions_status
ON decisions (status);

CREATE INDEX IF NOT EXISTS idx_assumptions_decision
ON assumptions (decision_id);

CREATE INDEX IF NOT EXISTS idx_observations_project
ON observations (project_id);

CREATE INDEX IF NOT EXISTS idx_memory_project
ON memory_objects (project_id);

CREATE INDEX IF NOT EXISTS idx_agent_runs_project
ON agent_runs (project_id);

CREATE INDEX IF NOT EXISTS idx_audit_project
ON audit_events (project_id);
