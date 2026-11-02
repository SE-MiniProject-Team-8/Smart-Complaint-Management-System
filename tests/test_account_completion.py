"""Issue #1 regressions for the existing authentication service."""
import sqlite3
from unittest import mock

from scms import auth
from tests.test_app import ApiClient, Base, PASSWORD


class AccountCompletionTests(Base):
    def test_login_validates_missing_fields_without_revealing_accounts(self):
        client = ApiClient(self.app)
        for payload, fields in [({}, {"university_id", "password"}),
                                ({"university_id": [], "password": 1},
                                 {"university_id", "password"}),
                                ({"university_id": "STU001", "password": PASSWORD,
                                  "role": "Dean"}, {"role"})]:
            with self.subTest(payload=payload):
                response = client.post("/session", payload)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(set(response.json["error"]["fields"]), fields)
                self.assertFalse(client.get("/session").json["data"]["authenticated"])

    def test_session_rotation_failure_preserves_old_session_and_allows_retry(self):
        client = ApiClient(self.app)
        old_token = client.csrf
        before = self.count("sessions")
        with mock.patch.object(auth.repo, "insert_session", side_effect=sqlite3.OperationalError):
            response = client.login("STU001")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.count("sessions"), before)
        session = client.get("/session").json["data"]
        self.assertFalse(session["authenticated"])
        self.assertEqual(session["csrf_token"], old_token)
        self.assertEqual(client.login("STU001").status_code, 200)
        self.assertNotEqual(client.csrf, old_token)
