"""Audit module (C06): append-only business history (REQ-6.1 to REQ-6.3, SEC-03).

`record` is called inside the caller's transaction so a state change and its
audit entry commit together or not at all. There is deliberately no update or
delete function; database triggers also reject UPDATE/DELETE on audit_logs.
"""
from . import auth
from . import repository as repo
from .db import utc_now

INITIAL_STATE = "NONE"  # sentinel previous_status for the submission entry (<= 30 chars)


def record(conn, complaint_id, actor_id, action, previous_status, new_status,
           previous_level=None, new_level=None):
    return repo.insert_audit(conn, complaint_id, actor_id, action, previous_status, new_status,
                             previous_level, new_level, utc_now())


def history(conn, actor, complaint_id, page, page_size):
    """Chronological history for the owner or a handler level that held the complaint."""
    auth.require_visible(conn, actor, complaint_id)
    rows, total = repo.list_audit(conn, complaint_id, page, page_size)
    items = [{
        "audit_id": r["audit_id"],
        "actor_id": r["actor_id"],
        "action": r["action"],
        "previous_status": r["previous_status"],
        "new_status": r["new_status"],
        "previous_level": r["previous_level"],
        "new_level": r["new_level"],
        "timestamp": r["timestamp"],
    } for r in rows]
    return items, total
