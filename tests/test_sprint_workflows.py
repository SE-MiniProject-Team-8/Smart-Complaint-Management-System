"""Regression scenarios for issues #7, #8 and #9 against Flask and SQLite."""
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone

from scms import auth, queries
from tests.test_app import ApiClient, Base


class SessionCapabilityTests(Base):
    def test_login_and_reload_expose_only_effective_sla_permission(self):
        for uid, role, allowed in [("STU001", "Student", False), ("FAC001", "Faculty", False),
                                   ("GC001", "Committee", False), ("DEAN01", "Dean", True),
                                   ("DEAN02", "Dean", False)]:
            client = ApiClient(self.app)
            logged_in = client.login(uid).json["data"]
            restored = client.get("/session").json["data"]
            for data in (logged_in, restored):
                self.assertEqual(data["university_id"], uid)
                self.assertEqual(data["role"], role)
                self.assertEqual(data["can_review_sla"], allowed)
                self.assertNotIn("password_hash", data)

    def test_logout_bootstrap_allows_a_different_account_to_sign_in(self):
        dean = self.staff("DEAN01")
        self.assertEqual(dean.delete("/session").status_code, 204)
        self.assertFalse(dean.get("/session").json["data"]["can_review_sla"])
        dean.start()
        self.assertEqual(dean.login("STU001").status_code, 200)
        self.assertEqual(dean.post("/sla/check").status_code, 403)

    def test_permission_revocation_takes_effect_during_existing_session(self):
        dean = self.staff("DEAN01")
        with closing(self.raw()) as conn:
            conn.execute("UPDATE users SET sla_review = 0 WHERE university_id = 'DEAN01'")
        self.assertFalse(dean.get("/session").json["data"]["can_review_sla"])
        self.assertEqual(dean.post("/sla/check").status_code, 403)

    def test_non_dean_cannot_use_sla_even_if_provisioned_with_flag(self):
        with closing(self.raw()) as conn:
            conn.execute("UPDATE users SET sla_review = 1 WHERE university_id = 'FAC001'")
        faculty = self.staff("FAC001")
        self.assertFalse(faculty.get("/session").json["data"]["can_review_sla"])
        c = self.submit()
        self.backdate(c["complaint_id"], 9)
        self.assertEqual(faculty.post("/sla/check").status_code, 403)
        self.assertEqual(faculty.post(f"/sla/complaints/{c['complaint_id']}/escalate",
                                     {"expected_version": 1}).status_code, 403)


class DashboardWorkflowTests(Base):
    def test_three_pages_are_complete_scoped_and_filterable(self):
        own = {self.submit()["complaint_id"] for _ in range(25)}
        others = {self.submit(self.bob, severity="High")["complaint_id"] for _ in range(3)}
        faculty = self.staff("FAC001")
        for client in (self.alice, faculty):
            seen = []
            for page in range(1, 4):
                result = client.get(f"/complaints?page={page}&page_size=10").json
                self.assertEqual(result["total"], 25)
                seen.extend(c["complaint_id"] for c in result["data"])
            self.assertEqual(len(seen), len(set(seen)))
            self.assertEqual(set(seen), own)
            self.assertTrue(set(seen).isdisjoint(others))
        target = min(own)
        faculty.post(f"/complaints/{target}/reject", {"reason": "More evidence needed", "expected_version": 1})
        for client in (self.alice, faculty):
            result = client.get("/complaints?status=Rejected&page_size=10").json
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["data"][0]["complaint_id"], target)

    def test_dashboard_queries_with_250_records_stay_under_two_seconds(self):
        # Local sequential requests; this is not a concurrent production load test.
        committee = self.staff("GC001")
        for index in range(250):
            c = self.submit(severity="Low" if index < 100 else "High")
            if index >= 200:
                committee.post(f"/complaints/{c['complaint_id']}/escalate", {"expected_version": 1})
        for client in (self.alice, self.staff("FAC001"), self.staff("GC001"), self.staff("DEAN01")):
            for _ in range(5):
                started = time.perf_counter()
                response = client.get("/complaints?page=1&page_size=10")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.json["data"]), 10)
                self.assertLess(time.perf_counter() - started, 2.0)


