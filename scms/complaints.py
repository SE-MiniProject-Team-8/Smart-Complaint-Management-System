"""ComplaintService (C04): owns every complaint use case and its transaction boundary.

Each mutation runs in ONE transaction that checks the actor, the legal state
transition and the expected version, then writes the complaint, assignment
history, audit entry and notification together. Any failure rolls all of it
back, and the caller only reports success after the commit (NFR-REL-02).
"""
import sqlite3

from . import audit, auth, routing
from . import repository as repo
from .db import transaction, utc_now
from .errors import conflict, forbidden, not_found
from .validation import check_unknown, integer, raise_if_errors, text

ACTIONABLE_STATUSES = ("Submitted", "Escalated", "Under Appeal Review")
TERMINAL_STATUSES = ("Resolved", "Rejected")
ALL_STATUSES = ACTIONABLE_STATUSES + TERMINAL_STATUSES


# ---- projections ------------------------------------------------------------

def summary(c):
    return {
        "complaint_id": c["complaint_id"],
        "category": c["category"],
        "severity": c["severity"],
        "status": c["status"],
        "current_level": c["current_level"],
        "assigned_role": routing.display_name(c["current_level"]),
        "submitted_at": c["submitted_at"],
        "status_updated_at": c["status_updated_at"],
        "version": c["version"],
    }


def allowed_actions(conn, actor, c):
    """UI hint only; every action is re-authorized server-side."""
    actions = []
    if auth.can_act(actor, c) and c["status"] in ACTIONABLE_STATUSES:
        actions += ["resolve", "reject"]
        if c["current_level"] < routing.LEVEL_DEAN:
            actions.append("escalate")
    if auth.is_owner(actor, c):
        if c["status"] == "Rejected" and not c["appealed"]:
            actions.append("appeal")
        if c["status"] == "Resolved" and repo.get_feedback(conn, c["complaint_id"]) is None:
            actions.append("feedback")
    return actions


def detail(conn, actor, c):
    data = summary(c)
    data.update({
        "description": c["description"],
        "appealed": bool(c["appealed"]),
        "final_review": bool(c["final_review"]),
        "resolution_remarks": c["resolution_remarks"],
        "rejection_reason": c["rejection_reason"],
        "allowed_actions": allowed_actions(conn, actor, c),
    })
    return data


# ---- use cases --------------------------------------------------------------

def submit(conn, actor, data):
    """REQ-2.1 to REQ-3.3: validate, route by severity, persist atomically."""
    auth.require_student(actor)
    errors = {}
    check_unknown(data, {"category", "description", "severity"}, errors)
    category = text(data, "category", 50, errors)
    description = text(data, "description", 1000, errors)
    severity = data.get("severity")
    if severity not in routing.SEVERITIES:
        errors["severity"] = "Severity must be Low, Medium, or High."
    raise_if_errors(errors)

    level = routing.initial_level(severity)
    now = utc_now()
    with transaction(conn):
        cid = repo.insert_complaint(conn, actor.user_id, category, description, severity, level, now)
        repo.insert_assignment(conn, cid, level, actor.user_id, now)
        audit.record(conn, cid, actor.user_id, "SUBMIT", audit.INITIAL_STATE, "Submitted",
                     None, level)
        repo.insert_notification(conn, cid, level, "SUBMITTED", now)
        complaint = repo.get_complaint(conn, cid)
    return summary(complaint)


def get_detail(conn, actor, complaint_id):
    c = auth.require_visible(conn, actor, complaint_id)
    return detail(conn, actor, c)


def _load_for_handler(conn, actor, complaint_id, data, extra_fields):
    """Shared preamble for Resolve / Reject / Escalate."""
    c = auth.require_visible(conn, actor, complaint_id)
    if not auth.can_act(actor, c):
        raise forbidden("This complaint is not assigned to your role.")
    errors = {}
    check_unknown(data, {"expected_version", *extra_fields}, errors)
    return c, errors


def _require_active(c):
    if c["status"] not in ACTIONABLE_STATUSES:
        raise conflict("INVALID_STATE", f"A {c['status']} complaint cannot be actioned.")


def _stale():
    return conflict("STALE_VERSION", "The complaint changed. Refresh and try again.")


def resolve(conn, actor, complaint_id, data):
    """REQ-4.1: Resolve requires non-blank remarks."""
    with transaction(conn):
        c, errors = _load_for_handler(conn, actor, complaint_id, data, {"remarks"})
        remarks = text(data, "remarks", 500, errors)
        version = integer(data, "expected_version", errors, minimum=1)
        raise_if_errors(errors)
        _require_active(c)

        now = utc_now()
        if repo.update_complaint_state(conn, complaint_id, version, now,
                                       status="Resolved", resolution_remarks=remarks) != 1:
            raise _stale()
        audit.record(conn, complaint_id, actor.user_id, "RESOLVE", c["status"], "Resolved",
                     c["current_level"], c["current_level"])
        updated = repo.get_complaint(conn, complaint_id)
    return detail(conn, actor, updated)


