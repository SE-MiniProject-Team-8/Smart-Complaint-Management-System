"""Tests against the real Flask + SQLite application (not the in-memory simulation).

Run from the repository root:  python -m unittest discover -s tests -v
"""
import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from scms import auth, create_app, db, routing

API = "/api/v1"
HASH = "pbkdf2:sha256:1000"  # cheap hash so tests stay fast; production default is stronger
PASSWORD = "Pass@1234"


def make_app(path):
    return create_app({
        "TESTING": True,
        "DATABASE": path,
        "SECRET_KEY": "test-secret",
        "SESSION_COOKIE_SECURE": False,
        "PASSWORD_HASH_METHOD": HASH,
    })


class ApiClient:
    """Browser stand-in: keeps the session cookie and CSRF token like the real UI."""

    def __init__(self, app):
        self.http = app.test_client()
        self.csrf = None
        self.start()

    def start(self):
        self.csrf = self.http.get(f"{API}/session").json["data"]["csrf_token"]

    def request(self, method, path, payload=None, csrf=True):
        headers = {"X-CSRF-Token": self.csrf} if (csrf and self.csrf) else {}
        kwargs = {"headers": headers}
        if payload is not None:
            kwargs["json"] = payload
        return self.http.open(f"{API}{path}", method=method, **kwargs)

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, payload=None, csrf=True):
        return self.request("POST", path, {} if payload is None else payload, csrf)

    def delete(self, path):
        return self.request("DELETE", path)

    def login(self, university_id, password=PASSWORD):
        response = self.post("/session", {"university_id": university_id, "password": password})
        if response.status_code == 200:
            self.csrf = response.json["data"]["csrf_token"]
        return response


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "scms.db")
        self.app = make_app(self.db_path)
        conn = db.connect(self.db_path)
        for uid, role, sla in [("FAC001", "Faculty", False), ("GC001", "Committee", False),
                               ("DEAN01", "Dean", True), ("DEAN02", "Dean", False)]:
            auth.create_staff(conn, uid, uid, f"{uid.lower()}@univ.edu", PASSWORD, role, sla, HASH)
        conn.close()
        self.alice = self.student("STU001", "Alice")
        self.bob = self.student("STU002", "Bob")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # helpers
    def student(self, uid, name):
        client = ApiClient(self.app)
        response = client.post("/users", {"university_id": uid, "name": name,
                                          "email": f"{uid.lower()}@univ.edu", "password": PASSWORD})
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(client.login(uid).status_code, 200)
        return client

    def staff(self, uid):
        client = ApiClient(self.app)
        self.assertEqual(client.login(uid).status_code, 200)
        return client

    def submit(self, client=None, severity="Low", category="Facilities", description="Fan broken"):
        response = (client or self.alice).post("/complaints", {
            "category": category, "description": description, "severity": severity})
        self.assertEqual(response.status_code, 201, response.json)
        return response.json["data"]

    def raw(self):
        return db.connect(self.db_path)

    def count(self, table):
        conn = self.raw()
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            conn.close()

    def backdate(self, complaint_id, days):
        stamp = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn = self.raw()
        conn.execute("UPDATE complaints SET status_updated_at = ? WHERE complaint_id = ?",
                     (stamp, complaint_id))
        conn.close()


class PersistenceTests(Base):
    """Issue #12: complaint records survive normal application restarts."""

    def test_records_survive_application_restart(self):
        first = self.submit(severity="Low")
        second = self.submit(severity="High", description="Grade discrepancy")
        fac = self.staff("FAC001")
        resolved = fac.post(f"/complaints/{first['complaint_id']}/resolve",
                            {"remarks": "Fan replaced", "expected_version": 1})
        self.assertEqual(resolved.status_code, 200)
        self.alice.post(f"/complaints/{first['complaint_id']}/feedback", {"rating": 5, "comment": "Quick"})

        # "Restart": a brand-new application object on the same database file.
        restarted = make_app(self.db_path)
        alice = ApiClient(restarted)
        self.assertEqual(alice.login("STU001").status_code, 200)  # password hash survived

        listing = alice.get("/complaints").json
        self.assertEqual(listing["total"], 2)
        by_id = {c["complaint_id"]: c for c in listing["data"]}
        self.assertEqual(by_id[first["complaint_id"]]["status"], "Resolved")
        self.assertEqual(by_id[second["complaint_id"]]["current_level"], 2)

        audit = alice.get(f"/complaints/{first['complaint_id']}/audit").json["data"]
        self.assertEqual([a["action"] for a in audit], ["SUBMIT", "RESOLVE"])
        self.assertEqual(alice.get(f"/complaints/{first['complaint_id']}/feedback").json["data"]["rating"], 5)

        # IDs come from the database, so they keep increasing after a restart.
        third = self.submit(alice, severity="Medium")
        self.assertGreater(third["complaint_id"], second["complaint_id"])

    def test_staff_session_state_not_trusted_from_cookie(self):
        # Role is read from the database for every request, not from the browser.
        self.assertEqual(self.alice.get("/notifications").status_code, 403)

    def test_init_db_is_idempotent_and_keeps_data(self):
        self.submit()
        db.init_db(self.db_path)
        db.init_db(self.db_path)
        self.assertEqual(self.count("complaints"), 1)


