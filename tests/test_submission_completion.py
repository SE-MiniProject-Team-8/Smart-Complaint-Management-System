"""Issue #2 acceptance checks against the persistent application, not a mock store."""
from datetime import datetime, timezone

from tests.test_app import Base, make_app, ApiClient


class SubmissionCompletionTests(Base):
    def test_documented_limits_location_timestamps_and_restart(self):
        before = datetime.now(timezone.utc).replace(microsecond=0)
        response = self.alice.post("/complaints", {
            "category": "  " + "C" * 50 + "  ",
            "description": "  " + "D" * 1000 + "  ", "severity": "Medium"})
        self.assertEqual(response.status_code, 201)
        created = response.json["data"]
        self.assertEqual(response.headers["Location"],
                         f"/api/v1/complaints/{created['complaint_id']}")
        self.assertGreater(created["complaint_id"], 0)
        submitted = datetime.strptime(created["submitted_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        self.assertGreaterEqual(submitted, before)
        self.assertLessEqual(submitted, datetime.now(timezone.utc))
        restarted = ApiClient(make_app(self.db_path))
        self.assertEqual(restarted.login("STU001").status_code, 200)
        detail = restarted.get(f"/complaints/{created['complaint_id']}").json["data"]
        self.assertEqual(detail["category"], "C" * 50)
        self.assertEqual(detail["description"], "D" * 1000)
        self.assertEqual(detail["status"], "Submitted")
        self.assertEqual(detail["submitted_at"], created["submitted_at"])
        self.assertEqual(detail["current_level"], 1)
        self.assertNotEqual(self.submit(restarted)["complaint_id"], created["complaint_id"])

    def test_invalid_fields_and_injected_server_fields_leave_no_partial_records(self):
        valid = {"category": "Facilities", "description": "Broken fan", "severity": "Low"}
        cases = [("category", value) for value in [None, "", "   ", [], {}, "C" * 51]]
        cases += [("description", value) for value in [None, "", "   ", 7, "D" * 1001]]
        cases += [("severity", value) for value in [None, "", "low", "Urgent", [], {}, True]]
        cases += [(field, 1) for field in ["student_id", "complaint_id", "current_level", "status"]]
        tables = ("complaints", "assignment_history", "audit_logs", "notifications")
        before = {table: self.count(table) for table in tables}
        for field, value in cases:
            with self.subTest(field=field, value=value):
                response = self.alice.post("/complaints", {**valid, field: value})
                self.assertEqual(response.status_code, 422)
                self.assertIn(field, response.json["error"]["fields"])
                self.assertNotIn("Location", response.headers)
                self.assertEqual({table: self.count(table) for table in tables}, before)
