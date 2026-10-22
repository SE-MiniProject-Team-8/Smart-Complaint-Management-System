"""SQLite Repository (C09): the only module that contains SQL.

All statements are parameterized. Mutation helpers take the caller's
connection so that they run inside the caller's transaction.
"""

# ---- users ---------------------------------------------------------------

def insert_user(conn, university_id, name, email, password_hash, role, sla_review, created_at):
    cur = conn.execute(
        "INSERT INTO users (university_id, name, email, password_hash, role, sla_review, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (university_id, name, email, password_hash, role, int(sla_review), created_at),
    )
    return cur.lastrowid


def get_user(conn, user_id):
    return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()


def get_user_by_university_id(conn, university_id):
    return conn.execute("SELECT * FROM users WHERE university_id = ?", (university_id,)).fetchone()


# ---- sessions ------------------------------------------------------------

def insert_session(conn, session_id, user_id, csrf_token, expires_at):
    conn.execute(
        "INSERT INTO sessions (session_id, user_id, csrf_token, expires_at) VALUES (?, ?, ?, ?)",
        (session_id, user_id, csrf_token, expires_at),
    )


def get_session(conn, session_id):
    return conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()


def delete_session(conn, session_id):
    conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))


def delete_expired_sessions(conn, now):
    conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))


# ---- complaints ----------------------------------------------------------

def insert_complaint(conn, student_id, category, description, severity, level, now):
    cur = conn.execute(
        "INSERT INTO complaints (student_id, category, description, severity, status,"
        " current_level, submitted_at, status_updated_at)"
        " VALUES (?, ?, ?, ?, 'Submitted', ?, ?, ?)",
        (student_id, category, description, severity, level, now, now),
    )
    return cur.lastrowid


def get_complaint(conn, complaint_id):
    return conn.execute("SELECT * FROM complaints WHERE complaint_id = ?", (complaint_id,)).fetchone()


def update_complaint_state(conn, complaint_id, expected_version, now, **fields):
    """Optimistic update: succeeds only if the version still matches.

    Returns the number of rows changed (0 means a stale version). The version
    is incremented exactly once per accepted change.
    """
    allowed = {"status", "current_level", "rejection_reason", "resolution_remarks",
               "appealed", "rejected_level", "final_review"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"Unsupported complaint fields: {sorted(unknown)}")
    assignments = ", ".join(f"{name} = ?" for name in fields)
    sql = (f"UPDATE complaints SET {assignments + ', ' if assignments else ''}"
           "status_updated_at = ?, version = version + 1 "
           "WHERE complaint_id = ? AND version = ?")
    params = list(fields.values()) + [now, complaint_id, expected_version]
    return conn.execute(sql, params).rowcount


def list_complaints(conn, where_sql, params, page, page_size):
    """`where_sql` is built only from fixed fragments in queries.py, never user text."""
    total = conn.execute(f"SELECT COUNT(*) FROM complaints WHERE {where_sql}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM complaints WHERE {where_sql}"
        " ORDER BY submitted_at DESC, complaint_id DESC LIMIT ? OFFSET ?",
        list(params) + [page_size, (page - 1) * page_size],
    ).fetchall()
    return rows, total


def list_overdue_candidates(conn):
    return conn.execute(
        "SELECT * FROM complaints WHERE status NOT IN ('Resolved', 'Rejected')"
        " ORDER BY status_updated_at ASC, complaint_id ASC"
    ).fetchall()


# ---- assignment history --------------------------------------------------

def insert_assignment(conn, complaint_id, level, actor_id, assigned_at):
    conn.execute(
        "INSERT INTO assignment_history (complaint_id, level, actor_id, assigned_at)"
        " VALUES (?, ?, ?, ?)",
        (complaint_id, level, actor_id, assigned_at),
    )


def has_assignment_level(conn, complaint_id, level):
    row = conn.execute(
        "SELECT 1 FROM assignment_history WHERE complaint_id = ? AND level = ? LIMIT 1",
        (complaint_id, level),
    ).fetchone()
    return row is not None


# ---- appeals -------------------------------------------------------------

def insert_appeal(conn, complaint_id, actor_id, justification, submitted_at,
                  rejected_level, target_level, final_review):
    cur = conn.execute(
        "INSERT INTO appeals (complaint_id, actor_id, justification, submitted_at,"
        " rejected_level, target_level, final_review) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (complaint_id, actor_id, justification, submitted_at,
         rejected_level, target_level, int(final_review)),
    )
    return cur.lastrowid


# ---- audit ---------------------------------------------------------------

def insert_audit(conn, complaint_id, actor_id, action, previous_status, new_status,
                 previous_level, new_level, timestamp):
    cur = conn.execute(
        "INSERT INTO audit_logs (complaint_id, actor_id, action, previous_status, new_status,"
        " previous_level, new_level, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (complaint_id, actor_id, action, previous_status, new_status,
         previous_level, new_level, timestamp),
    )
    return cur.lastrowid


def list_audit(conn, complaint_id, page, page_size):
    total = conn.execute("SELECT COUNT(*) FROM audit_logs WHERE complaint_id = ?",
                         (complaint_id,)).fetchone()[0]
    rows = conn.execute(
        "SELECT * FROM audit_logs WHERE complaint_id = ?"
        " ORDER BY timestamp ASC, audit_id ASC LIMIT ? OFFSET ?",
        (complaint_id, page_size, (page - 1) * page_size),
    ).fetchall()
    return rows, total


# ---- notifications -------------------------------------------------------

def insert_notification(conn, complaint_id, target_level, event, created_at):
    conn.execute(
        "INSERT INTO notifications (complaint_id, target_level, event, created_at)"
        " VALUES (?, ?, ?, ?)",
        (complaint_id, target_level, event, created_at),
    )


def list_notifications(conn, target_level, page, page_size):
    total = conn.execute("SELECT COUNT(*) FROM notifications WHERE target_level = ?",
                         (target_level,)).fetchone()[0]
    rows = conn.execute(
        "SELECT notification_id, complaint_id, event, created_at FROM notifications"
        " WHERE target_level = ? ORDER BY created_at DESC, notification_id DESC LIMIT ? OFFSET ?",
        (target_level, page_size, (page - 1) * page_size),
    ).fetchall()
    return rows, total


# ---- feedback ------------------------------------------------------------

def insert_feedback(conn, complaint_id, rating, comment, submitted_at):
    cur = conn.execute(
        "INSERT INTO feedback (complaint_id, rating, comment, submitted_at) VALUES (?, ?, ?, ?)",
        (complaint_id, rating, comment, submitted_at),
    )
    return cur.lastrowid


def get_feedback(conn, complaint_id):
    # Deliberately no join to users: the handler projection must not expose identity.
    return conn.execute(
        "SELECT feedback_id, rating, comment, submitted_at FROM feedback WHERE complaint_id = ?",
        (complaint_id,),
    ).fetchone()


# ---- settings ------------------------------------------------------------

def get_setting(conn, key):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None