class ModuleBoundaryTests(unittest.TestCase):
    """Routing rules live in one pure module (NFR-MAIN-01)."""

    def test_initial_level(self):
        self.assertEqual(routing.initial_level("Low"), 1)
        self.assertEqual(routing.initial_level("Medium"), 1)
        self.assertEqual(routing.initial_level("High"), 2)
        with self.assertRaises(ValueError):
            routing.initial_level("Urgent")

    def test_next_level_and_dean_ceiling(self):
        self.assertEqual(routing.next_level(1), 2)
        self.assertEqual(routing.next_level(2), 3)
        with self.assertRaises(routing.AppError) as ctx:
            routing.next_level(3)
        self.assertEqual(ctx.exception.code, "ESCALATION_LIMIT")

    def test_appeal_target(self):
        self.assertEqual(routing.appeal_target(1), (2, False))
        self.assertEqual(routing.appeal_target(2), (3, False))
        self.assertEqual(routing.appeal_target(3), (3, True))


class AuthTests(Base):
    def test_unknown_id_and_wrong_password_are_indistinguishable(self):
        client = ApiClient(self.app)
        wrong = client.login("STU001", "WrongPassword")
        unknown = client.login("NOBODY", "WrongPassword")
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.json["error"]["message"], "Invalid credentials.")
        self.assertEqual(wrong.json["error"]["message"], unknown.json["error"]["message"])
        self.assertEqual(wrong.json["error"]["code"], "AUTHENTICATION_FAILED")

    def test_password_is_salted_hash_and_never_returned(self):
        conn = self.raw()
        stored = conn.execute("SELECT password_hash FROM users WHERE university_id='STU001'").fetchone()[0]
        conn.close()
        self.assertNotIn(PASSWORD, stored)
        self.assertTrue(stored.startswith("pbkdf2:sha256"))
        self.assertLessEqual(len(stored), 255)
        response = ApiClient(self.app).post("/users", {"university_id": "S9", "name": "N",
                                                       "email": "n@x.edu", "password": PASSWORD})
        self.assertNotIn("password", response.get_data(as_text=True).lower())

    def test_registration_cannot_choose_role_and_duplicates_conflict(self):
        client = ApiClient(self.app)
        elevated = client.post("/users", {"university_id": "X1", "name": "X", "email": "x@x.edu",
                                          "password": PASSWORD, "role": "Dean"})
        self.assertEqual(elevated.status_code, 422)
        self.assertIn("role", elevated.json["error"]["fields"])
        dup = client.post("/users", {"university_id": "STU001", "name": "Dup", "email": "dup@x.edu",
                                     "password": PASSWORD})
        self.assertEqual(dup.status_code, 409)
        self.assertEqual(dup.json["error"]["code"], "DUPLICATE_ACCOUNT")

    def test_csrf_login_rotation_and_logout(self):
        bare = ApiClient(self.app)
        self.assertEqual(bare.post("/session", {"university_id": "STU001", "password": PASSWORD},
                                   csrf=False).status_code, 403)
        self.assertEqual(self.alice.get("/complaints").status_code, 200)

        # Login rotates the session id and CSRF token; the pre-login token stops working.
        client = ApiClient(self.app)
        pre_login_csrf = client.csrf
        self.assertEqual(client.login("FAC001").status_code, 200)
        self.assertNotEqual(client.csrf, pre_login_csrf)
        client.csrf = pre_login_csrf
        self.assertEqual(client.post("/complaints", {}).status_code, 403)
        conn = self.raw()
        anonymous = conn.execute("SELECT COUNT(*) FROM sessions WHERE user_id IS NULL AND csrf_token = ?",
                                 (pre_login_csrf,)).fetchone()[0]
        conn.close()
        self.assertEqual(anonymous, 0)

        # Logout deletes the server-side session.
        self.assertEqual(self.alice.delete("/session").status_code, 204)
        self.assertEqual(self.alice.get("/complaints").status_code, 401)

    def test_protected_routes_require_login(self):
        anon = ApiClient(self.app)
        self.assertEqual(anon.get("/complaints").status_code, 401)
        self.assertEqual(anon.post("/complaints", {"category": "a", "description": "b",
                                                   "severity": "Low"}).status_code, 401)


