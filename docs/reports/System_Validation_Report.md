# System Validation Report

**Project:** Smart Complaint Management System (SCMS)
**Team:** SE-MiniProject-Team-8
**Report ID:** SCMS-SVR-1.0
**Date of execution:** 15-11-2026
**Build under test:** `main` at `75d93e6` plus the test additions in this change
**Basis:** SRS v3.0 (requirements), Test Plan v3.0 (system test IDs ST-*)

## 1. Purpose

System validation answers the question *did we build the right system?*
It checks the delivered application, running end to end in a real browser
and through its public HTTP interface, against every requirement in the
SRS: functional (REQ), non-functional (NFR) and security (SEC). Unit-level
results are in the [Unit Testing Report](Unit_Testing_Report.md).

## 2. Scope

**In scope:** all 28 functional requirements REQ-1.1 to REQ-9.2, the
non-functional requirements NFR-PERF, NFR-DATA, NFR-USAB, NFR-MAIN and
NFR-REL, the security requirements SEC-01 to SEC-04, and the security
objectives SO-01 and SO-02.

**Out of scope** (as in Test Plan section 4): production hosting,
load beyond the mini-project workload, browsers other than Chromium, a
formal accessibility audit, and external integrations (ERP, SSO, email),
which the SRS excludes.

## 3. Environment

| Item | Value |
|---|---|
| Server | Flask development server started by `tests/run_product_browser.py` on a free local port, with a fresh temporary SQLite database |
| Browser | Headless Chromium driven by Playwright (`tests/product_browser.cjs`) |
| Viewports | 1280 × 900 desktop and 390 × 844 mobile |
| Accounts | One Student registered through the UI; Faculty, Committee and Dean (with SLA review) provisioned through `flask create-staff`, as in deployment |
| Local run | Linux x86_64, Python 3.13.18, SQLite 3.53.1, Google Chrome stable |
| CI run | GitHub Actions job `browser` (`ubuntu-latest`, Python 3.12, Playwright 1.64.1 with Chromium) on every push and pull request |

## 4. Validation methods

| Code | Method | Used for |
|---|---|---|
| **B** | End-to-end workflow in a real browser through the actual UI | User-visible functional behaviour |
| **A** | Automated system test through the public HTTP API with the database inspected afterwards | Rules not visible in the UI (atomicity, immutability, authorization on forged requests) |
| **M** | Measurement with the production password hash (`tests/measure_performance.py`) | Performance requirements |
| **I** | Inspection of code, schema or configuration | Structural requirements (modularity, hashing) |

## 5. End-to-end browser workflows

Executed on 15-11-2026. All 10 workflows passed with **zero uncaught page
JavaScript errors**. Raw result:
[`evidence/browser-validation.json`](evidence/browser-validation.json).

| # | Workflow (as executed by the browser) | Requirements exercised | Result |
|---|---|---|---|
| W1 | Student registers through the form and is signed in automatically | REQ-1.1, REQ-1.2 | Pass |
| W2 | Student submits an empty complaint form and sees the field-specific "required" error next to the field | REQ-2.2, NFR-USAB-01 | Pass |
| W3 | Low complaint containing a `<script>` tag is submitted, receives a reference ID, appears on the student's tracking list, and its audit history renders the text without creating a script element | REQ-2.1, REQ-2.3, REQ-3.1, REQ-6.2, REQ-7.1 | Pass |
| W4 | Faculty sees it in their queue with an in-app notice and resolves it with remarks | REQ-3.3, REQ-4.1, REQ-7.2 | Pass |
| W5 | Student is offered feedback only after resolution and submits a rating | REQ-9.1 | Pass |
| W6 | Medium complaint goes to Faculty and is rejected; the student appeals once, moving it to Committee; Committee escalates to Dean; Dean cannot escalate further | REQ-3.1, REQ-4.2, REQ-4.3, REQ-5.1, REQ-5.2, REQ-5.3 | Pass |
| W7 | High complaint goes straight to Committee; after a Dean rejection the appeal stays at Dean for final review | REQ-3.2, REQ-5.4, REQ-7.3 | Pass |
| W8 | Dean runs the manual overdue review, sees handler and days overdue, and escalates an overdue complaint | REQ-8.1, REQ-8.2 | Pass |
| W9 | The staff dashboard, resized to a 390-pixel mobile width, has no horizontal overflow | NFR-USAB-01 | Pass |
| W10 | After the session expires, private data is cleared from the UI and the user is returned to sign-in | REQ-1.3, SO-01 | Pass |

## 6. Requirement-by-requirement validation

System test IDs come from the Test Plan traceability matrix (section 13).

### 6.1 Functional requirements

