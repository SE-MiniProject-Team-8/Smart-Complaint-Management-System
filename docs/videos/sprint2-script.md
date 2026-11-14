# Sprint 2 video script (2 minutes)

**Build:** `main` (application code frozen at `75d93e6`; later commits change only tests, CI and documents)
**Sprint 2 issues shown:** #1 authentication, #2 submission, #3 session
access, #4 severity assignment, #5 resolution and escalation, #6 audit
trail, plus the final test and coverage results

## Before recording

```sh
git switch main && git pull --ff-only
```

Follow the common setup in [README.md](README.md). Before you press record,
open a second browser window (or a private window) for the staff accounts.

## Shot list

| Time | Screen | Narration |
|---|---|---|
| 0:00–0:05 | Title card: "SCMS, Team 8, Sprint 2 final build. Recorded <date>" | "This is the final Sprint 2 build of SCMS." |
| 0:05–0:20 | Register student `S001`. Then sign out and sign in with a wrong password, then with an unknown ID: the same message both times | "Students register themselves and are always created as Students. Staff are created only by the operator. A failed login shows the same message whether the ID or the password was wrong." |
| 0:20–0:35 | Click Submit with an empty form: field errors appear. Submit *Low* "Projector not working" and *High* "Exam paper leak". Show the reference IDs | "Each field is validated, and nothing is saved until it is valid. Low and Medium go to Faculty; High goes straight to the Grievance Committee." |
| 0:35–0:55 | Staff window: sign in `FAC001`. The notice and the Low complaint are visible; the High one is not. Try Resolve with blank remarks (error), then resolve with remarks | "Faculty see only their queue, with an in-app notice. Resolving requires remarks." |
| 0:55–1:10 | Sign in `COM001`, escalate the High complaint. Sign in `DEAN01`: it is there; there is no Escalate button | "The Committee can escalate to the Dean. The Dean is the last level and cannot escalate further." |
| 1:10–1:25 | Student window: open the resolved complaint, show its audit history (Submit, Resolve with actor and time). Submit a 4-star feedback | "Every action is written to an audit trail that nobody can edit, not even through the database. Feedback is offered once, after resolution, and handlers see it without the student's identity." |
| 1:25–1:35 | Leave the staff window idle, then in a terminal expire the session (or wait), click Refresh: back to sign-in, private data cleared | "Protected requests need a valid session and CSRF token. An expired session clears the screen." |
| 1:35–1:50 | GitHub, Actions tab: a green "Application checks" run with the application and browser jobs; open the coverage summary | "Every push runs 96 tests, a real Chromium walkthrough and a coverage gate in GitHub Actions." |
| 1:50–2:00 | `docs/reports/` on GitHub: the four reports | "Coverage is 98 % of lines and 92 % of branches. The reports and updated SRS, SAD and Test Plan are in the docs folder. Thank you." |

To expire the session for the 1:25 scene:

```sh
python -c "import os,sqlite3; c=sqlite3.connect(os.environ['SCMS_DATABASE']); c.execute(\"UPDATE sessions SET expires_at='2000-01-01T00:00:00Z'\"); c.commit()"
```