class SubmissionTests(Base):
    def test_severity_routing(self):
        low = self.submit(severity="Low")
        medium = self.submit(severity="Medium")
        high = self.submit(severity="High")
        self.assertEqual((low["current_level"], low["assigned_role"]), (1, "Faculty-in-Charge"))
        self.assertEqual(medium["current_level"], 1)
        self.assertEqual((high["current_level"], high["assigned_role"]), (2, "Grievance Committee"))
        self.assertEqual(low["status"], "Submitted")
        self.assertEqual(low["version"], 1)

    def test_submission_writes_complaint_history_audit_and_notice_together(self):
        c = self.submit(severity="High")
        self.assertEqual(self.count("complaints"), 1)
        self.assertEqual(self.count("assignment_history"), 1)
        self.assertEqual(self.count("audit_logs"), 1)
        notice = self.staff("GC001").get("/notifications").json
        self.assertEqual(notice["total"], 1)
        self.assertEqual(notice["data"][0]["complaint_id"], c["complaint_id"])

    def test_invalid_input_leaves_no_records(self):
        for payload in [
            {"category": "", "description": "x", "severity": "Low"},
            {"category": "A", "description": "   ", "severity": "Low"},
            {"category": "A", "description": "x", "severity": "Urgent"},
            {"category": "A" * 51, "description": "x", "severity": "Low"},
            {"category": "A", "description": "x" * 1001, "severity": "Low"},
            {"category": "A", "description": "x", "severity": "Low", "status": "Resolved"},
        ]:
            response = self.alice.post("/complaints", payload)
            self.assertEqual(response.status_code, 422, payload)
            self.assertEqual(response.json["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(self.count("complaints"), 0)
        self.assertEqual(self.count("audit_logs"), 0)

    def test_only_students_submit(self):
        response = self.staff("FAC001").post("/complaints", {"category": "A", "description": "x",
                                                              "severity": "Low"})
        self.assertEqual(response.status_code, 403)

    def test_failed_write_rolls_back_everything(self):
        with mock.patch("scms.audit.record", side_effect=sqlite3.OperationalError("disk I/O error")):
            response = self.alice.post("/complaints", {"category": "A", "description": "x",
                                                       "severity": "Low"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["error"]["code"], "PERSISTENCE_UNAVAILABLE")
        for table in ("complaints", "assignment_history", "audit_logs", "notifications"):
            self.assertEqual(self.count(table), 0, table)

    def test_unexpected_error_rolls_back_and_hides_details(self):
        with mock.patch("scms.repository.insert_notification", side_effect=RuntimeError("secret detail")):
            response = self.alice.post("/complaints", {"category": "A", "description": "x",
                                                       "severity": "Low"})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret detail", response.get_data(as_text=True))
        self.assertIn("request_id", response.json["error"])
        self.assertEqual(self.count("complaints"), 0)
        self.assertEqual(self.count("audit_logs"), 0)


class HandlerActionTests(Base):
    def test_resolve_requires_remarks_and_records_audit(self):
        c = self.submit()
        fac = self.staff("FAC001")
        path = f"/complaints/{c['complaint_id']}/resolve"
        blank = fac.post(path, {"remarks": "  ", "expected_version": 1})
        self.assertEqual(blank.status_code, 422)
        done = fac.post(path, {"remarks": "Replaced", "expected_version": 1})
        self.assertEqual(done.status_code, 200)
        self.assertEqual(done.json["data"]["status"], "Resolved")
        self.assertEqual(done.json["data"]["version"], 2)
        self.assertEqual(self.count("audit_logs"), 2)

    def test_reject_records_reason_and_level(self):
        c = self.submit()
        fac = self.staff("FAC001")
        missing = fac.post(f"/complaints/{c['complaint_id']}/reject", {"expected_version": 1})
        self.assertEqual(missing.status_code, 422)
        ok = fac.post(f"/complaints/{c['complaint_id']}/reject",
                      {"reason": "Out of scope", "expected_version": 1})
        self.assertEqual(ok.json["data"]["status"], "Rejected")
        conn = self.raw()
        self.assertEqual(conn.execute("SELECT rejected_level FROM complaints").fetchone()[0], 1)
        conn.close()

    def test_only_currently_assigned_level_may_act(self):
        c = self.submit(severity="Low")
        # Committee never held this complaint: invisible, not merely forbidden.
        gc = self.staff("GC001")
        self.assertEqual(gc.post(f"/complaints/{c['complaint_id']}/resolve",
                                 {"remarks": "x", "expected_version": 1}).status_code, 404)
        # Faculty escalates; Faculty keeps read access but loses mutation rights (REQ-4.4).
        fac = self.staff("FAC001")
        self.assertEqual(fac.post(f"/complaints/{c['complaint_id']}/escalate",
                                  {"expected_version": 1}).status_code, 200)
        again = fac.post(f"/complaints/{c['complaint_id']}/resolve",
                         {"remarks": "x", "expected_version": 2})
        self.assertEqual(again.status_code, 403)
        self.assertEqual(fac.get(f"/complaints/{c['complaint_id']}").status_code, 200)
        self.assertEqual(self.alice.post(f"/complaints/{c['complaint_id']}/resolve",
                                         {"remarks": "x", "expected_version": 2}).status_code, 403)

    def test_escalation_chain_and_dean_ceiling(self):
        c = self.submit(severity="Low")
        cid = c["complaint_id"]
        r1 = self.staff("FAC001").post(f"/complaints/{cid}/escalate", {"expected_version": 1})
        self.assertEqual((r1.json["data"]["current_level"], r1.json["data"]["status"]), (2, "Escalated"))
        r2 = self.staff("GC001").post(f"/complaints/{cid}/escalate", {"expected_version": 2})
        self.assertEqual(r2.json["data"]["assigned_role"], "Dean")
        r3 = self.staff("DEAN01").post(f"/complaints/{cid}/escalate", {"expected_version": 3})
        self.assertEqual(r3.status_code, 409)
        self.assertEqual(r3.json["error"]["code"], "ESCALATION_LIMIT")
        self.assertEqual(self.count("notifications"), 3)  # submit + two escalations

    def test_stale_version_is_rejected_without_changes(self):
        c = self.submit()
        response = self.staff("FAC001").post(f"/complaints/{c['complaint_id']}/resolve",
                                             {"remarks": "ok", "expected_version": 5})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["error"]["code"], "STALE_VERSION")
        detail = self.alice.get(f"/complaints/{c['complaint_id']}").json["data"]
        self.assertEqual((detail["status"], detail["version"]), ("Submitted", 1))
        self.assertEqual(self.count("audit_logs"), 1)

    def test_terminal_complaints_cannot_be_actioned(self):
        c = self.submit()
        fac = self.staff("FAC001")
        fac.post(f"/complaints/{c['complaint_id']}/resolve", {"remarks": "ok", "expected_version": 1})
        again = fac.post(f"/complaints/{c['complaint_id']}/escalate", {"expected_version": 2})
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json["error"]["code"], "INVALID_STATE")


class AppealTests(Base):
    def reject_at_l1(self):
        c = self.submit()
        self.staff("FAC001").post(f"/complaints/{c['complaint_id']}/reject",
                                  {"reason": "No", "expected_version": 1})
        return c["complaint_id"]

    def test_single_appeal_moves_up_one_level(self):
        cid = self.reject_at_l1()
        response = self.alice.post(f"/complaints/{cid}/appeals",
                                   {"justification": "Please reconsider", "expected_version": 2})
        self.assertEqual(response.status_code, 201, response.json)
        data = response.json["data"]
        self.assertEqual((data["status"], data["current_level"], data["final_review"]),
                         ("Under Appeal Review", 2, False))
        self.assertEqual(data["version"], 3)

    def test_second_appeal_is_blocked(self):
        cid = self.reject_at_l1()
        self.alice.post(f"/complaints/{cid}/appeals", {"justification": "Once", "expected_version": 2})
        # Committee rejects the appeal; the student still cannot appeal again.
        self.staff("GC001").post(f"/complaints/{cid}/reject", {"reason": "No again", "expected_version": 3})
        second = self.alice.post(f"/complaints/{cid}/appeals", {"justification": "Twice", "expected_version": 4})
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json["error"]["code"], "APPEAL_ALREADY_USED")
        self.assertEqual(self.count("appeals"), 1)

    def test_database_enforces_one_appeal_even_if_service_check_is_bypassed(self):
        cid = self.reject_at_l1()
        self.alice.post(f"/complaints/{cid}/appeals", {"justification": "Once", "expected_version": 2})
        conn = self.raw()
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO appeals (complaint_id, actor_id, justification, submitted_at,"
                         " rejected_level, target_level) VALUES (?, 1, 'dup', 'now', 1, 2)", (cid,))
        conn.close()

    def test_dean_rejection_appeal_stays_at_dean_for_final_review(self):
        c = self.submit(severity="High")
        cid = c["complaint_id"]
        self.staff("GC001").post(f"/complaints/{cid}/escalate", {"expected_version": 1})
        self.staff("DEAN01").post(f"/complaints/{cid}/reject", {"reason": "No", "expected_version": 2})
        response = self.alice.post(f"/complaints/{cid}/appeals",
                                   {"justification": "Final", "expected_version": 3})
        data = response.json["data"]
        self.assertEqual((data["current_level"], data["final_review"]), (3, True))

    def test_appeal_preconditions(self):
        c = self.submit()
        cid = c["complaint_id"]
        not_rejected = self.alice.post(f"/complaints/{cid}/appeals",
                                       {"justification": "x", "expected_version": 1})
        self.assertEqual(not_rejected.json["error"]["code"], "NOT_REJECTED")
        rejected_cid = self.reject_at_l1()
        # Another student cannot appeal (or even see) it.
        other = self.bob.post(f"/complaints/{rejected_cid}/appeals",
                              {"justification": "x", "expected_version": 2})
        self.assertEqual(other.status_code, 404)
        blank = self.alice.post(f"/complaints/{rejected_cid}/appeals",
                                {"justification": " ", "expected_version": 2})
        self.assertEqual(blank.status_code, 422)


