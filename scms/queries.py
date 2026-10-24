"""Query module (C08): dashboards, manual SLA review and notifications.

Reads use role-scoped filters (REQ-7.x). SLA review is manual and
permission-protected (REQ-8.x); no background scheduler exists.
"""
from datetime import datetime, timedelta, timezone

from . import auth, routing
from . import repository as repo
from . import complaints
from .db import transaction, utc_now
from .errors import conflict, not_found, validation_error
from .validation import check_unknown, integer, raise_if_errors


# ---- dashboards ---------------------------------------------------------------

def list_visible(conn, actor, status, page, page_size):
    """Students: own complaints. Faculty/Committee: current queue.
    Dean: complaints that reached L3 (never complaints resolved at earlier levels)."""
    if status is not None and status not in complaints.ALL_STATUSES:
        raise validation_error({"status": "Unsupported status."})

    if actor.is_student:
        where, params = "student_id = ?", [actor.user_id]
    else:
        where, params = "current_level = ?", [actor.level]
    if status is not None:
        where += " AND status = ?"
        params.append(status)

    rows, total = repo.list_complaints(conn, where, params, page, page_size)
    return [complaints.summary(r) for r in rows], total


# ---- notifications ------------------------------------------------------------

def notifications(conn, actor, page, page_size):
    auth.require_handler_role(actor)
    rows, total = repo.list_notifications(conn, actor.level, page, page_size)
    return [dict(r) for r in rows], total


# ---- SLA ----------------------------------------------------------------------

def _threshold_days(conn):
    value = repo.get_setting(conn, "sla_threshold_days")
    try:
        days = int(value)
    except (TypeError, ValueError):
        days = 7
    return days if days > 0 else 7


def _elapsed_days(status_updated_at, now):
    updated = datetime.strptime(status_updated_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (now - updated).total_seconds() / 86400


def sla_check(conn, actor, now=None):
    """REQ-8.1: list active complaints whose time in the current status exceeds the threshold."""
    auth.require_sla_review(actor)
    now = now or datetime.now(timezone.utc)
    threshold = _threshold_days(conn)
    cutoff = (now - timedelta(days=threshold)).strftime("%Y-%m-%dT%H:%M:%SZ")
    items = []
    for c in repo.list_overdue_candidates(conn, cutoff=cutoff):
        elapsed = _elapsed_days(c["status_updated_at"], now)
        if elapsed > threshold:
            items.append({
                "complaint_id": c["complaint_id"],
                "version": c["version"],
                "status": c["status"],
                "current_handler": routing.display_name(c["current_level"]),
                "days_overdue": max(0, int(elapsed - threshold)),
                "can_escalate": c["current_level"] < routing.LEVEL_DEAN,
            })
    return {"checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "threshold_days": threshold, "items": items}


def sla_escalate(conn, actor, complaint_id, data, now=None):
    """REQ-8.2: narrowly scoped overdue escalation. Rechecks permission, threshold,
    active state and version, then delegates the next level to RoutingPolicy."""
    auth.require_sla_review(actor)
    errors = {}
    check_unknown(data, {"expected_version"}, errors)
    version = integer(data, "expected_version", errors, minimum=1)
    raise_if_errors(errors)

    now = now or datetime.now(timezone.utc)
    with transaction(conn):
        c = repo.get_complaint(conn, complaint_id)
        if c is None:
            raise not_found()
        if c["status"] not in complaints.ACTIONABLE_STATUSES:
            raise conflict("INVALID_STATE", f"A {c['status']} complaint cannot be escalated.")
        if _elapsed_days(c["status_updated_at"], now) <= _threshold_days(conn):
            raise conflict("INVALID_STATE", "The complaint is not overdue.")
        updated = complaints._escalate_in_transaction(conn, actor, c, version, "SLA_ESCALATE")
    # The SLA capability permits escalation across queues, not reading their details.
    return complaints.summary(updated)
