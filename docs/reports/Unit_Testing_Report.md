# Unit Testing Report

**Project:** Smart Complaint Management System (SCMS)
**Team:** SE-MiniProject-Team-8
**Report ID:** SCMS-UTR-1.0
**Date of execution:** 15-11-2026
**Build under test:** `main` at `75d93e6` plus the test additions in this change
**Related documents:** SRS v3.0, SAD v2.0, Test Plan v3.0 (all in `docs/`)

## 1. Purpose

This report records the execution and results of the automated unit and
integration tests for SCMS, and maps them to the test cases defined in
Test Plan section 13.1 (TC-01 to TC-18). The code coverage achieved by the
same run is reported separately in the
[Code Coverage Report](Code_Coverage_Report.md) and the
[Branch Coverage Report](Branch_Coverage_Report.md).

## 2. Test items

| Item | Location | Notes |
|---|---|---|
| Application package | `scms/` (13 modules, 808 statements) | Flask 3.1.3, Werkzeug 3.1.8, SQLite |
| Unit and integration tests | `tests/test_*.py` (7 modules, 96 tests) | Python `unittest`; each test uses a fresh temporary SQLite file |
| Design-stage model tests | `test_scms.py` (10 tests) | Tests an in-file model (`SCMSCore`), not the `scms` package. Reported separately in section 6 |

## 3. Environment

| Item | Value |
|---|---|
| Local run | Linux x86_64, Python 3.13.18, SQLite 3.53.1 |
| CI run | GitHub Actions `ubuntu-latest`, Python 3.12 (`.github/workflows/ci.yml`, job `application`) |
| Test runner | `python -m coverage run -m unittest discover -s tests -v` |
| Isolation | Every test class creates its own temporary database and removes it in `tearDown`. No test depends on another's data. A cheap password hash (`pbkdf2:sha256:1000`) is used in tests only; production uses the Werkzeug default iteration count |

## 4. Approach

* **Unit level.** Pure functions are tested directly: `routing.py`
  (initial level, next level, appeal target), `validation.py`, `db.transaction`
  and the repository guards.
* **Component and integration level.** Each service (auth, complaints,
  audit, feedback, queries) is exercised through the real JSON API
  (`/api/v1`) with the Flask test client, which keeps the session cookie
  and CSRF token like the browser does. Assertions check both the HTTP
  response and the resulting rows in SQLite (complaint, assignment history,
  audit log, notification), so a test fails if a workflow leaves partial
  state.
* **Fault injection.** Database failures are simulated (failed `BEGIN`,
  failed write, failed `COMMIT`, failed `ROLLBACK`, unexpected exception) to
  verify NFR-REL-02: success is never reported unless the write committed.
* **Negative and security cases.** Wrong role, wrong owner, stale version,
  missing CSRF token, expired session, duplicate appeal, edited audit row.

## 5. Results summary

| Metric | Value |
|---|---|
| Tests executed | **96** |
| Passed | **96** |
| Failed / errors / skipped | 0 / 0 / 0 |
| Execution time | 6.0 s |
| Line coverage of `scms/` | 98.4 % (795 / 808 statements) |
| Branch coverage of `scms/` | 91.8 % (156 / 170 branches) |
| Raw output | [`evidence/unit-test-output.txt`](evidence/unit-test-output.txt) |

The one `unhandled RuntimeError request_id=…` line in the raw output is
expected. It is logged by
`SubmissionTests.test_unexpected_error_rolls_back_and_hides_details`, which
deliberately raises an internal error and verifies that the client receives
only a generic message with a request ID.

### 5.1 Results by test module

| Module | Test classes | Tests | Result | What it verifies |
|---|---|---:|---|---|
| `test_app.py` | AuthTests, SubmissionTests, HandlerActionTests, AppealTests, AuditTests, DashboardTests, SlaTests, FeedbackTests, PersistenceTests, ModuleBoundaryTests, ApiConventionTests, Issue11UsabilityPerformanceTests | 56 | Pass | Core requirements REQ-1 to REQ-9, SEC-01 to SEC-04, error contract, usability markup and performance targets |
| `test_sprint_workflows.py` | AppealWorkflowTests, DashboardWorkflowTests, SessionCapabilityTests, SlaWorkflowTests | 13 | Pass | Sprint 1 issues #7 to #9: role queues, appeal flow, dashboard paging, SLA permission and stale actions |
| `test_access_completion.py` | AccessCompletionTests | 3 | Pass | Expired sessions, cross-owner and unassigned-role denial, role change during a session |
| `test_account_completion.py` | AccountCompletionTests | 2 | Pass | Login validation without account disclosure, session rotation failure |
| `test_submission_completion.py` | SubmissionCompletionTests | 2 | Pass | Field limits, injected server fields, UTC timestamps, persistence across restart |
| `test_operations.py` | StaffProvisioningCliTests, TransactionBoundaryTests, BoundaryAndEdgeBranchTests | 20 | Pass | Staff provisioning CLI, transaction failure paths, edge branches found by the coverage report |
| **Total** | **22 classes** | **96** | **Pass** | |

