"""NFR-PERF-01 / NFR-PERF-02 measurement against the real app (production password hash).

Seeds 250 complaints through the API, then times submissions and dashboard
reads in-process with the Flask test client (network latency excluded).
Not part of the unit suite. Run from the repository root:

    python tests/measure_performance.py

Output is recorded in docs/reports/evidence/performance-measurement.json.
"""
import os, sys, statistics, tempfile, time, json
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scms import create_app, auth, db
tmp = tempfile.mkdtemp(); path = os.path.join(tmp, "m.db")
app = create_app({"TESTING": True, "DATABASE": path, "SECRET_KEY": "x", "SESSION_COOKIE_SECURE": False})
conn = db.connect(path)
auth.create_staff(conn, "FAC1", "F", "f@e.edu", "Pass@1234", "Faculty")
conn.close()
def client():
    c = app.test_client(); tok = c.get("/api/v1/session").json["data"]["csrf_token"]; return c, tok
def login(uid):
    c, tok = client()
    r = c.post("/api/v1/session", json={"university_id": uid, "password": "Pass@1234"}, headers={"X-CSRF-Token": tok})
    return c, r.json["data"]["csrf_token"]
c, tok = client()
c.post("/api/v1/users", json={"university_id": "S1", "name": "S", "email": "s@e.edu", "password": "Pass@1234"}, headers={"X-CSRF-Token": tok})
s, stok = login("S1")
sub = []
for i in range(250):
    t = time.perf_counter()
    r = s.post("/api/v1/complaints", json={"category": "Facilities", "description": f"Issue {i}", "severity": ["Low","Medium"][i % 2]}, headers={"X-CSRF-Token": stok})
    sub.append(time.perf_counter() - t); assert r.status_code == 201, r.json
f, ftok = login("FAC1")
dash = []
for _ in range(30):
    t = time.perf_counter(); r = f.get("/api/v1/complaints?page=1&page_size=20"); dash.append(time.perf_counter() - t); assert r.status_code == 200
sdash = []
for _ in range(30):
    t = time.perf_counter(); r = s.get("/api/v1/complaints?page=13&page_size=20"); sdash.append(time.perf_counter() - t)
def st(x): x = sorted(x); return {"n": len(x), "median_ms": round(statistics.median(x)*1000, 2), "p95_ms": round(x[int(len(x)*0.95)-1]*1000, 2), "max_ms": round(x[-1]*1000, 2)}
print(json.dumps({"records": 250, "submission": st(sub), "faculty_dashboard": st(dash), "student_dashboard_last_page": st(sdash)}, indent=1))
