CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    uid TEXT NOT NULL REFERENCES user_profiles(uid) ON DELETE CASCADE,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('job_match','internship','application','interview','deadline','ai_insight')),
    notification_type TEXT NOT NULL,
    job_id TEXT,
    company_name TEXT,
    match_percentage INTEGER CHECK (match_percentage IS NULL OR (match_percentage BETWEEN 0 AND 100)),
    is_read INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0,1)),
    action_url TEXT,
    created_at TEXT NOT NULL,
    is_demo INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0,1)),
    dedupe_key TEXT,
    UNIQUE(uid, dedupe_key)
);
CREATE INDEX IF NOT EXISTS idx_notifications_uid_created ON notifications(uid, created_at DESC, id);
CREATE INDEX IF NOT EXISTS idx_notifications_uid_read_created ON notifications(uid, is_read, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_uid_category_created ON notifications(uid, category, created_at DESC);

CREATE TABLE IF NOT EXISTS notification_preferences (
    uid TEXT PRIMARY KEY REFERENCES user_profiles(uid) ON DELETE CASCADE,
    preferences_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);
