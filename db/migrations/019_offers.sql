-- 019_offers.sql — Offer Evaluation & Negotiation
-- Phase 5B: offers table for tracking, benchmarking, comp comparison, negotiation

BEGIN;

CREATE TABLE IF NOT EXISTS offers (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    version INTEGER DEFAULT 1,
    version_label VARCHAR(50) DEFAULT 'initial',
    base_salary NUMERIC(12,2),
    signing_bonus NUMERIC(12,2),
    annual_bonus_pct NUMERIC(5,2),
    annual_bonus_target NUMERIC(12,2),
    equity_type VARCHAR(30),
    equity_value NUMERIC(12,2),
    equity_shares INTEGER,
    equity_vesting_months INTEGER DEFAULT 48,
    equity_cliff_months INTEGER DEFAULT 12,
    benefits_notes TEXT,
    pto_days INTEGER,
    remote_policy VARCHAR(30),
    title_offered VARCHAR(200),
    start_date DATE,
    expiration_date DATE,
    location VARCHAR(200),
    status VARCHAR(30) DEFAULT 'pending',
    negotiation_notes TEXT,
    decision_factors JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_offers_application_id ON offers(application_id);
CREATE INDEX IF NOT EXISTS idx_offers_status ON offers(status);

COMMIT;
