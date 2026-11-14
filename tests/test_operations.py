"""Operator commands and the shared transaction boundary.

These cover paths the HTTP tests cannot reach: the trusted staff
provisioning CLI (no public route exists for staff accounts) and the
failure branches of db.transaction that guarantee NFR-REL-02 (never report
success unless the write committed).

Run from the repository root:  python -m unittest discover -s tests -v
"""
import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

from scms import auth, create_app, db, queries, validation
from scms import repository as repo
from scms.errors import AppError

HASH = "pbkdf2:sha256:1000"


class StaffProvisioningCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "cli.db")
        self.app = create_app({"TESTING": True, "DATABASE": self.path,
                               "SECRET_KEY": "test-secret", "PASSWORD_HASH_METHOD": HASH})
        self.runner = self.app.test_cli_runner()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def staff(self, *extra, university_id="FAC100", email="fac100@example.edu", role="Faculty"):
        return self.runner.invoke(args=[
            "create-staff", "--university-id", university_id, "--name", "Faculty Test",
            "--email", email, "--role", role, "--password", "Pass@1234", *extra])

    def test_init_db_is_idempotent_and_reports_location(self):
        for _ in range(2):
            result = self.runner.invoke(args=["init-db"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Database ready at", result.output)
            self.assertIn(self.path, result.output)

    def test_create_staff_stores_hashed_password_and_role(self):
        result = self.staff()
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Created Faculty account FAC100.", result.output)
        conn = db.connect(self.path)
        try:
            row = conn.execute("SELECT role, sla_review, password_hash FROM users "
                               "WHERE university_id = 'FAC100'").fetchone()
        finally:
            conn.close()
        self.assertEqual(row["role"], "Faculty")
        self.assertEqual(row["sla_review"], 0)
        self.assertNotIn("Pass@1234", row["password_hash"])  # SEC-01
        self.assertTrue(row["password_hash"].startswith("pbkdf2:sha256"))

    def test_dean_can_be_granted_sla_review(self):
        result = self.staff("--sla-review", university_id="DEAN100",
                            email="dean100@example.edu", role="Dean")
        self.assertEqual(result.exit_code, 0, result.output)
        conn = db.connect(self.path)
        try:
            flag = conn.execute("SELECT sla_review FROM users WHERE university_id = 'DEAN100'"
                                ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(flag, 1)

    def test_duplicate_staff_fails_cleanly_without_traceback(self):
        self.assertEqual(self.staff().exit_code, 0)
        result = self.staff()
        self.assertEqual(result.exit_code, 1)
        self.assertIn("already exists", result.output)
        self.assertNotIn("Traceback", result.output)

    def test_student_role_cannot_be_provisioned_through_cli(self):
        result = self.staff(role="Student")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid value for '--role'", result.output)


class _CommitFails:
    """Wraps a real connection but makes COMMIT (and optionally ROLLBACK) fail."""

    def __init__(self, conn, rollback_fails=False):
        self.conn = conn
        self.rollback_fails = rollback_fails
        self.statements = []

    def execute(self, sql, *args):
        self.statements.append(sql)
        if sql == "COMMIT":
            raise sqlite3.OperationalError("disk I/O error")
        if sql == "ROLLBACK" and self.rollback_fails:
            raise sqlite3.OperationalError("no transaction is active")
        return self.conn.execute(sql, *args)


class TransactionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "tx.db")
        db.init_db(self.path)
        self.conn = db.connect(self.path)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def settings_count(self):
        return self.conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]

    def insert_setting(self, conn):
        conn.execute("INSERT INTO settings (key, value) VALUES ('probe', '1')")

    def test_successful_block_commits(self):
        before = self.settings_count()
        with db.transaction(self.conn):
            self.insert_setting(self.conn)
        self.assertEqual(self.settings_count(), before + 1)

    def test_begin_failure_is_reported_as_persistence_unavailable(self):
        self.conn.execute("BEGIN")  # a second BEGIN inside an open transaction fails
        try:
            with self.assertRaises(AppError) as caught:
                with db.transaction(self.conn):
                    self.fail("body must not run when BEGIN fails")
        finally:
            self.conn.execute("ROLLBACK")
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(caught.exception.code, "PERSISTENCE_UNAVAILABLE")

    def test_sqlite_error_in_body_rolls_back_and_hides_detail(self):
        before = self.settings_count()
        with self.assertRaises(AppError) as caught:
            with db.transaction(self.conn):
                self.insert_setting(self.conn)
                self.conn.execute("INSERT INTO settings (key, value) VALUES ('probe', '2')")
        self.assertEqual(caught.exception.code, "PERSISTENCE_UNAVAILABLE")
        self.assertNotIn("UNIQUE", caught.exception.message)
        self.assertEqual(self.settings_count(), before)

    def test_unexpected_error_in_body_rolls_back_and_propagates(self):
        before = self.settings_count()
        with self.assertRaises(KeyError):
            with db.transaction(self.conn):
                self.insert_setting(self.conn)
                raise KeyError("boom")
        self.assertEqual(self.settings_count(), before)

    def test_commit_failure_rolls_back_and_never_reports_success(self):
        before = self.settings_count()
        wrapped = _CommitFails(self.conn)
        with self.assertRaises(AppError) as caught:
            with db.transaction(wrapped):
                self.insert_setting(wrapped)
        self.assertEqual(caught.exception.code, "PERSISTENCE_UNAVAILABLE")
        self.assertEqual(wrapped.statements[-1], "ROLLBACK")
        self.assertEqual(self.settings_count(), before)

    def test_commit_failure_still_reported_when_rollback_also_fails(self):
        wrapped = _CommitFails(self.conn, rollback_fails=True)
        with self.assertRaises(AppError) as caught:
            with db.transaction(wrapped):
                self.insert_setting(wrapped)
        self.assertEqual(caught.exception.code, "PERSISTENCE_UNAVAILABLE")
        self.conn.execute("ROLLBACK")  # clean up the real transaction left open

    def test_in_memory_database_skips_file_only_pragmas(self):
        conn = db.connect(":memory:")
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(mode, "memory")
        self.assertEqual(fk, 1)


class BoundaryAndEdgeBranchTests(unittest.TestCase):
    """Edge branches identified by the branch-coverage report (docs/reports)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "edge.db")
        self.app = create_app({"TESTING": True, "DATABASE": self.path,
                               "SECRET_KEY": "test-secret", "SESSION_COOKIE_SECURE": False,
                               "PASSWORD_HASH_METHOD": HASH})
        self.http = self.app.test_client()
        self.conn = db.connect(self.path)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_app_reads_configuration_from_environment_when_no_overrides(self):
        env = {"SCMS_SECRET_KEY": "env-secret", "SCMS_DATABASE": os.path.join(self.tmp, "env.db")}
        with mock.patch.dict(os.environ, env):
            app = create_app()
        self.assertEqual(app.config["SECRET_KEY"], "env-secret")
        self.assertEqual(app.config["DATABASE"], env["SCMS_DATABASE"])
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])  # secure by default

    def test_health_check_reports_ok_and_unavailable(self):
        self.assertEqual(self.http.get("/healthz").json, {"status": "ok"})
        broken = mock.Mock()
        broken.execute.side_effect = sqlite3.OperationalError("database is locked")
        with mock.patch("scms.api.get_db", return_value=broken):
            response = self.http.get("/healthz")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json, {"status": "unavailable"})

    def test_unsafe_request_without_session_is_rejected_before_any_work(self):
        response = self.http.post("/api/v1/users", json={})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json["error"]["code"], "CSRF_FAILED")
        response = self.http.delete("/api/v1/session")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json["error"]["code"], "AUTHENTICATION_REQUIRED")

    def test_registration_rejects_missing_password_and_bad_email(self):
        with self.assertRaises(AppError) as caught:
            auth.register_student(self.conn, {"university_id": "S1", "name": "A",
                                              "email": "not-an-email"}, HASH)
        self.assertEqual(set(caught.exception.fields), {"password", "email"})

    def test_create_staff_rejects_student_role_even_when_called_directly(self):
        with self.assertRaises(AppError) as caught:
            auth.create_staff(self.conn, "X1", "X", "x@example.edu", "Pass@1234", "Student",
                              hash_method=HASH)
        self.assertEqual(caught.exception.status, 422)
        self.assertIn("role", caught.exception.fields)

    def test_invalid_sla_threshold_setting_falls_back_to_seven_days(self):
        for stored in ("abc", "0", "-3"):
            self.conn.execute("UPDATE settings SET value = ? WHERE key = 'sla_threshold_days'",
                              (stored,))
            self.assertEqual(queries._threshold_days(self.conn), 7)

    def test_repository_refuses_unknown_columns_and_handles_empty_audit(self):
        with self.assertRaises(ValueError):
            repo.update_complaint_state(self.conn, 1, 1, db.utc_now(), owner="attacker")
        self.assertEqual(repo.list_audit(self.conn, 999, 1, 10), ([], 0))

    def test_field_validators_reject_wrong_types_and_bad_paging(self):
        errors = {}
        self.assertIsNone(validation.text({"name": 5}, "name", 10, errors))
        self.assertIsNone(validation.integer({}, "rating", errors, required=False))
        self.assertEqual(list(errors), ["name"])
        with self.assertRaises(AppError) as caught:
            validation.paging({"page": "two", "page_size": "500"})
        self.assertEqual(set(caught.exception.fields), {"page", "page_size"})


if __name__ == "__main__":
    unittest.main()
