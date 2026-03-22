-- Migration 026: Networking events tracking
-- Supports: POST/GET /api/crm/events, POST /api/crm/events/{id}/attendees

CREATE TABLE IF NOT EXISTS networking_events (
    id              SERIAL PRIMARY KEY,
    event_name      TEXT NOT NULL,
    event_type      TEXT DEFAULT 'other'
                    CHECK (event_type IN ('conference', 'meetup', 'coffee_chat', 'webinar', 'career_fair', 'other')),
    event_date      DATE,
    location        TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS networking_event_attendees (
    id              SERIAL PRIMARY KEY,
    event_id        INTEGER NOT NULL REFERENCES networking_events(id) ON DELETE CASCADE,
    contact_id      INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(event_id, contact_id)
);

CREATE INDEX IF NOT EXISTS idx_networking_events_date ON networking_events(event_date DESC);
CREATE INDEX IF NOT EXISTS idx_networking_event_attendees_event ON networking_event_attendees(event_id);
CREATE INDEX IF NOT EXISTS idx_networking_event_attendees_contact ON networking_event_attendees(contact_id);
