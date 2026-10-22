# Smart Complaint Management System (SCMS)

Layered modular monolith: Python 3 + Flask + SQLite (see `Member3-Architecture/` and `Member 4/`).
Complaint records are stored in a SQLite file, so they survive application restarts.

## Modules (`scms/`)

| Module | Component | Responsibility |
|---|---|---|
| `api.py` | C02 | Routes under `/api/v1`, session/CSRF guard, JSON errors, request logging |
| `auth.py` | C03 | Registration, password hashing, sessions, ownership/role/assignment policy |
| `complaints.py` | C04 | Submit, resolve, reject, escalate, appeal; owns the transaction boundary |
| `routing.py` | C05 | Pure routing rules (initial level, next level, appeal target, Dean ceiling) |
| `audit.py` | C06 | Append-only audit history |
| `feedback.py` | C07 | Feedback for resolved complaints, identity-suppressed handler view |
| `queries.py` | C08 | Role-scoped dashboards, manual SLA review, notifications |
| `repository.py`, `db.py`, `schema.sql` | C09 | All SQL, connections, transactions, constraints, audit triggers |

Every complaint change writes the complaint, assignment history, audit entry and
notification in **one transaction**; a failure rolls all of it back and no success
is reported before the commit.

## Setup

```bash
pip install -r requirements.txt
export SCMS_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export SCMS_INSECURE_COOKIES=1            # plain-HTTP local development only
# optional: export SCMS_DATABASE=/path/to/scms.db   (default: instance/scms.db)

flask --app scms init-db
flask --app scms create-staff --university-id FAC001 --name "Prof. Bob" \
      --email bob@univ.edu --role Faculty          # Faculty | Committee | Dean
flask --app scms create-staff --university-id DEAN01 --name "Dean Davis" \
      --email dean@univ.edu --role Dean --sla-review
python run.py
```

Students self-register through `POST /api/v1/users`; staff accounts are provisioned
only with the command above. For shared deployment use a WSGI server behind HTTPS,
keep the database file outside the web root, and back it up with SQLite's `.backup`.

## Tests

```bash
SCMS_SECRET_KEY=test python -m unittest discover -s tests -v   # real app + SQLite
python -m unittest test_scms -v                                # original in-memory simulation
```

`test_scms.py` is the earlier in-memory simulation and cannot show durability; the tests
in `tests/` run against the real application, including a restart-persistence test.

## Not implemented yet

No browser UI (templates), login throttling, or configurable-threshold admin screen.
Performance targets (2 s dashboard, 3 s submission) have not been measured.
