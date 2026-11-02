"""Run real browser workflows on a disposable SQLite database and local server.

Requires Node.js and Playwright; see docs/product-verification.md.
No existing application database is read or modified.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scms import auth, create_app, db
from werkzeug.serving import make_server


def main():
    with tempfile.TemporaryDirectory(prefix="scms-browser-") as folder:
        database = str(Path(folder) / "test.db")
        app = create_app({
            "DATABASE": database,
            "SECRET_KEY": "isolated-browser-test-only",
            "SESSION_COOKIE_SECURE": False,
            "PASSWORD_HASH_METHOD": "pbkdf2:sha256:1000",
        })
        conn = db.connect(database)
        try:
            for uid, role, sla in [("FAC001", "Faculty", False),
                                   ("GC001", "Committee", False),
                                   ("DEAN01", "Dean", True)]:
                auth.create_staff(conn, uid, uid, f"{uid}@example.edu",
                                  "Test-Only-123", role, sla,
                                  "pbkdf2:sha256:1000")
        finally:
            conn.close()
        server = make_server("127.0.0.1", 0, app, threaded=True)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            result = subprocess.run(
                ["node", str(ROOT / "tests/product_browser.cjs")],
                cwd=ROOT,
                env={**os.environ,
                     "SCMS_E2E_URL": f"http://127.0.0.1:{server.server_port}/",
                     "SCMS_E2E_DB": database},
                timeout=180,
            )
            return result.returncode
        finally:
            server.shutdown()
            worker.join(timeout=5)
            server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
