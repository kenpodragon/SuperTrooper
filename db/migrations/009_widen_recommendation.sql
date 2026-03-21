-- Migration 009: Widen gap_analyses.recommendation column
-- The rule-based gap analysis generates recommendation strings that exceed 50 chars
ALTER TABLE gap_analyses ALTER COLUMN recommendation TYPE varchar(255);
