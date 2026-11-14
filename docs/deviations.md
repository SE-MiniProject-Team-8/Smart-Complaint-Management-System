# Deviations: plan versus delivery

**Project:** Smart Complaint Management System (SCMS), SE-MiniProject-Team-8
**Updated:** 15-11-2026

This document records where the project differed from the course plan:
schedule, process and scope. Dates come from the repository history
(commit and merge timestamps) and GitHub. Scope deviations are summarised
here and specified in SRS v3.0 Section 8 and SAD v2.0 Section 5 3.

## 1. Schedule

| Deliverable | Planned | Actual | Deviation |
|---|---|---|---|
| SRS (IEEE format) | 28-09-2026 | v1.1 committed 11-09-2026; v2.0 committed 02-10-2026 | v2.0 four days late |
| Test Plan (IEEE format) | 28-09-2026 | v1.0 committed 11-09-2026; v2.0 and initial tests committed 02-10-2026 | v2.0 four days late |
| SAD, Section 4 Design | 28-09-2026 | Committed 11-10-2026 (`Member 4/`, now `docs/archive/SAD_Section4_Design_v1.0.docx`) | 13 days late |
| SAD, Section 3 Architecture | 28-09-2026 | Committed between 11-10-2026 and 14-10-2026 (`Member3-Architecture/`, now `docs/archive/SAD_Section3_Architecture_v1.0.docx`). The three commits (`cb62f62`, `bc917c8`, `74c5630`) show 03-10-2026 because the date was set on the local machine; their parent commit `d83e2a5` is from 11-10-2026 | About 14 days late |
| SAD as one document | 28-09-2026 | Sections 3 and 4 combined, with the as-built update, as `docs/SCMS_SAD_v2.0.docx` on 15-11-2026 | Combined late; content of Sections 3 and 4 unchanged |
| Backlog (GitHub Project, issues, story points, sprints) | 12-10-2026 | Issues #1 to #12 exist, three per member. Creation dates and board history are recorded on GitHub | See GitHub for exact dates |
| Sprint 1 (19 to 23-10-2026) | PRs raised, reviewed and merged in the window | PRs #13 and #14 merged 22-10-2026. PR #15 merged 24-10-2026 | PR #15 merged one day after the sprint |
| Sprint 1 video (1 min) | During Sprint 1 | Not recorded during the sprint. Recorded after the code freeze (see section 4) | Late |
| Sprint 2 (26 to 30-10-2026) | Remaining issues merged | Work committed from 31-10-2026; PRs #16 to #18 merged 01 to 02-11-2026; PRs #19 to #23 merged 02-11-2026 | Two to three days late |
| Code freeze | 30-10-2026 | 02-11-2026 (merge of PR #23, `75d93e6`) | Three days late. No application code changed after this; later changes are tests, CI and documents only |
| Documents updated to the delivered system | End of Sprint 2 | SRS v3.0, Test Plan v3.0, SAD v2.0 on 15-11-2026 | Late |
| Sprint 2 video (2 min) | During Sprint 2 | Recorded after the code freeze (see section 4) | Late |
| Unit Testing, System Validation, Code Coverage, Branch Coverage reports | Before the demo | `docs/reports/`, 15-11-2026 | On time |

## 2. Process

| Expected process | What happened | Effect and correction |
|---|---|---|
| Every PR reviewed by the repository owner before merging | PRs #19, #20 and #21 (issues #1 to #3, owned by the repository owner) were opened and merged by the same person without a second reviewer | No independent review of those three PRs. All of their behaviour is covered by the automated tests and the browser workflow, which CI runs on every push |
| GitHub Actions enabled and run on every PR from Sprint 1 | The workflow `.github/workflows/ci.yml` was first added on 02-11-2026 (commit `dc74afb`). PRs #13, #14, #15, #17 and #18 were merged before it existed and had no automated check. The real-browser job was added in PR #22 | Every later push and PR runs the full suite. The tests from the earlier PRs are part of that suite and pass. Coverage measurement and a 90 % coverage gate were added on 15-11-2026 |
| Tests exercise the application | `test_scms.py` (Test Plan v2.0) tests an in-file model, not the `scms` package | Labelled as design-stage model tests in the file and in CI. Every rule it checks is also tested against the real application (Unit Testing Report, section 6) |
| Deliverable documents in `docs/` | SRS, Test Plan and SAD sections were kept at the repository root and in per-member folders | Current versions are in `docs/`. Earlier versions are kept unchanged in `docs/archive/` |

## 3. Scope

The delivered system implements every SRS requirement. These points are
realised differently from the Version 2.0 wording:

| ID | Summary | Detail |
|---|---|---|
| DV-01 | No separate Admin role; the SLA review belongs to a Dean with the `sla_review` permission | SRS v3.0 §8, SAD v2.0 5 3 D-01 |
| DV-02 | Complaints are assigned to a level queue, not a named handler; notices go to the queue | SRS v3.0 §8, SAD D-02 |
| DV-03 | Closed (Resolved or Rejected) complaints are not listed as overdue | SRS v3.0 §8, SAD D-03 |
| DV-04 | The SLA escalation works across queues without granting detail access | SRS v3.0 §8, SAD D-04 |
| DV-05 | Registration creates an active Student account; staff accounts are created only by the operator CLI | SRS v3.0 §8 |
| DV-06 | Feedback is offered as a form on resolved complaints, not as a pop-up prompt | SRS v3.0 §8 |
| DV-07 | Schema extended (sessions, assignment history, appeals, notifications, settings, version columns) | SRS v3.0 §8, SAD 5 3 D-05 |
| DV-08 | Verified on Python 3.12 and 3.13, Chromium only | SRS v3.0 §8, Test Plan v3.0 §15.6 |

## 4. Sprint videos

Neither video was recorded during its sprint window. Both are recorded
from the delivered build after the code freeze and are labelled with the
date they were recorded. The Sprint 1 video is recorded from commit
`35e4919`, the state of `main` immediately after the Sprint 1 PRs (#13,
#14, #15) were merged, so it shows only Sprint 1 functionality. Recording
scripts: `docs/videos/`.
