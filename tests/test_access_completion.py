"""Issue #3 access checks at the HTTP boundary."""
from tests.test_app import ApiClient, Base


class AccessCompletionTests(Base):
    def test_expired_session_denies_every_protected_operation_without_writes(self):
        c = self.submit()
        conn = self.raw()
        conn.execute("UPDATE sessions SET expires_at = '2000-01-01T00:00:00Z'")
        conn.close()
        before = self.count("audit_logs")
        cid = c["complaint_id"]
        endpoints = [("GET", "/complaints"), ("GET", f"/complaints/{cid}"),
                     ("GET", f"/complaints/{cid}/audit"), ("GET", "/notifications"),
                     ("GET", f"/complaints/{cid}/feedback"),
                     ("POST", "/complaints"), ("POST", "/sla/check"),
                     ("POST", f"/sla/complaints/{cid}/escalate"),
                     ("DELETE", "/session")]
        endpoints += [("POST", f"/complaints/{cid}/{action}") for action in
                      ("resolve", "reject", "escalate", "appeals", "feedback")]
        for method, path in endpoints:
            with self.subTest(method=method, path=path):
                response = self.alice.request(method, path, {} if method == "POST" else None)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json["error"]["code"], "AUTHENTICATION_REQUIRED")
                self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(self.count("audit_logs"), before)
        self.assertFalse(self.alice.get("/session").json["data"]["authenticated"])
        self.alice.start()
        self.assertEqual(self.alice.login("STU001").status_code, 200)

    def test_other_owner_and_unassigned_roles_cannot_read_or_mutate(self):
        c = self.submit()
        cid = c["complaint_id"]
        clients = [self.bob, self.staff("GC001"), self.staff("DEAN01")]
        before = self.count("audit_logs")
        for client in clients:
            for suffix in ("", "/audit", "/feedback"):
                with self.subTest(suffix=suffix):
                    response = client.get(f"/complaints/{cid}{suffix}")
                    self.assertEqual(response.status_code, 404)
                    self.assertEqual(response.json["error"]["code"], "NOT_FOUND")
            for action in ("resolve", "reject", "escalate", "appeals", "feedback"):
                response = client.post(f"/complaints/{cid}/{action}", {
                    "expected_version": 1, "remarks": "Done", "reason": "No",
                    "justification": "Review", "rating": 5})
                self.assertEqual(response.status_code, 404)
        self.assertEqual(self.count("audit_logs"), before)

    def test_role_changes_apply_to_an_existing_session(self):
        fac = self.staff("FAC001")
        self.assertEqual(fac.get("/notifications").status_code, 200)
        conn = self.raw()
        conn.execute("UPDATE users SET role = 'Student' WHERE university_id = 'FAC001'")
        conn.close()
        self.assertEqual(fac.get("/session").json["data"]["role"], "Student")
        self.assertEqual(fac.get("/notifications").status_code, 403)