| SRS ID | Requirement (short) | System test | Method | Evidence | Result |
|---|---|---|---|---|---|
| REQ-1.1 | Student registration | ST-AUTH-01 | B | W1 | Pass |
| REQ-1.2 | Authentication before protected access | ST-AUTH-02 | B, A | W1; AuthTests.test_protected_routes_require_login | Pass |
| REQ-1.3 | Role-restricted actions and views | ST-SEC-01 | B, A | W10; AccessCompletionTests (3) | Pass |
| REQ-1.4 | Generic invalid-login message | ST-SEC-02 | A | AuthTests.test_unknown_id_and_wrong_password_are_indistinguishable | Pass |
| REQ-2.1 | Submit category, description, severity | ST-CMP-01 | B | W3 | Pass |
| REQ-2.2 | Field-specific validation, nothing stored | ST-CMP-02 | B, A | W2; SubmissionTests.test_invalid_input_leaves_no_records | Pass |
| REQ-2.3 | Timestamp and unique Complaint ID | ST-CMP-03 | B, A | W3; SubmissionCompletionTests (UTC timestamps) | Pass |
| REQ-3.1 | Low/Medium to Faculty queue | ST-ROUTE-01 | B | W3, W6 | Pass |
| REQ-3.2 | High directly to Committee | ST-ROUTE-02 | B | W7 | Pass |
| REQ-3.3 | In-app notice on assignment | ST-ROUTE-03 | B | W4 (notice shown to the receiving queue) | Pass, see note 1 |
| REQ-4.1 | Resolve with mandatory remarks | ST-HND-01 | B | W4 | Pass |
| REQ-4.2 | Reject with mandatory reason | ST-HND-02 | B | W6 | Pass |
| REQ-4.3 | Escalate L1 → L2 → L3; no escalation from Dean | ST-HND-03 | B | W6 (Dean ceiling) | Pass |
| REQ-4.4 | Only the current level may act | ST-SEC-03 | A | HandlerActionTests.test_only_currently_assigned_level_may_act (forged requests from other roles) | Pass |
| REQ-5.1 | Appeal only if Rejected and not appealed | ST-APL-01 | B | W6 | Pass |
| REQ-5.2 | Appeal goes one level up, status Under Appeal Review | ST-APL-02 | B | W6 (Faculty rejection → Committee) | Pass |
| REQ-5.3 | Second appeal refused | ST-APL-03 | B, A | W6; AppealTests.test_database_enforces_one_appeal_even_if_service_check_is_bypassed | Pass |
| REQ-5.4 | Dean-level appeal: final review, no escalation | ST-APL-04 | B | W7 | Pass |
| REQ-6.1 | Immutable audit entry with actor, action, statuses, time | ST-AUD-01 | A | AuditTests.test_every_accepted_action_adds_exactly_one_audit_entry | Pass |
| REQ-6.2 | Audit visible to owner and past/current handlers | ST-AUD-02 | B, A | W3; AuditTests.test_history_is_complete_ordered_and_scoped | Pass |
| REQ-6.3 | No one can edit or delete audit entries | ST-SEC-04 | A | AuditTests.test_audit_has_no_write_routes; AuditTests.test_audit_rows_are_immutable_in_the_database (direct SQL `UPDATE`/`DELETE` rejected by triggers) | Pass |
| REQ-7.1 | Student sees only own complaints | ST-DASH-01 | B, A | W3; DashboardTests.test_role_scoped_dashboards | Pass |
| REQ-7.2 | Handler sees only their level's queue | ST-DASH-02 | B, A | W4; DashboardWorkflowTests.test_three_pages_are_complete_scoped_and_filterable | Pass |
| REQ-7.3 | Dean sees only complaints that reached L3 | ST-DASH-03 | B, A | W7; DashboardTests.test_role_scoped_dashboards | Pass |
| REQ-8.1 | Manual overdue check, configurable threshold (default 7 days) | ST-SLA-01 | B, A | W8; SlaWorkflowTests.test_configured_threshold_and_strict_boundary | Pass, see note 2 |
| REQ-8.2 | Show handler, days overdue, one-click escalate | ST-SLA-02 | B | W8 | Pass |
| REQ-9.1 | Rating 1–5 and optional comment after resolution | ST-FB-01 | B | W5 | Pass |
| REQ-9.2 | Handler view of feedback has no student identity | ST-FB-02 | A, I | FeedbackTests.test_handler_view_hides_student_identity; `feedback` table has no student column | Pass |

**Note 1, REQ-3.3.** Complaints are assigned to a role queue (Faculty,
Committee or Dean level), and the in-app notice is delivered to that
queue. Individual named handlers are not assigned. This matches the
architecture (SAD section 3.4) and is recorded as deviation D-02 in SRS v3.0.

**Note 2, REQ-8.** The SRS names "Dean/Admin". No separate Admin role was
built. The overdue review is available to a Dean account that has been
granted the `sla_review` permission at provisioning. Deviation D-01 in SRS v3.0.

### 6.2 Non-functional requirements

