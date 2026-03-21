BEGIN;

CREATE TABLE IF NOT EXISTS mock_interviews (
    id SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES applications(id),
    job_title TEXT,
    company TEXT,
    interview_type TEXT DEFAULT 'behavioral',  -- behavioral, technical, case, mixed
    difficulty TEXT DEFAULT 'medium',           -- easy, medium, hard
    status TEXT DEFAULT 'pending',              -- pending, in_progress, completed, reviewed, archived
    overall_score INTEGER,                      -- 1-100
    overall_feedback TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mock_interview_questions (
    id SERIAL PRIMARY KEY,
    mock_interview_id INTEGER REFERENCES mock_interviews(id) ON DELETE CASCADE,
    question_number INTEGER NOT NULL,
    question_type TEXT DEFAULT 'behavioral',  -- behavioral, technical, situational, case
    question_text TEXT NOT NULL,
    suggested_answer TEXT,   -- AI-generated ideal answer
    user_answer TEXT,        -- user's actual answer
    score INTEGER,           -- 1-10
    feedback TEXT,           -- AI evaluation feedback
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mock_interviews_application ON mock_interviews(application_id);
CREATE INDEX IF NOT EXISTS idx_mock_questions_interview ON mock_interview_questions(mock_interview_id);

COMMIT;