class AuditTests(Base):
    def test_history_is_complete_ordered_and_scoped(self):
        c = self.submit(severity="Low")
        cid = c["complaint_id"]
        self.staff("FAC001").post(f"/complaints/{cid}/escalate", {"expected_version": 1})
        self.staff("GC001").post(f"/complaints/{cid}/resolve", {"remarks": "Done", "expected_version": 2})

        history = self.alice.get(f"/complaints/{cid}/audit").json["data"]
        self.assertEqual([h["action"] for h in history], ["SUBMIT", "ESCALATE", "RESOLVE"])
        self.assertEqual(history[1]["previous_level"], 1)
        self.assertEqual(history[1]["new_level"], 2)
        ids = [h["audit_id"] for h in history]
        self.assertEqual(ids, sorted(ids))
        # Previous handler level may read; a student who does not own it gets 404.
        self.assertEqual(self.staff("FAC001").get(f"/complaints/{cid}/audit").status_code, 200)
        self.assertEqual(self.bob.get(f"/complaints/{cid}/audit").status_code, 404)

    def test_audit_has_no_write_routes(self):
        c = self.submit()
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            response = self.alice.request(method, f"/complaints/{c['complaint_id']}/audit", {})
            self.assertEqual(response.status_code, 405, method)

    def test_audit_rows_are_immutable_in_the_database(self):
        self.submit()
        conn = self.raw()
        with self.assertRaises(sqlite3.DatabaseError):
            conn.execute("UPDATE audit_logs SET action = 'TAMPERED'")
        with self.assertRaises(sqlite3.DatabaseError):
            conn.execute("DELETE FROM audit_logs")
        conn.close()
        self.assertEqual(self.count("audit_logs"), 1)

    def test_every_accepted_action_adds_exactly_one_audit_entry(self):
        c = self.submit()
        before = self.count("audit_logs")
        self.staff("FAC001").post(f"/complaints/{c['complaint_id']}/resolve",
                                  {"remarks": "ok", "expected_version": 1})
        self.assertEqual(self.count("audit_logs"), before + 1)
        # A denied action writes nothing.
        self.staff("GC001").post(f"/complaints/{c['complaint_id']}/resolve",
                                 {"remarks": "ok", "expected_version": 2})
        self.assertEqual(self.count("audit_logs"), before + 1)


