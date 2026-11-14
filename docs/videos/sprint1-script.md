# Sprint 1 video script (1 minute)

**Build:** commit `35e4919` (main immediately after PRs #13, #14 and #15)
**Sprint 1 issues shown:** #12 persistence and modules, #11 usability and
performance, #7 role dashboards, #8 appeals, #9 SLA review

## Before recording

```sh
git fetch origin
git switch --detach 35e4919
```

Then follow the common setup in [README.md](README.md). Before you press
record:

1. As a student (register `S001` through the form), submit three complaints:
   *Low* "Projector not working", *Medium* "Lab timetable clash", and *Low*
   "Library AC broken".
2. Signed in as `FAC001`, reject the Medium complaint with the reason "Not enough detail".
3. Age the "Library AC broken" complaint so it is overdue (README, "Making a complaint overdue").

After recording, return to the latest code with `git switch main`.

## Shot list

| Time | Screen | Narration |
|---|---|---|
| 0:00–0:05 | Title card: "SCMS, Team 8, Sprint 1 (commit 35e4919). Recorded <date>" | "This is our Sprint 1 build of the Smart Complaint Management System." |
| 0:05–0:15 | Student `S001`, Track My Complaints tab: three complaints with coloured status badges | "Complaints are stored in SQLite and each student sees only their own, with a clear status for each." |
| 0:15–0:30 | Student opens the Rejected complaint, types a justification, clicks Appeal. Status changes to *Under Appeal Review* | "A rejected complaint can be appealed once. Faculty rejected this one, so the appeal goes up one level to the Grievance Committee. The Appeal button is then gone." |
| 0:30–0:40 | Sign in as `COM001`: the appealed complaint is in the Committee queue. Use the status filter | "The Committee dashboard shows only its own queue, with filters and paging." |
| 0:40–0:55 | Sign in as `DEAN01`, open Overdue Review, click "Check overdue complaints". The aged complaint shows handler and days overdue. Click Escalate | "The Dean runs the SLA check by hand. No scheduler is involved. This complaint was aged for the demo. It shows the current handler and days overdue, and one click escalates it." |
| 0:55–1:00 | Terminal: `python -m unittest discover -s tests` → `Ran 68 tests … OK` | "All 68 tests pass on this build." |

At `35e4919` the suite has 68 tests. Run the command once before recording
to confirm the count on your machine.
