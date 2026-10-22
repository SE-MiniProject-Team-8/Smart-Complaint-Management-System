-- SCMS SQLite schema (Section 3.7 / 3.8 and Section 4.7 of the design).
-- Foreign keys are enabled per connection in db.py.

CREATE TABLE IF NOT EXISTS users (
    user_id        INTEGER PRIMARY KEY,
    university_id  TEXT NOT NULL UNIQUE CHECK (length(university_id) BETWEEN 1 AND 20),
    name           TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
    email          TEXT NOT NULL UNIQUE CHECK (length(email) BETWEEN 1 AND 100),
    password_hash  TEXT NOT NULL CHECK (length(password_hash) <= 255),
    role           TEXT NOT NULL CHECK (role IN ('Student', 'Faculty', 'Committee', 'Dean')),
    sla_review     INTEGER NOT NULL DEFAULT 0 CHECK (sla_review IN (0, 1)),
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    user_id     INTEGER REFERENCES users(user_id) ON DELETE CASCADE,  -- NULL = pre-login CSRF session
    csrf_token  TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS complaints (
    complaint_id       INTEGER PRIMARY KEY,
    student_id         INTEGER NOT NULL REFERENCES users(user_id),
    category           TEXT NOT NULL CHECK (length(category) BETWEEN 1 AND 50),
    description        TEXT NOT NULL CHECK (length(description) BETWEEN 1 AND 1000),
    severity           TEXT NOT NULL CHECK (severity IN ('Low', 'Medium', 'High')),
    status             TEXT NOT NULL CHECK (status IN
                         ('Submitted', 'Escalated', 'Under Appeal Review', 'Resolved', 'Rejected')),
    current_level      INTEGER NOT NULL CHECK (current_level BETWEEN 1 AND 3),
    assigned_to        INTEGER REFERENCES users(user_id),
    submitted_at       TEXT NOT NULL,
    status_updated_at  TEXT NOT NULL,
    rejection_reason   TEXT CHECK (rejection_reason IS NULL OR length(rejection_reason) <= 500),
    resolution_remarks TEXT CHECK (resolution_remarks IS NULL OR length(resolution_remarks) <= 500),
    appealed           INTEGER NOT NULL DEFAULT 0 CHECK (appealed IN (0, 1)),
    rejected_level     INTEGER CHECK (rejected_level IS NULL OR rejected_level BETWEEN 1 AND 3),
    final_review       INTEGER NOT NULL DEFAULT 0 CHECK (final_review IN (0, 1)),
    version            INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)
);

CREATE TABLE IF NOT EXISTS assignment_history (
    assignment_id  INTEGER PRIMARY KEY,
    complaint_id   INTEGER NOT NULL REFERENCES complaints(complaint_id),
    level          INTEGER NOT NULL CHECK (level BETWEEN 1 AND 3),
    actor_id       INTEGER NOT NULL REFERENCES users(user_id),
    assigned_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS appeals (
    appeal_id       INTEGER PRIMARY KEY,
    complaint_id    INTEGER NOT NULL UNIQUE REFERENCES complaints(complaint_id),  -- one appeal only
    actor_id        INTEGER NOT NULL REFERENCES users(user_id),
    justification   TEXT NOT NULL CHECK (length(justification) BETWEEN 1 AND 1000),
    submitted_at    TEXT NOT NULL,
    rejected_level  INTEGER NOT NULL CHECK (rejected_level BETWEEN 1 AND 3),
    target_level    INTEGER NOT NULL CHECK (target_level BETWEEN 1 AND 3),
    final_review    INTEGER NOT NULL DEFAULT 0 CHECK (final_review IN (0, 1))
);

CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id         INTEGER PRIMARY KEY,
    complaint_id     INTEGER NOT NULL REFERENCES complaints(complaint_id),
    actor_id         INTEGER NOT NULL REFERENCES users(user_id),
    action           TEXT NOT NULL CHECK (length(action) BETWEEN 1 AND 50),
    previous_status  TEXT NOT NULL CHECK (length(previous_status) <= 30),
    new_status       TEXT NOT NULL CHECK (length(new_status) <= 30),
    previous_level   INTEGER CHECK (previous_level IS NULL OR previous_level BETWEEN 1 AND 3),
    new_level        INTEGER CHECK (new_level IS NULL OR new_level BETWEEN 1 AND 3),
    timestamp        TEXT NOT NULL
);

-- Audit history is append-only (REQ-6.1, SEC-03).
CREATE TRIGGER IF NOT EXISTS audit_logs_no_update
BEFORE UPDATE ON audit_logs
BEGIN
    SELECT RAISE(ABORT, 'audit_logs is append-only');
END;

CREATE TRIGGER IF NOT EXISTS audit_logs_no_delete
BEFORE DELETE ON audit_logs
BEGIN
    SELECT RAISE(ABORT, 'audit_logs is append-only');
END;

CREATE TABLE IF NOT EXISTS notifications (
    notification_id  INTEGER PRIMARY KEY,
    complaint_id     INTEGER NOT NULL REFERENCES complaints(complaint_id),
    target_level     INTEGER NOT NULL CHECK (target_level BETWEEN 1 AND 3),
    event            TEXT NOT NULL,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    feedback_id   INTEGER PRIMARY KEY,
    complaint_id  INTEGER NOT NULL UNIQUE REFERENCES complaints(complaint_id),  -- no student_id by design
    rating        INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment       TEXT CHECK (comment IS NULL OR length(comment) <= 500),
    submitted_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);

INSERT OR IGNORE INTO settings (key, value) VALUES ('sla_threshold_days', '7');

CREATE INDEX IF NOT EXISTS idx_complaints_student     ON complaints(student_id, submitted_at);
CREATE INDEX IF NOT EXISTS idx_complaints_level       ON complaints(current_level, status);
CREATE INDEX IF NOT EXISTS idx_complaints_status_time ON complaints(status, status_updated_at);
CREATE INDEX IF NOT EXISTS idx_assignment_complaint   ON assignment_history(complaint_id, level);
CREATE INDEX IF NOT EXISTS idx_audit_complaint        ON audit_logs(complaint_id, timestamp, audit_id);
CREATE INDEX IF NOT EXISTS idx_notifications_level    ON notifications(target_level, created_at);
