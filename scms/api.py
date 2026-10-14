"""Web API and presentation boundary (C02).

Routes parse and validate requests, enforce the session/CSRF guard and call the
service modules. They contain no SQL and no business rules.
"""
import json
import logging
import secrets
import time
import uuid

from flask import Blueprint, current_app, g, jsonify, request, session
from werkzeug.exceptions import HTTPException

from . import audit, auth, complaints, db, feedback, queries
from .errors import AppError
from .validation import paging

bp = Blueprint("api", __name__)
request_log = logging.getLogger("scms.request")
error_log = logging.getLogger("scms.error")

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


# ---- request plumbing -----------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = db.connect(current_app.config["DATABASE"])
    return g.db


def ok(data, status=200, headers=None):
    return jsonify({"data": data}), status, headers or {}


def page_response(items, total, page, page_size):
    return jsonify({"data": items, "page": page, "page_size": page_size, "total": total})


def body(optional=False):
    """Parse a JSON object body (400 malformed, 415 wrong content type)."""
    if optional and not request.get_data():
        return {}
    if request.mimetype != "application/json":
        raise AppError(415, "UNSUPPORTED_MEDIA_TYPE", "Content-Type must be application/json.")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AppError(400, "MALFORMED_JSON", "Request body must be a JSON object.")
    return data


def current_actor():
    return auth.require_actor(get_db(), g.session_row)


@bp.before_request
def guard():
    g.session_row = auth.load_session(get_db(), session.get("sid"))
    if request.method in UNSAFE_METHODS:
        row = g.session_row
        if row is None:
            if request.endpoint == "api.logout":
                raise AppError(401, "AUTHENTICATION_REQUIRED", "Your session has expired.")
            raise AppError(403, "CSRF_FAILED", "Missing or invalid CSRF token.")
        supplied = request.headers.get("X-CSRF-Token", "")
        if not secrets.compare_digest(supplied, row["csrf_token"]):
            raise AppError(403, "CSRF_FAILED", "Missing or invalid CSRF token.")


# ---- A: accounts and sessions ----------------------------------------------------

@bp.post("/users")
def register():
    user = auth.register_student(get_db(), body(),
                                 hash_method=current_app.config["PASSWORD_HASH_METHOD"])
    return ok(user, 201)


@bp.get("/session")
def session_info():
    row = g.session_row
    if row is None:
        session_id, csrf = auth.create_session(get_db())
        session["sid"] = session_id
        return ok({"authenticated": False, "user_id": None, "role": None, "csrf_token": csrf})
    if row["user_id"] is None:
        return ok({"authenticated": False, "user_id": None, "role": None,
                   "csrf_token": row["csrf_token"]})
    actor = current_actor()
    return ok({"authenticated": True, "user_id": actor.user_id, "role": actor.role,
               "csrf_token": row["csrf_token"]})


@bp.post("/session")
def login():
    data = body()
    user, session_id, csrf = auth.login(get_db(), session.get("sid"),
                                        data.get("university_id"), data.get("password"))
    session["sid"] = session_id
    return ok({"user_id": user["user_id"], "role": user["role"], "csrf_token": csrf})


@bp.delete("/session")
def logout():
    auth.logout(get_db(), session.pop("sid", None))
    return "", 204


# ---- C: complaints -----------------------------------------------------------------

@bp.post("/complaints")
def create_complaint():
    created = complaints.submit(get_db(), current_actor(), body())
    location = f"{request.script_root}/api/v1/complaints/{created['complaint_id']}"
    return ok(created, 201, {"Location": location})


@bp.get("/complaints")
def list_complaints():
    actor = current_actor()
    page, page_size = paging(request.args)
    items, total = queries.list_visible(get_db(), actor, request.args.get("status"),
                                        page, page_size)
    return page_response(items, total, page, page_size)


@bp.get("/complaints/<int:complaint_id>")
def complaint_detail(complaint_id):
    return ok(complaints.get_detail(get_db(), current_actor(), complaint_id))


# ---- W: handler actions and appeals ---------------------------------------------------