def reject(conn, actor, complaint_id, data):
    """REQ-4.2: Reject requires a reason and records the rejecting level for appeals."""
    with transaction(conn):
        c, errors = _load_for_handler(conn, actor, complaint_id, data, {"reason"})
        reason = text(data, "reason", 500, errors)
        version = integer(data, "expected_version", errors, minimum=1)
        raise_if_errors(errors)
        _require_active(c)

        now = utc_now()
        if repo.update_complaint_state(conn, complaint_id, version, now, status="Rejected",
                                       rejection_reason=reason,
                                       rejected_level=c["current_level"]) != 1:
            raise _stale()
        audit.record(conn, complaint_id, actor.user_id, "REJECT", c["status"], "Rejected",
                     c["current_level"], c["current_level"])
        updated = repo.get_complaint(conn, complaint_id)
    return detail(conn, actor, updated)


def _escalate_in_transaction(conn, actor, c, expected_version, action):
    """Move to the next level; shared by normal and SLA escalation."""
    _require_active(c)
    target = routing.next_level(c["current_level"])  # raises ESCALATION_LIMIT at L3
    now = utc_now()
    if repo.update_complaint_state(conn, c["complaint_id"], expected_version, now,
                                   status="Escalated", current_level=target) != 1:
        raise _stale()
    repo.insert_assignment(conn, c["complaint_id"], target, actor.user_id, now)
    repo.insert_notification(conn, c["complaint_id"], target, "ESCALATED", now)
    audit.record(conn, c["complaint_id"], actor.user_id, action, c["status"], "Escalated",
                 c["current_level"], target)
    return repo.get_complaint(conn, c["complaint_id"])


def escalate(conn, actor, complaint_id, data):
    """REQ-4.3: escalate one level; the Dean cannot escalate further."""
    with transaction(conn):
        c, errors = _load_for_handler(conn, actor, complaint_id, data, set())
        version = integer(data, "expected_version", errors, minimum=1)
        raise_if_errors(errors)
        updated = _escalate_in_transaction(conn, actor, c, version, "ESCALATE")
    return detail(conn, actor, updated)


def appeal(conn, actor, complaint_id, data):
    """REQ-5.1 to REQ-5.4: the owning Student may appeal a Rejected complaint once."""
    with transaction(conn):
        c = auth.require_visible(conn, actor, complaint_id)
        if not auth.is_owner(actor, c):
            raise not_found()
        errors = {}
        check_unknown(data, {"justification", "expected_version"}, errors)
        justification = text(data, "justification", 1000, errors)
        version = integer(data, "expected_version", errors, minimum=1)
        raise_if_errors(errors)

        if c["appealed"]:
            raise conflict("APPEAL_ALREADY_USED", "Only one appeal is permitted.")
        if c["status"] != "Rejected":
            raise conflict("NOT_REJECTED", "Only Rejected complaints can be appealed.")

        rejected_level = c["rejected_level"] or c["current_level"]
        target, final_review = routing.appeal_target(rejected_level)
        now = utc_now()
        # Conditional update + UNIQUE(appeals.complaint_id) stop concurrent duplicate appeals.
        if repo.update_complaint_state(conn, complaint_id, version, now,
                                       status="Under Appeal Review", current_level=target,
                                       appealed=1, final_review=int(final_review)) != 1:
            raise _stale()
        try:
            appeal_id = repo.insert_appeal(conn, complaint_id, actor.user_id, justification, now,
                                           rejected_level, target, final_review)
        except sqlite3.IntegrityError as exc:
            raise conflict("APPEAL_ALREADY_USED", "Only one appeal is permitted.") from exc
        repo.insert_assignment(conn, complaint_id, target, actor.user_id, now)
        repo.insert_notification(conn, complaint_id, target, "APPEALED", now)
        audit.record(conn, complaint_id, actor.user_id, "APPEAL", "Rejected", "Under Appeal Review",
                     c["current_level"], target)
        updated = repo.get_complaint(conn, complaint_id)
    return {
        "appeal_id": appeal_id,
        "complaint_id": complaint_id,
        "status": updated["status"],
        "current_level": updated["current_level"],
        "assigned_role": routing.display_name(updated["current_level"]),
        "final_review": bool(updated["final_review"]),
        "appealed": True,
        "version": updated["version"],
    }
