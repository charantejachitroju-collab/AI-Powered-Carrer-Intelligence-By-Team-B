CREATE TABLE IF NOT EXISTS job_applications (
    uid TEXT NOT NULL REFERENCES user_profiles(uid) ON DELETE CASCADE,
    notification_id TEXT NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    status INTEGER NOT NULL DEFAULT 0 CHECK (status BETWEEN 0 AND 3),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (uid, notification_id)
);
CREATE INDEX IF NOT EXISTS idx_job_applications_uid_status_updated
    ON job_applications(uid, status, updated_at DESC);