@bp.post("/complaints/<int:complaint_id>/resolve")
def resolve(complaint_id):
    return ok(complaints.resolve(get_db(), current_actor(), complaint_id, body()))


@bp.post("/complaints/<int:complaint_id>/reject")
def reject(complaint_id):
    return ok(complaints.reject(get_db(), current_actor(), complaint_id, body()))


@bp.post("/complaints/<int:complaint_id>/escalate")
def escalate(complaint_id):
    return ok(complaints.escalate(get_db(), current_actor(), complaint_id, body()))


@bp.post("/complaints/<int:complaint_id>/appeals")
def appeal(complaint_id):
    return ok(complaints.appeal(get_db(), current_actor(), complaint_id, body()), 201)


# ---- Q: audit, SLA, notifications, feedback ------------------------------------------------

@bp.get("/complaints/<int:complaint_id>/audit")
def audit_history(complaint_id):
    actor = current_actor()
    page, page_size = paging(request.args)
    items, total = audit.history(get_db(), actor, complaint_id, page, page_size)
    return page_response(items, total, page, page_size)


@bp.post("/sla/check")
def sla_check():
    body(optional=True)  # {} only; the threshold cannot be changed by the request
    return ok(queries.sla_check(get_db(), current_actor()))


@bp.post("/sla/complaints/<int:complaint_id>/escalate")
def sla_escalate(complaint_id):
    return ok(queries.sla_escalate(get_db(), current_actor(), complaint_id, body()))


@bp.get("/notifications")
def notifications():
    actor = current_actor()
    page, page_size = paging(request.args)
    items, total = queries.notifications(get_db(), actor, page, page_size)
    return page_response(items, total, page, page_size)


@bp.post("/complaints/<int:complaint_id>/feedback")
def submit_feedback(complaint_id):
    return ok(feedback.submit(get_db(), current_actor(), complaint_id, body()), 201)


@bp.get("/complaints/<int:complaint_id>/feedback")
def get_feedback(complaint_id):
    return ok(feedback.get(get_db(), current_actor(), complaint_id))


# ---- hooks, logging and errors -----------------------------------------------------------------

def register_request_hooks(app):
    @app.before_request
    def start():
        g.request_id = uuid.uuid4().hex[:12]
        g.started = time.perf_counter()
        g.error_code = None

    @app.after_request
    def finish(response):
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        # Operational log: never request bodies, cookies, tokens or complaint text.
        request_log.info(json.dumps({
            "request_id": getattr(g, "request_id", None),
            "timestamp": db.utc_now(),
            "route": request.url_rule.rule if request.url_rule else request.path,
            "method": request.method,
            "status": response.status_code,
            "elapsed_ms": round((time.perf_counter() - getattr(g, "started", time.perf_counter())) * 1000, 1),
            "error_code": getattr(g, "error_code", None),
        }))
        return response

    @app.teardown_appcontext
    def close_db(_exc):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    @app.get("/healthz")
    def healthz():
        # Readiness check: a lightweight query that exposes no records.
        try:
            get_db().execute("SELECT 1").fetchone()
        except Exception:
            return jsonify({"status": "unavailable"}), 503
        return jsonify({"status": "ok"})


def _error_response(status, code, message, fields=None):
    g.error_code = code
    payload = {"code": code, "message": message,
               "request_id": getattr(g, "request_id", "unknown")}
    if fields:
        payload["fields"] = fields
    return jsonify({"error": payload}), status


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(exc):
        return _error_response(exc.status, exc.code, exc.message, exc.fields)

    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.code, "HTTP_ERROR")
        message = "Resource not found." if exc.code == 404 else exc.name
        return _error_response(exc.code, code, message)

    @app.errorhandler(Exception)
    def handle_unexpected(exc):
        # Redacted: exception type only, no message/SQL/request content.
        error_log.error("unhandled %s request_id=%s", type(exc).__name__,
                        getattr(g, "request_id", "unknown"))
        return _error_response(500, "INTERNAL_ERROR",
                               "Something went wrong. Quote the reference ID if you contact support.")