| SRS ID | Requirement | System test | Method | Measured / observed | Result |
|---|---|---|---|---|---|
| NFR-PERF-01 | Dashboard loads within 2 s | ST-PERF-01 | M | 250 complaints: Faculty dashboard median **1.3 ms**, p95 1.7 ms, max 1.8 ms; Student last page median 1.1 ms, max 1.6 ms | Pass |
| NFR-PERF-02 | Valid submission confirmed within 3 s | ST-PERF-02 | M | 250 submissions: median **2.8 ms**, p95 4.0 ms, max 4.8 ms | Pass |
| NFR-DATA-01 | Submitted complaints persist | ST-DATA-01 | B, A | W3; PersistenceTests.test_records_survive_application_restart | Pass |
| NFR-DATA-02 | Invalid submissions store nothing | ST-DATA-02 | A | SubmissionTests.test_invalid_input_leaves_no_records (row counts unchanged) | Pass |
| NFR-DATA-03 | Unique Complaint ID | ST-DATA-03 | A, I | `complaint_id INTEGER PRIMARY KEY`; W3 reference IDs distinct | Pass |
| NFR-DATA-04 | Chronological audit history | ST-DATA-04 | A | AuditTests.test_history_is_complete_ordered_and_scoped | Pass |
| NFR-USAB-01 | Clear labels and validation messages | ST-USAB-01 | B | W2, W9 | Pass |
| NFR-USAB-02 | Clear complaint status | ST-USAB-02 | B, I | W3 tracking list; colour-coded status badges (`.badge-status-*`) with the status as text, on every list | Pass |
| NFR-MAIN-01 | Modular structure | ST-MAIN-01 | I | Separate modules: `auth.py` (C03), `complaints.py` (C04), `routing.py` (C05), `audit.py` (C06), `feedback.py` (C07), `queries.py` (C08), `repository.py`/`db.py` (C09). Escalation logic exists only in `routing.py` | Pass |
| NFR-REL-01 | Records survive restart | ST-REL-01 | A | PersistenceTests.test_records_survive_application_restart (app object destroyed and recreated on the same file) | Pass |
| NFR-REL-02 | No success unless stored | ST-REL-02 | A | SubmissionTests.test_failed_write_rolls_back_everything; TransactionBoundaryTests (7), including a simulated `COMMIT` failure | Pass |

Performance figures are from
[`evidence/performance-measurement.json`](evidence/performance-measurement.json).
They are in-process timings with the Flask test client and the production
password hash, so network latency and browser rendering are excluded. The
SRS targets are three orders of magnitude above the measured values, so the
margin covers both.

## 7. Security validation (Test Plan section 5.5)

| Objective / requirement | Validation performed | Result |
|---|---|---|
| **SO-01 Confidentiality and access control** | Every protected route rejects requests with no session (401). Requests for another student's complaint, or from a role whose level does not hold it, return 404, which does not reveal that the record exists. Role changes take effect in the existing session. An expired session clears the UI (W10) | Pass |
| **SO-02 Integrity and accountability** | Each accepted action writes exactly one audit row in the same transaction as the state change. Audit rows cannot be changed even with direct SQL (triggers). Stale versions are rejected without changes, which prevents lost updates | Pass |
| **SEC-01** Hashed passwords only | Stored value is a salted `pbkdf2:sha256` hash. The plaintext never appears in the database or in any API response | Pass |
| **SEC-02** Server-side authorization | Forged API calls that bypass the UI are refused by `auth.py` checks (REQ-4.4 tests). The role is always re-read from the database; it is never trusted from the cookie | Pass |
| **SEC-03** Audit records protected | No route mutates audit data, and database triggers abort `UPDATE` and `DELETE` | Pass |
| **SEC-04** Generic login failure | An unknown ID and a wrong password return an identical body and status. A dummy hash is checked for unknown IDs, so timing does not reveal which accounts exist | Pass |
| Additional: CSRF | Every unsafe request without a valid `X-CSRF-Token` is refused (403) before any work is done; tokens rotate on login | Pass |
| Additional: Stored script injection | Complaint text containing a `<script>` tag is displayed as text in the audit view; no script element is created (W3) | Pass |
| Additional: Error disclosure | Internal errors return a generic message with a request ID. Database errors never reach the client | Pass |

## 8. Defects found during system validation

| ID | Found | Description | Severity | Status |
|---|---|---|---|---|
| SV-01 | 02-11-2026, first real-browser run | Staff filter controls overflowed horizontally at a 390-pixel width | Low (layout only) | Fixed in PR #22; W9 passes |

No defects were found in the 15-11-2026 run.

## 9. Limitations

* Validated in Chromium only. Firefox and Edge, listed in the Test Plan
  environment, were not run automatically.
* Single-server, single-file SQLite deployment. Concurrency was validated
  through version conflicts and SQLite locking, not under parallel load.
* No formal WCAG audit. Labels, keyboard attributes and the mobile layout of
  the staff dashboard were checked (TC-16, W9).

## 10. Conclusion

The delivered SCMS satisfies all 28 functional requirements, all listed
non-functional requirements and all four security requirements, with two
documented deviations in how REQ-3.3 and REQ-8 are realised (role-queue
assignment, and Dean with SLA permission in place of a separate Admin
role). The system is accepted for demonstration.
