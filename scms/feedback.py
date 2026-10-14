"""Feedback module (C07): REQ-9.1 and REQ-9.2.

Feedback rows hold the complaint link and no student_id, and the handler-facing
projection never joins to users, so the submitter's identity is not returned.
"""
import sqlite3

from . import auth
from . import repository as repo
from .db import transaction, utc_now
from .errors import conflict, not_found
from .validation import check_unknown, integer, raise_if_errors, text


def submit(conn, actor, complaint_id, data):
    with transaction(conn):
        c = auth.require_visible(conn, actor, complaint_id)
        if not auth.is_owner(actor, c):
            raise not_found()

        errors = {}
        check_unknown(data, {"rating", "comment"}, errors)
        rating = integer(data, "rating", errors, minimum=1, maximum=5)
        if "rating" in errors:
            errors["rating"] = "Rating must be an integer between 1 and 5."
        comment = text(data, "comment", 500, errors, required=False)
        raise_if_errors(errors)

        if c["status"] != "Resolved":
            raise conflict("INVALID_STATE", "Feedback can only be submitted for Resolved complaints.")
        now = utc_now()
        try:
            feedback_id = repo.insert_feedback(conn, complaint_id, rating, comment or None, now)
        except sqlite3.IntegrityError as exc:
            raise conflict("FEEDBACK_ALREADY_EXISTS",
                           "Feedback has already been submitted for this complaint.") from exc
    return {"feedback_id": feedback_id, "rating": rating, "submitted_at": now}


def get(conn, actor, complaint_id):
    """Owner or an authorized handler level; the projection carries no identity."""
    auth.require_visible(conn, actor, complaint_id)
    row = repo.get_feedback(conn, complaint_id)
    if row is None:
        raise not_found()
    return {"rating": row["rating"], "comment": row["comment"],
            "submitted_at": row["submitted_at"]}