class DashboardTests(Base):
    def test_role_scoped_dashboards(self):
        a_low = self.submit(self.alice, "Low")
        b_high = self.submit(self.bob, "High")
        a_dean = self.submit(self.alice, "High")
        self.staff("GC001").post(f"/complaints/{a_dean['complaint_id']}/escalate", {"expected_version": 1})

        ids = lambda r: {c["complaint_id"] for c in r.json["data"]}
        self.assertEqual(ids(self.alice.get("/complaints")), {a_low["complaint_id"], a_dean["complaint_id"]})
        self.assertEqual(ids(self.bob.get("/complaints")), {b_high["complaint_id"]})
        self.assertEqual(ids(self.staff("FAC001").get("/complaints")), {a_low["complaint_id"]})
        self.assertEqual(ids(self.staff("GC001").get("/complaints")), {b_high["complaint_id"]})
        self.assertEqual(ids(self.staff("DEAN01").get("/complaints")), {a_dean["complaint_id"]})

    def test_pagination_and_filter_validation(self):
        for _ in range(3):
            self.submit()
        page = self.alice.get("/complaints?page=2&page_size=2").json
        self.assertEqual((page["page"], page["page_size"], page["total"], len(page["data"])), (2, 2, 3, 1))
        self.assertEqual(self.alice.get("/complaints?page_size=101").status_code, 422)
        self.assertEqual(self.alice.get("/complaints?status=Bogus").status_code, 422)
        self.assertEqual(self.alice.get("/complaints?status=Resolved").json["total"], 0)

    def test_invisible_complaint_looks_like_missing(self):
        c = self.submit()
        hidden = self.bob.get(f"/complaints/{c['complaint_id']}")
        missing = self.bob.get("/complaints/99999")
        self.assertEqual(hidden.status_code, 404)
        self.assertEqual(hidden.json["error"]["message"], missing.json["error"]["message"])


