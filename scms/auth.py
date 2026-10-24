"""AuthService (C03): registration, credentials, sessions and access policy.

Every protected use case receives a verified Actor produced here; UI
visibility is never treated as authorization.
"""
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from . import repository as repo
from .db import transaction, utc_now
from .errors import AppError, conflict, forbidden, not_found
from .routing import ROLE_TO_LEVEL
from .validation import EMAIL_RE, check_unknown, raise_if_errors, text

SESSION_LIFETIME = timedelta(hours=8)
STAFF_ROLES = ("Faculty", "Committee", "Dean")
DEFAULT_HASH_METHOD = "pbkdf2:sha256"

# Used to equalize timing when the university ID is unknown (SEC-04).
_DUMMY_HASH = generate_password_hash("not-a-real-password", method=DEFAULT_HASH_METHOD)


@dataclass(frozen=True)
class Actor:
    user_id: int
    university_id: str
    role: str
    sla_review: bool

    @property
    def level(self):
        return ROLE_TO_LEVEL.get(self.role)

    @property
    def is_student(self):
        return self.role == "Student"


# ---- registration and credentials ------------------------------------------

def register_student(conn, data, hash_method=DEFAULT_HASH_METHOD):
    """REQ-1.1: public registration always creates a Student."""
    errors = {}
    check_unknown(data, {"university_id", "name", "email", "password"}, errors)
    university_id = text(data, "university_id", 20, errors)
    name = text(data, "name", 100, errors)
    email = text(data, "email", 100, errors)
    password = data.get("password")
    if not isinstance(password, str) or not password:
        errors["password"] = "Password is required."
    if email and not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."
    raise_if_errors(errors)

    return _create_user(conn, university_id, name, email, password, "Student", False, hash_method)


def create_staff(conn, university_id, name, email, password, role, sla_review=False,
                 hash_method=DEFAULT_HASH_METHOD):
    """Trusted provisioning of Faculty / Committee / Dean accounts (not exposed over HTTP)."""
    if role not in STAFF_ROLES:
        raise AppError(422, "VALIDATION_ERROR", "Check the highlighted fields.",
                       {"role": f"Role must be one of {', '.join(STAFF_ROLES)}."})
    return _create_user(conn, university_id, name, email, password, role, sla_review, hash_method)


def _create_user(conn, university_id, name, email, password, role, sla_review, hash_method):
    password_hash = generate_password_hash(password, method=hash_method)  # salted, adaptive
    with transaction(conn):
        try:
            user_id = repo.insert_user(conn, university_id, name, email, password_hash,
                                       role, sla_review, utc_now())
        except sqlite3.IntegrityError as exc:
            raise conflict("DUPLICATE_ACCOUNT",
                           "An account with that university ID or email already exists.") from exc
    return {"user_id": user_id, "university_id": university_id, "name": name, "role": role}


def authenticate(conn, university_id, password):
    """REQ-1.2 / REQ-1.4: the same generic failure for unknown ID and wrong password."""
    user = repo.get_user_by_university_id(conn, university_id) if isinstance(university_id, str) else None
    stored = user["password_hash"] if user else _DUMMY_HASH
    ok = isinstance(password, str) and check_password_hash(stored, password)
    if not user or not ok:
        raise AppError(401, "AUTHENTICATION_FAILED", "Invalid credentials.")
    return user


# ---- sessions -------------------------------------------------------------

def _new_token():
    return secrets.token_urlsafe(32)


def create_session(conn, user_id=None):
    """Create a session row (pre-login when user_id is None). Returns (session_id, csrf_token)."""
    session_id, csrf = _new_token(), _new_token()
    expires = (datetime.now(timezone.utc) + SESSION_LIFETIME).strftime("%Y-%m-%dT%H:%M:%SZ")
    with transaction(conn):
        repo.delete_expired_sessions(conn, utc_now())
        repo.insert_session(conn, session_id, user_id, csrf, expires)
    return session_id, csrf


def load_session(conn, session_id):
    """Return the live session row or None if missing/expired."""
    if not session_id:
        return None
    row = repo.get_session(conn, session_id)
    if row is None or row["expires_at"] <= utc_now():
        return None
    return row


def login(conn, old_session_id, university_id, password):
    """Verify credentials, then rotate session id and CSRF token."""
    user = authenticate(conn, university_id, password)
    with transaction(conn):
        if old_session_id:
            repo.delete_session(conn, old_session_id)
    session_id, csrf = create_session(conn, user["user_id"])
    return user, session_id, csrf


def logout(conn, session_id):
    with transaction(conn):
        repo.delete_session(conn, session_id)


def require_actor(conn, session_row):
    """Turn a session row into a verified Actor (role always read from the database)."""
    if session_row is None or session_row["user_id"] is None:
        raise AppError(401, "AUTHENTICATION_REQUIRED", "Please sign in.")
    user = repo.get_user(conn, session_row["user_id"])
    if user is None:
        raise AppError(401, "AUTHENTICATION_REQUIRED", "Please sign in.")
    return Actor(user["user_id"], user["university_id"], user["role"], bool(user["sla_review"]))


# ---- access policy ----------------------------------------------------------

def is_owner(actor, complaint):
    return actor.is_student and complaint["student_id"] == actor.user_id


def can_view(conn, actor, complaint):
    """Owner, or a handler level that currently holds or previously held the complaint.

    Historic assignment grants read access only (REQ-6.2); it never grants mutation.
    """
    if is_owner(actor, complaint):
        return True
    if actor.level is None:
        return False
    return (complaint["current_level"] == actor.level
            or repo.has_assignment_level(conn, complaint["complaint_id"], actor.level))


def can_act(actor, complaint):
    """REQ-4.4: only the handler level currently assigned may Resolve/Reject/Escalate."""
    return actor.level is not None and complaint["current_level"] == actor.level


def require_visible(conn, actor, complaint_id):
    complaint = repo.get_complaint(conn, complaint_id)
    if complaint is None or not can_view(conn, actor, complaint):
        raise not_found()
    return complaint


def require_handler_role(actor):
    if actor.level is None:
        raise forbidden()


def require_student(actor):
    if not actor.is_student:
        raise forbidden()


def can_review_sla(actor):
    return actor.role == "Dean" and actor.sla_review


def require_sla_review(actor):
    if not can_review_sla(actor):
        raise forbidden("SLA review permission is required.")