class AppealWorkflowTests(Base):
    def test_rejected_complaint_moves_between_role_queues_and_cannot_be_appealed_twice(self):
        c = self.submit()
        cid = c["complaint_id"]
        faculty, committee = self.staff("FAC001"), self.staff("GC001")
        faculty.post(f"/complaints/{cid}/reject", {"reason": "Need evidence", "expected_version": 1})
        self.assertIn("appeal", self.alice.get(f"/complaints/{cid}").json["data"]["allowed_actions"])
        self.assertNotIn("appeal", faculty.get(f"/complaints/{cid}").json["data"]["allowed_actions"])
        response = self.alice.post(f"/complaints/{cid}/appeals", {"justification": "Evidence provided", "expected_version": 2})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["data"]["current_level"], 2)
        self.assertEqual(faculty.get("/complaints").json["total"], 0)
        self.assertEqual(committee.get("/complaints?status=Under%20Appeal%20Review").json["total"], 1)
        committee.post(f"/complaints/{cid}/reject", {"reason": "Evidence insufficient", "expected_version": 3})
        detail = self.alice.get(f"/complaints/{cid}").json["data"]
        self.assertNotIn("appeal", detail["allowed_actions"])
        self.assertEqual(self.alice.post(f"/complaints/{cid}/appeals", {
            "justification": "Again", "expected_version": 4}).status_code, 409)
        self.assertEqual(self.count("appeals"), 1)

    def test_stale_appeal_leaves_no_duplicate_or_partial_writes(self):
        c = self.submit()
        cid = c["complaint_id"]
        self.staff("FAC001").post(f"/complaints/{cid}/reject", {"reason": "Missing evidence", "expected_version": 1})
        before = {table: self.count(table) for table in ("appeals", "audit_logs", "assignment_history", "notifications")}
        response = self.alice.post(f"/complaints/{cid}/appeals", {"justification": "New evidence", "expected_version": 1})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["error"]["code"], "STALE_VERSION")
        self.assertEqual(before, {table: self.count(table) for table in before})
        self.assertIn("appeal", self.alice.get(f"/complaints/{cid}").json["data"]["allowed_actions"])

    def test_dean_final_review_exposes_no_escalation_or_second_appeal(self):
        c = self.submit(severity="High")
        cid = c["complaint_id"]
        self.staff("GC001").post(f"/complaints/{cid}/escalate", {"expected_version": 1})
        dean = self.staff("DEAN01")
        dean.post(f"/complaints/{cid}/reject", {"reason": "Final decision", "expected_version": 2})
        response = self.alice.post(f"/complaints/{cid}/appeals", {"justification": "Please reconsider", "expected_version": 3})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json["data"]["final_review"])
        self.assertEqual(response.json["data"]["current_level"], 3)
        self.assertEqual(set(dean.get(f"/complaints/{cid}").json["data"]["allowed_actions"]), {"resolve", "reject"})


class SlaWorkflowTests(Base):
    def test_review_returns_version_for_scoped_escalation_without_detail_access(self):
        c = self.submit()
        cid = c["complaint_id"]
        self.backdate(cid, 9)
        dean = self.staff("DEAN01")
        self.assertEqual(dean.get(f"/complaints/{cid}").status_code, 404)
        item = dean.post("/sla/check").json["data"]["items"][0]
        self.assertEqual(item["version"], 1)
        self.assertNotIn("description", item)
        self.assertNotIn("student_id", item)
        response = dean.post(f"/sla/complaints/{cid}/escalate", {"expected_version": item["version"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["data"]["current_level"], 2)
        self.assertNotIn("description", response.json["data"])
        self.assertNotIn("rejection_reason", response.json["data"])
        self.assertEqual(dean.get(f"/complaints/{cid}").status_code, 404)
        self.assertEqual(dean.post(f"/complaints/{cid}/resolve", {"remarks": "Invalid", "expected_version": 2}).status_code, 404)

    def test_stale_sla_action_cannot_move_complaint_twice(self):
        c = self.submit()
        cid = c["complaint_id"]
        self.backdate(cid, 9)
        dean = self.staff("DEAN01")
        version = dean.post("/sla/check").json["data"]["items"][0]["version"]
        self.staff("FAC001").post(f"/complaints/{cid}/escalate", {"expected_version": 1})
        self.backdate(cid, 9)  # simulate a later overdue period at its new level
        before = self.count("audit_logs")
        response = dean.post(f"/sla/complaints/{cid}/escalate", {"expected_version": version})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["error"]["code"], "STALE_VERSION")
        self.assertEqual(self.count("audit_logs"), before)
        self.assertEqual(self.alice.get(f"/complaints/{cid}").json["data"]["current_level"], 2)

    def test_configured_threshold_and_strict_boundary(self):
        c = self.submit()
        now = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)
        actor = auth.Actor(1, "DEAN01", "Dean", True)
        with closing(self.raw()) as conn:
            conn.execute("UPDATE settings SET value = '3' WHERE key = 'sla_threshold_days'")
            conn.execute("UPDATE complaints SET status_updated_at = ? WHERE complaint_id = ?",
                         ((now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"), c["complaint_id"]))
            self.assertEqual(queries.sla_check(conn, actor, now)["items"], [])
            result = queries.sla_check(conn, actor, now + timedelta(seconds=1))
            self.assertEqual(result["threshold_days"], 3)
            self.assertEqual(len(result["items"]), 1)
            self.assertEqual(result["items"][0]["days_overdue"], 0)

    def test_sla_check_requires_csrf_and_does_not_mutate(self):
        c = self.submit()
        self.backdate(c["complaint_id"], 9)
        dean = self.staff("DEAN01")
        self.assertEqual(dean.post("/sla/check", csrf=False).status_code, 403)
        before = self.count("audit_logs")
        self.assertEqual(dean.post("/sla/check").status_code, 200)
        self.assertEqual(self.count("audit_logs"), before)