class FeedbackTests(Base):
    def resolved(self):
        c = self.submit()
        self.staff("FAC001").post(f"/complaints/{c['complaint_id']}/resolve",
                                  {"remarks": "Fixed", "expected_version": 1})
        return c["complaint_id"]

    def test_only_resolved_complaints_accept_feedback(self):
        c = self.submit()
        response = self.alice.post(f"/complaints/{c['complaint_id']}/feedback", {"rating": 4})
        self.assertEqual(response.status_code, 409)

    def test_rating_validation_and_single_feedback(self):
        cid = self.resolved()
        for bad in (0, 6, "5", True, 4.5, None):
            r = self.alice.post(f"/complaints/{cid}/feedback", {"rating": bad})
            self.assertEqual(r.status_code, 422, bad)
        self.assertEqual(self.alice.post(f"/complaints/{cid}/feedback", {"rating": 5}).status_code, 201)
        again = self.alice.post(f"/complaints/{cid}/feedback", {"rating": 3})
        self.assertEqual(again.json["error"]["code"], "FEEDBACK_ALREADY_EXISTS")
        self.assertEqual(self.count("feedback"), 1)

    def test_handler_view_hides_student_identity(self):
        cid = self.resolved()
        self.alice.post(f"/complaints/{cid}/feedback", {"rating": 5, "comment": "Great"})
        view = self.staff("FAC001").get(f"/complaints/{cid}/feedback")
        self.assertEqual(view.status_code, 200)
        self.assertEqual(set(view.json["data"]), {"rating", "comment", "submitted_at"})
        text = view.get_data(as_text=True)
        for leaked in ("Alice", "STU001", "stu001@univ.edu", "student_id"):
            self.assertNotIn(leaked, text)
        conn = self.raw()
        columns = [r[1] for r in conn.execute("PRAGMA table_info(feedback)")]
        conn.close()
        self.assertNotIn("student_id", columns)

    def test_other_student_cannot_submit_or_read(self):
        cid = self.resolved()
        self.assertEqual(self.bob.post(f"/complaints/{cid}/feedback", {"rating": 5}).status_code, 404)
        self.assertEqual(self.bob.get(f"/complaints/{cid}/feedback").status_code, 404)


