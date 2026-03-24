-- 028_linkedin_scraped.sql
-- Tables for LinkedIn scraped posts and comments (from browser scraper)

CREATE TABLE IF NOT EXISTS linkedin_scraped_posts (
    id SERIAL PRIMARY KEY,
    urn TEXT UNIQUE,
    text TEXT,
    post_type VARCHAR(30) DEFAULT 'text',
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    reposts INTEGER DEFAULT 0,
    media_files JSONB DEFAULT '[]',
    url TEXT,
    original_author TEXT,
    posted_at TIMESTAMP WITH TIME ZONE,
    imported_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS linkedin_scraped_comments (
    id SERIAL PRIMARY KEY,
    original_author TEXT,
    original_snippet TEXT,
    original_post_url TEXT,
    comment_text TEXT,
    comment_url TEXT,
    urn TEXT UNIQUE,
    commented_at TIMESTAMP WITH TIME ZONE,
    imported_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_scraped_posts_urn ON linkedin_scraped_posts(urn);
CREATE INDEX IF NOT EXISTS idx_scraped_posts_posted_at ON linkedin_scraped_posts(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_scraped_comments_urn ON linkedin_scraped_comments(urn);
CREATE INDEX IF NOT EXISTS idx_scraped_comments_commented_at ON linkedin_scraped_comments(commented_at DESC);
