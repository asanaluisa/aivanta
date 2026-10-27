-- Aivanta initial schema (PostgreSQL 14+).
-- Applied by Alembic revision 0001_initial. Mirrors app/models.py; the test
-- tests/api/test_migrations.py checks that both stay identical.

CREATE TABLE organizations (
    id              SERIAL PRIMARY KEY,
    key             VARCHAR(64)  NOT NULL UNIQUE,
    name            VARCHAR(200) NOT NULL,
    currency        VARCHAR(3)   NOT NULL,
    is_synthetic    BOOLEAN      NOT NULL,
    data_start      DATE,
    data_end        DATE,
    data_version    INTEGER      NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE departments (
    id                  SERIAL PRIMARY KEY,
    organization_id     INTEGER NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    key                 VARCHAR(64)  NOT NULL,
    name_key            VARCHAR(128) NOT NULL,
    loaded_hourly_rate  NUMERIC(14, 2) NOT NULL,
    UNIQUE (organization_id, key)
);
CREATE INDEX ix_departments_organization_id ON departments (organization_id);

CREATE TABLE users (
    id                SERIAL PRIMARY KEY,
    organization_id   INTEGER NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    key               VARCHAR(128) NOT NULL,
    email             VARCHAR(254) UNIQUE,
    display_name      VARCHAR(200),
    password_hash     VARCHAR(256),
    role              VARCHAR(16) NOT NULL,
    preferred_locale  VARCHAR(5)  NOT NULL,
    department_id     INTEGER REFERENCES departments (id),
    is_active         BOOLEAN NOT NULL,
    UNIQUE (organization_id, key),
    CONSTRAINT ck_users_role CHECK (role IN ('admin', 'finance', 'analyst', 'viewer', 'member'))
);
CREATE INDEX ix_users_organization_id ON users (organization_id);

CREATE TABLE ai_providers (
    id   SERIAL PRIMARY KEY,
    key  VARCHAR(32) NOT NULL UNIQUE
);

CREATE TABLE ai_models (
    id           SERIAL PRIMARY KEY,
    provider_id  INTEGER NOT NULL REFERENCES ai_providers (id),
    key          VARCHAR(128) NOT NULL,
    tier         VARCHAR(16)  NOT NULL,
    UNIQUE (provider_id, key)
);

CREATE TABLE model_prices (
    id                      SERIAL PRIMARY KEY,
    organization_id         INTEGER NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    model_id                INTEGER NOT NULL REFERENCES ai_models (id),
    effective_from          DATE NOT NULL,
    input_per_mtok          NUMERIC(12, 6) NOT NULL,
    output_per_mtok         NUMERIC(12, 6) NOT NULL,
    cached_input_per_mtok   NUMERIC(12, 6),
    UNIQUE (organization_id, model_id, effective_from)
);
CREATE INDEX ix_model_prices_organization_id ON model_prices (organization_id);

CREATE TABLE use_cases (
    id                  SERIAL PRIMARY KEY,
    organization_id     INTEGER NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    key                 VARCHAR(64)  NOT NULL,
    name_key            VARCHAR(128) NOT NULL,
    department_id       INTEGER REFERENCES departments (id),
    task_complexity     VARCHAR(16)  NOT NULL,
    measurement_start   DATE,
    measurement_end     DATE,
    data_source         TEXT NOT NULL,
    UNIQUE (organization_id, key)
);
CREATE INDEX ix_use_cases_organization_id ON use_cases (organization_id);

CREATE TABLE experiments (
    id                SERIAL PRIMARY KEY,
    organization_id   INTEGER NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    use_case_id       INTEGER NOT NULL UNIQUE REFERENCES use_cases (id) ON DELETE CASCADE,
    design            VARCHAR(32) NOT NULL,
    assignment_unit   VARCHAR(64),
    description       TEXT NOT NULL,
    start_date        DATE,
    end_date          DATE
);
CREATE INDEX ix_experiments_organization_id ON experiments (organization_id);

CREATE TABLE baselines (
    id                SERIAL PRIMARY KEY,
    organization_id   INTEGER NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    use_case_id       INTEGER NOT NULL REFERENCES use_cases (id) ON DELETE CASCADE,
    metric            VARCHAR(32) NOT NULL,
    value             DOUBLE PRECISION NOT NULL,
    source            TEXT NOT NULL,
    measured_from     DATE,
    measured_to       DATE
);
CREATE INDEX ix_baselines_organization_id ON baselines (organization_id);

CREATE TABLE ingestion_batches (
    id                SERIAL PRIMARY KEY,
    organization_id   INTEGER NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    format            VARCHAR(32)  NOT NULL,
    filename          VARCHAR(255) NOT NULL,
    accepted          INTEGER NOT NULL,
    duplicates        INTEGER NOT NULL,
    rejected          INTEGER NOT NULL,
    unallocated       INTEGER NOT NULL,
    summary           JSON NOT NULL,
    created_by        INTEGER REFERENCES users (id),
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX ix_ingestion_batches_organization_id ON ingestion_batches (organization_id);

CREATE TABLE attribution_rules (
    id                SERIAL PRIMARY KEY,
    organization_id   INTEGER NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    identifier        VARCHAR(255) NOT NULL,
    department_id     INTEGER REFERENCES departments (id),
    use_case_id       INTEGER REFERENCES use_cases (id),
    UNIQUE (organization_id, identifier)
);
CREATE INDEX ix_attribution_rules_organization_id ON attribution_rules (organization_id);

CREATE TABLE tasks (
    id                      BIGSERIAL PRIMARY KEY,
    organization_id         INTEGER NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    external_id             VARCHAR(64) NOT NULL,
    use_case_id             INTEGER NOT NULL REFERENCES use_cases (id) ON DELETE CASCADE,
    arm                     VARCHAR(8)  NOT NULL,
    task_type               VARCHAR(64) NOT NULL,
    completed_on            DATE NOT NULL,
    duration_minutes        DOUBLE PRECISION NOT NULL,
    success                 BOOLEAN NOT NULL,
    quality_score           DOUBLE PRECISION,
    had_error               BOOLEAN NOT NULL,
    rework_minutes          DOUBLE PRECISION NOT NULL,
    review_minutes          DOUBLE PRECISION NOT NULL,
    customer_satisfaction   DOUBLE PRECISION,
    user_id                 INTEGER REFERENCES users (id),
    UNIQUE (organization_id, external_id),
    CONSTRAINT ck_tasks_arm CHECK (arm IN ('ai', 'non_ai'))
);
CREATE INDEX ix_tasks_org_uc_day ON tasks (organization_id, use_case_id, completed_on);

CREATE TABLE usage_events (
    id                    BIGSERIAL PRIMARY KEY,
    organization_id       INTEGER NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    external_id           VARCHAR(64) NOT NULL,
    occurred_at           TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    model_id              INTEGER NOT NULL REFERENCES ai_models (id),
    input_tokens          BIGINT NOT NULL,
    output_tokens         BIGINT NOT NULL,
    cached_input_tokens   BIGINT NOT NULL,
    request_count         INTEGER NOT NULL,
    retries               INTEGER NOT NULL,
    status                VARCHAR(16) NOT NULL,
    latency_ms            INTEGER,
    cost                  NUMERIC(18, 8) NOT NULL,
    user_id               INTEGER REFERENCES users (id),
    department_id         INTEGER REFERENCES departments (id),
    use_case_id           INTEGER REFERENCES use_cases (id),
    task_external_id      VARCHAR(64),
    source                VARCHAR(64) NOT NULL,
    ingestion_batch_id    INTEGER REFERENCES ingestion_batches (id),
    UNIQUE (organization_id, external_id),
    CONSTRAINT ck_usage_cached_le_input CHECK (cached_input_tokens <= input_tokens),
    CONSTRAINT ck_usage_requests CHECK (request_count >= 1)
);
CREATE INDEX ix_usage_org_time ON usage_events (organization_id, occurred_at);

CREATE TABLE cost_items (
    id                SERIAL PRIMARY KEY,
    organization_id   INTEGER NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    external_id       VARCHAR(64) NOT NULL,
    category          VARCHAR(32) NOT NULL,
    amount            NUMERIC(14, 2) NOT NULL,
    period_start      DATE NOT NULL,
    period_end        DATE NOT NULL,
    one_off           BOOLEAN NOT NULL,
    description_key   VARCHAR(128) NOT NULL,
    use_case_id       INTEGER REFERENCES use_cases (id),
    department_id     INTEGER REFERENCES departments (id),
    UNIQUE (organization_id, external_id),
    CONSTRAINT ck_cost_items_category CHECK (category IN
        ('subscription', 'infrastructure', 'implementation', 'maintenance', 'other_operating')),
    CONSTRAINT ck_cost_items_period CHECK (period_end >= period_start)
);
CREATE INDEX ix_cost_items_organization_id ON cost_items (organization_id);

CREATE TABLE benefit_claims (
    id                    SERIAL PRIMARY KEY,
    organization_id       INTEGER NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    external_id           VARCHAR(64) NOT NULL,
    use_case_id           INTEGER NOT NULL REFERENCES use_cases (id) ON DELETE CASCADE,
    category              VARCHAR(32) NOT NULL,
    amount                NUMERIC(14, 2) NOT NULL,
    verification_status   VARCHAR(16) NOT NULL,
    evidence_key          VARCHAR(255) NOT NULL,
    period_start          DATE NOT NULL,
    period_end            DATE NOT NULL,
    confidence            DOUBLE PRECISION NOT NULL,
    source                TEXT NOT NULL,
    verified_by           INTEGER REFERENCES users (id),
    verified_at           TIMESTAMP WITH TIME ZONE,
    UNIQUE (organization_id, external_id),
    CONSTRAINT ck_benefit_category CHECK (category IN
        ('financial_savings', 'incremental_contribution', 'cost_avoidance')),
    CONSTRAINT ck_benefit_status CHECK (verification_status IN
        ('verified', 'supported', 'estimated', 'unverified')),
    CONSTRAINT ck_benefit_amount CHECK (amount >= 0)
);
CREATE INDEX ix_benefit_claims_organization_id ON benefit_claims (organization_id);

CREATE TABLE budgets (
    id                SERIAL PRIMARY KEY,
    organization_id   INTEGER NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    external_id       VARCHAR(64) NOT NULL,
    department_id     INTEGER REFERENCES departments (id),
    month             DATE NOT NULL,
    amount            NUMERIC(14, 2) NOT NULL,
    UNIQUE (organization_id, department_id, month)
);
CREATE INDEX ix_budgets_organization_id ON budgets (organization_id);

CREATE TABLE alerts (
    id                SERIAL PRIMARY KEY,
    organization_id   INTEGER NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    rule_id           VARCHAR(64)  NOT NULL,
    severity          VARCHAR(16)  NOT NULL,
    scope_type        VARCHAR(32)  NOT NULL,
    scope_key         VARCHAR(128) NOT NULL,
    metrics           JSON NOT NULL,
    first_seen_at     TIMESTAMP WITH TIME ZONE NOT NULL,
    acknowledged_by   INTEGER REFERENCES users (id),
    acknowledged_at   TIMESTAMP WITH TIME ZONE,
    UNIQUE (organization_id, rule_id, scope_type, scope_key)
);
CREATE INDEX ix_alerts_organization_id ON alerts (organization_id);

CREATE TABLE assumption_sets (
    id                SERIAL PRIMARY KEY,
    organization_id   INTEGER NOT NULL UNIQUE REFERENCES organizations (id) ON DELETE CASCADE,
    values            JSON NOT NULL,
    updated_by        INTEGER REFERENCES users (id),
    updated_at        TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE roi_snapshots (
    id                SERIAL PRIMARY KEY,
    organization_id   INTEGER NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    scope_type        VARCHAR(32)  NOT NULL,
    scope_key         VARCHAR(128) NOT NULL,
    period_start      DATE NOT NULL,
    period_end        DATE NOT NULL,
    status            VARCHAR(32)  NOT NULL,
    total_cost        NUMERIC(14, 2) NOT NULL,
    gross_benefit     NUMERIC(14, 2) NOT NULL,
    net_benefit       NUMERIC(14, 2),
    roi_pct           NUMERIC(10, 2),
    data_version      INTEGER NOT NULL,
    assumptions       JSON NOT NULL,
    payload           JSON NOT NULL,
    created_by        INTEGER REFERENCES users (id),
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX ix_roi_snapshots_organization_id ON roi_snapshots (organization_id);

CREATE TABLE audit_events (
    id                BIGSERIAL PRIMARY KEY,
    organization_id   INTEGER NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    user_id           INTEGER REFERENCES users (id),
    action            VARCHAR(64) NOT NULL,
    entity_type       VARCHAR(64) NOT NULL,
    entity_id         VARCHAR(128),
    before            JSON,
    after             JSON,
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_org_time ON audit_events (organization_id, created_at);