### 5.2 Traceability to Test Plan test cases (section 13.1)

| Test Plan ID | Scenario | SRS mapping | Automated tests (class.method) | Result |
|---|---|---|---|---|
| TC-01 | User registration and authentication | REQ-1.1, REQ-1.2 | AuthTests.test_registration_cannot_choose_role_and_duplicates_conflict; AuthTests.test_csrf_login_rotation_and_logout; AccountCompletionTests (2) | Pass |
| TC-02 | Role-based authorization | REQ-1.3, SEC-02 | AuthTests.test_protected_routes_require_login; AccessCompletionTests.test_other_owner_and_unassigned_roles_cannot_read_or_mutate; AccessCompletionTests.test_role_changes_apply_to_an_existing_session; PersistenceTests.test_staff_session_state_not_trusted_from_cookie; DashboardTests.test_invisible_complaint_looks_like_missing | Pass |
| TC-03 | Invalid credential generic error | REQ-1.4, SEC-04 | AuthTests.test_unknown_id_and_wrong_password_are_indistinguishable; AccountCompletionTests.test_login_validates_missing_fields_without_revealing_accounts | Pass |
| TC-04 | Complaint submission validation | REQ-2.1, REQ-2.2 | SubmissionTests.test_invalid_input_leaves_no_records; SubmissionTests.test_only_students_submit; SubmissionCompletionTests.test_invalid_fields_and_injected_server_fields_leave_no_partial_records | Pass |
| TC-05 | Severity-based routing | REQ-3.1, REQ-3.2 | SubmissionTests.test_severity_routing; ModuleBoundaryTests.test_initial_level | Pass |
| TC-06 | Handler resolve / reject / escalate | REQ-4.1 to REQ-4.4 | HandlerActionTests (all 7); ModuleBoundaryTests.test_next_level_and_dean_ceiling | Pass |
| TC-07 | Appeal workflow | REQ-5.1 to REQ-5.4 | AppealTests (all 5); AppealWorkflowTests (all 3); ModuleBoundaryTests.test_appeal_target | Pass |
| TC-08 | Audit trail integrity | REQ-6.1 to REQ-6.3, SEC-03 | AuditTests (all 4) | Pass |
| TC-09 | Dashboard filtering | REQ-7.1 to REQ-7.3 | DashboardTests.test_role_scoped_dashboards; DashboardTests.test_pagination_and_filter_validation; DashboardWorkflowTests.test_three_pages_are_complete_scoped_and_filterable | Pass |
| TC-10 | SLA overdue review | REQ-8.1, REQ-8.2 | SlaTests (all 5); SlaWorkflowTests (all 4); SessionCapabilityTests (all 4) | Pass |
| TC-11 | Post-resolution feedback | REQ-9.1, REQ-9.2 | FeedbackTests (all 4) | Pass |
| TC-12 | Dashboard response time | NFR-PERF-01 | Issue11UsabilityPerformanceTests.test_dashboard_performance_target_under_two_seconds; DashboardWorkflowTests.test_dashboard_queries_with_250_records_stay_under_two_seconds; Issue11UsabilityPerformanceTests.test_performance_indexes_exist | Pass |
| TC-13 | Complaint submission response time | NFR-PERF-02 | Issue11UsabilityPerformanceTests.test_valid_complaint_is_confirmed_within_three_seconds; Issue11UsabilityPerformanceTests.test_repeated_submissions_stay_under_target | Pass |
| TC-14 | Persistence and invalid-record behaviour | NFR-DATA-01, NFR-DATA-02 | SubmissionTests.test_submission_writes_complaint_history_audit_and_notice_together; SubmissionTests.test_invalid_input_leaves_no_records | Pass |
| TC-15 | Password hashing | SEC-01 | AuthTests.test_password_is_salted_hash_and_never_returned; StaffProvisioningCliTests.test_create_staff_stores_hashed_password_and_role | Pass |
| TC-16 | Usability: validation messages and status | NFR-USAB-01, NFR-USAB-02 | Issue11UsabilityPerformanceTests.test_browser_form_has_clear_labels_and_field_specific_errors; …test_browser_keyboard_and_form_attributes; …test_browser_page_structure_accessibility_and_responsiveness | Pass |
| TC-17 | Persistence after restart | NFR-REL-01 | PersistenceTests.test_records_survive_application_restart; PersistenceTests.test_init_db_is_idempotent_and_keeps_data; SubmissionCompletionTests.test_documented_limits_location_timestamps_and_restart | Pass |
| TC-18 | No false success before storage | NFR-REL-02 | SubmissionTests.test_failed_write_rolls_back_everything; SubmissionTests.test_unexpected_error_rolls_back_and_hides_details; TransactionBoundaryTests (all 7) | Pass |

