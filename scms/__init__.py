"""Smart Complaint Management System: layered modular monolith (Flask + SQLite).

Modules (Section 3 component ids):
    api.py         C02  routes, request parsing, session/CSRF guard
    auth.py        C03  registration, credentials, sessions, access policy
    complaints.py  C04  complaint use cases and transaction boundary
    routing.py     C05  pure routing decisions (levels, appeal target)
    audit.py       C06  append-only audit history
    feedback.py    C07  resolved-complaint feedback
    queries.py     C08  dashboards, manual SLA review, notifications
    repository.py  C09  all SQL; db.py owns connections and transactions
"""
import os
from pathlib import Path

from . import db
from .api import bp as api_blueprint
from .api import register_error_handlers, register_request_hooks
from .cli import register_cli


def create_app(test_config=None):
    from flask import Flask

    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("SCMS_DATABASE", str(Path("instance") / "scms.db")),
        SECRET_KEY=os.environ.get("SCMS_SECRET_KEY"),
        # Secure cookies are the default; set SCMS_INSECURE_COOKIES=1 for plain-HTTP local dev only.
        SESSION_COOKIE_SECURE=os.environ.get("SCMS_INSECURE_COOKIES") != "1",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PASSWORD_HASH_METHOD="pbkdf2:sha256",
    )
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SCMS_SECRET_KEY must be set (keep it outside source control).")

    # Records live in a SQLite file, so they survive application restarts (NFR-REL-01).
    db.init_db(app.config["DATABASE"])

    app.register_blueprint(api_blueprint, url_prefix="/api/v1")
    register_request_hooks(app)
    register_error_handlers(app)
    register_cli(app)
    return app
