BEGIN;

CREATE TABLE IF NOT EXISTS market_signals (
  id SERIAL PRIMARY KEY,
  source VARCHAR(50) NOT NULL,  -- bls_jolts, lisep_tru, warn_act, hn_hiring, news, manual
  signal_type VARCHAR(50) NOT NULL,  -- layoff, hiring_freeze, market_trend, job_openings, separation_rate, quit_rate, wage_data
  title TEXT NOT NULL,
  body TEXT,
  data_json JSONB,  -- structured data specific to signal type
  region VARCHAR(100),  -- geographic region (US, state, metro)
  industry VARCHAR(100),  -- industry sector
  severity VARCHAR(20) DEFAULT 'neutral',  -- positive, neutral, negative, critical
  source_url TEXT,
  captured_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_signals_source ON market_signals(source);
CREATE INDEX IF NOT EXISTS idx_market_signals_type ON market_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_market_signals_severity ON market_signals(severity);
CREATE INDEX IF NOT EXISTS idx_market_signals_captured ON market_signals(captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_market_signals_industry ON market_signals(industry);
CREATE INDEX IF NOT EXISTS idx_market_signals_region ON market_signals(region);

COMMIT;
