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

## Issue #11 — Usability and performance

Open `http://127.0.0.1:5000/` after starting the app to use the accessible web portal.
Key improvements delivered in Issue #11:

- **Accessible & Responsive UI**: Responsive design for mobile and desktop screens, skip navigation link, WCAG-compliant color contrasts, and touch-friendly tap targets (>= 44px).
- **Clear Forms & Label Association**: Explicit `<label for="...">` associations, helpful placeholders, visual required indicators (`*`), and `aria-required="true"` attributes.
- **Form Validation & Input Preservation**: Field-specific error highlighting, `aria-invalid` and `aria-describedby` links, autofocus on the first invalid field, and input preservation in `sessionStorage` preventing data loss on failure or reload.
- **Real-Time Guidance**: Live character countdown on complaint description (1,000 character limit) with visual warning thresholds.
- **Complaint Tracking & Management**: "Track My Complaints" tab enabling students to view their submitted issues, live status badges, assigned handlers, resolution remarks, rejection reasons, and options for appeals or feedback submission.
- **Performance Optimizations**:
  - Composite SQLite indexes (`idx_sessions_expires`, `idx_complaints_student_status`, `idx_complaints_level_status_sub`).
  - PRAGMA `temp_store = MEMORY` and `cache_size = -2000` to eliminate disk sorting overhead.
  - Request-scoped actor caching (`g.actor`) avoiding redundant user database queries.
  - SQL-level cutoff filtering for overdue SLA candidate queries.
  - Zero-result early return in pagination queries avoiding unnecessary sorted queries.
  - Verified performance targets: Dashboard query latency < 2.0 seconds and submission confirmation latency < 3.0 seconds under single and repeated operations.

## Sprint 1 — Dashboards, appeals and SLA review

- **#7 Dashboards:** Students see their own complaints; Faculty, Committee and Dean
  accounts see their review queues. Both dashboards support status filters, refresh,
  ten-item pages, status badges and complaint details. Staff can use the actions
  authorized for the complaint's current review level.
- **#8 Appeals:** A student can appeal an eligible rejection once, with a required
  justification. The complaint reopens at the next review level; a Dean rejection
  stays with the Dean for final review. Stale actions refresh the details and
  preserve the explanation for an explicit retry.
- **#9 SLA review:** Only a Dean provisioned with `--sla-review` sees the manual
  overdue check. Results show the configured threshold, current handler and days
  overdue. One click escalates an active overdue complaint by one level, with a
  fresh version check and no escalation beyond the Dean. The default threshold is
  seven days, stored in `settings.sla_threshold_days`; a configuration screen is
  not included. There is no background escalation scheduler.

Session responses include the effective `can_review_sla` permission for the UI;
every action is independently authorized on the server. SLA escalation returns
summary fields only and does not grant access to another queue's complaint details.

See [Sprint 1 verification and screenshots](docs/sprint1/verification.md).

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
SCMS_SECRET_KEY=test python -m unittest discover -s tests -v   # real app + SQLite, including Issue #11
python -m unittest test_scms -v                                # original in-memory simulation
```

`test_scms.py` is the earlier in-memory simulation and cannot show durability; the tests
in `tests/` run against the real application, including a restart-persistence test.

## Future enhancements / Other issues

Login rate-limiting/throttling and configurable-threshold admin screen.
(Browser UI, accessibility, and performance targets are implemented and verified in Issue #11).