class SlaTests(Base):
    def test_check_lists_overdue_without_changing_state(self):
        c = self.submit()
        cid = c["complaint_id"]
        dean = self.staff("DEAN01")
        self.assertEqual(dean.post("/sla/check", {}).json["data"]["items"], [])
        self.backdate(cid, 10)
        result = dean.post("/sla/check", {}).json["data"]
        self.assertEqual(result["threshold_days"], 7)
        self.assertEqual(len(result["items"]), 1)
        item = result["items"][0]
        self.assertEqual((item["complaint_id"], item["days_overdue"], item["can_escalate"]), (cid, 3, True))
        detail = self.alice.get(f"/complaints/{cid}").json["data"]
        self.assertEqual((detail["status"], detail["version"]), ("Submitted", 1))

    def test_requires_explicit_permission(self):
        self.assertEqual(self.staff("FAC001").post("/sla/check", {}).status_code, 403)
        self.assertEqual(self.staff("DEAN02").post("/sla/check", {}).status_code, 403)
        self.assertEqual(self.alice.post("/sla/check", {}).status_code, 403)

    def test_terminal_complaints_are_not_listed(self):
        c = self.submit()
        self.staff("FAC001").post(f"/complaints/{c['complaint_id']}/resolve",
                                  {"remarks": "ok", "expected_version": 1})
        self.backdate(c["complaint_id"], 30)
        self.assertEqual(self.staff("DEAN01").post("/sla/check", {}).json["data"]["items"], [])

    def test_sla_escalation_is_scoped_audited_and_capped(self):
        c = self.submit()
        cid = c["complaint_id"]
        dean = self.staff("DEAN01")
        not_overdue = dean.post(f"/sla/complaints/{cid}/escalate", {"expected_version": 1})
        self.assertEqual(not_overdue.status_code, 409)

        self.backdate(cid, 8)
        first = dean.post(f"/sla/complaints/{cid}/escalate", {"expected_version": 1})
        self.assertEqual(first.json["data"]["current_level"], 2)
        # The exception grants escalation only, not ordinary handler authority.
        resolve = dean.post(f"/complaints/{cid}/resolve", {"remarks": "x", "expected_version": 2})
        self.assertIn(resolve.status_code, (403, 404))

        self.backdate(cid, 8)
        self.assertEqual(dean.post(f"/sla/complaints/{cid}/escalate",
                                   {"expected_version": 2}).json["data"]["current_level"], 3)
        self.backdate(cid, 8)
        capped = dean.post(f"/sla/complaints/{cid}/escalate", {"expected_version": 3})
        self.assertEqual(capped.json["error"]["code"], "ESCALATION_LIMIT")

        actions = [h["action"] for h in self.alice.get(f"/complaints/{cid}/audit").json["data"]]
        self.assertEqual(actions, ["SUBMIT", "SLA_ESCALATE", "SLA_ESCALATE"])

    def test_sla_escalation_denied_without_permission(self):
        c = self.submit()
        self.backdate(c["complaint_id"], 8)
        response = self.staff("DEAN02").post(f"/sla/complaints/{c['complaint_id']}/escalate",
                                             {"expected_version": 1})
        self.assertEqual(response.status_code, 403)


class ApiConventionTests(Base):
    def test_error_shape_headers_and_content_checks(self):
        no_store = self.alice.get("/complaints")
        self.assertEqual(no_store.headers["Cache-Control"], "no-store")

        malformed = self.alice.http.post(f"{API}/complaints", data="{not json",
                                         headers={"X-CSRF-Token": self.alice.csrf,
                                                  "Content-Type": "application/json"})
        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(malformed.json["error"]["code"], "MALFORMED_JSON")

        wrong_type = self.alice.http.post(f"{API}/complaints", data="a=b",
                                          headers={"X-CSRF-Token": self.alice.csrf})
        self.assertEqual(wrong_type.status_code, 415)

        unknown = self.alice.get("/does-not-exist")
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(unknown.json["error"]["code"], "NOT_FOUND")
        self.assertIn("request_id", unknown.json["error"])

    def test_readiness_check_exposes_no_records(self):
        self.submit()
        response = self.app.test_client().get("/healthz")
        self.assertEqual(response.json, {"status": "ok"})

    def test_secret_key_is_required(self):
        with self.assertRaises(RuntimeError):
            create_app({"DATABASE": os.path.join(self.tmp, "other.db"), "SECRET_KEY": None})


if __name__ == "__main__":
    unittest.main()