All 18 planned test cases are covered by at least one passing automated
test. TC-12, TC-13 and TC-16 are also validated at system level (see the
[System Validation Report](System_Validation_Report.md)).

## 6. Design-stage model tests (`test_scms.py`)

`test_scms.py` was written for Test Plan v2.0 before the application
existed. It defines its own `SCMSCore` class and tests that model, so it
does not exercise any code in `scms/`. Its 10 tests pass (0.001 s, see
[`evidence/design-model-test-output.txt`](evidence/design-model-test-output.txt)),
but they are **not counted** in the 96 above or in the coverage figures.
Each rule it checks is verified against the real application:

| `test_scms.py` test | Real-application equivalent |
|---|---|
| test_ut_1_01_valid_registration | AuthTests.test_registration_cannot_choose_role_and_duplicates_conflict |
| test_ut_1_03_invalid_credentials_generic_message | AuthTests.test_unknown_id_and_wrong_password_are_indistinguishable |
| test_ut_2_02_mandatory_fields_rejection | SubmissionTests.test_invalid_input_leaves_no_records |
| test_ut_3_routing_logic | SubmissionTests.test_severity_routing |
| test_ut_4_01_resolve_remarks_mandatory | HandlerActionTests.test_resolve_requires_remarks_and_records_audit |
| test_ut_4_03_escalation_ceiling | HandlerActionTests.test_escalation_chain_and_dean_ceiling |
| test_ut_5_02_prevent_second_appeal | AppealTests.test_second_appeal_is_blocked |
| test_it_6_01_audit_log_generation | AuditTests.test_every_accepted_action_adds_exactly_one_audit_entry |
| test_ut_8_sla_overdue_flagging | SlaTests.test_check_lists_overdue_without_changing_state |
| test_ut_9_01_feedback_score_validation | FeedbackTests.test_rating_validation_and_single_feedback |

CI still runs `test_scms.py` as a separate, clearly labelled step so that
Test Plan v2.0 remains traceable.

## 7. Tests added during this reporting cycle

Running coverage showed that `scms/cli.py` (61 %) and `scms/db.py` (83 %)
had untested paths, including the transaction failure branches that NFR-REL-02
depends on. `tests/test_operations.py` was added with 20 tests:

* **StaffProvisioningCliTests (5).** `init-db` is idempotent. `create-staff`
  stores a hashed password and the requested role. Dean accounts can be
  granted SLA review. Duplicate accounts fail with a clean message. The
  Student role cannot be provisioned through the CLI.
* **TransactionBoundaryTests (7).** A successful block commits. A failed
  `BEGIN`, an SQLite error in the block, an unexpected exception, a failed
  `COMMIT` and a failed `COMMIT` plus failed `ROLLBACK` each leave the
  database unchanged and raise `PERSISTENCE_UNAVAILABLE` (or re-raise).
  In-memory databases skip the file-only pragmas.
* **BoundaryAndEdgeBranchTests (8).** Configuration from environment
  variables; health check OK and unavailable; unsafe request without a
  session; registration with a missing password and a bad email; direct
  staff creation with the Student role; invalid SLA threshold values; the
  repository column allow-list and an empty audit list; validator
  type and paging errors.

No defects in application code were found by these tests. Every new test
passed against the existing implementation.

## 8. Defects

No open defects. Defects found earlier in the project and fixed before this
run are recorded in the pull requests that fixed them. The most recent was
the narrow-screen filter overflow found by the real-browser check and fixed
in PR #22.

## 9. Variances from the Test Plan

* The Test Plan listed the test cases as manual-or-automated. All 18 are now
  automated, so they are repeatable in CI.
* `test_scms.py` is reported as design-stage model tests, not as unit tests
  of the application (section 6).
* Performance targets are checked at a mini-project workload (250
  complaints), as the Test Plan specifies. This is not a production load test.

## 10. Conclusion

All 96 unit and integration tests pass on the delivered code, every Test
Plan test case TC-01 to TC-18 is covered by passing automated tests, and
the exit criterion of no open critical defects (Test Plan section 5.4) is met.
