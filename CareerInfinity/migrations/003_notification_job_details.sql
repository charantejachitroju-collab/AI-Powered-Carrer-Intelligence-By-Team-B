CREATE TABLE IF NOT EXISTS notification_job_details (
    notification_id TEXT PRIMARY KEY REFERENCES notifications(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    external_job_id TEXT NOT NULL,
    company_logo TEXT,
    location TEXT,
    salary_min REAL,
    salary_max REAL,
    salary_currency TEXT,
    salary_period TEXT,
    employment_type TEXT,
    work_mode TEXT,
    experience TEXT,
    qualification TEXT,
    job_url TEXT,
    posted_at TEXT,
    application_deadline TEXT,
    description TEXT NOT NULL DEFAULT '',
    required_skills_json TEXT NOT NULL DEFAULT '[]',
    matching_skills_json TEXT NOT NULL DEFAULT '[]',
    missing_skills_json TEXT NOT NULL DEFAULT '[]',
    match_explanation TEXT NOT NULL DEFAULT '',
    last_seen_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_uid_job_unique
    ON notifications(uid, job_id) WHERE job_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_notification_job_details_last_seen
    ON notification_job_details(source, last_seen_at DESC);

-- Remove the fictional placeholder records from the earlier notification draft.
DELETE FROM notifications WHERE is_demo = 1;
