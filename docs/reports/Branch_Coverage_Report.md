# Branch Coverage Report

**Project:** Smart Complaint Management System (SCMS)
**Team:** SE-MiniProject-Team-8
**Report ID:** SCMS-BCR-1.0
**Date of measurement:** 15-11-2026
**Build measured:** `main` at `75d93e6` plus the test additions in this change

## 1. Purpose

Statement coverage shows which lines ran. Branch coverage is stricter: for
every decision (`if`, `while`, `for`, boolean short-circuit exits) it
checks that **each possible outcome** was taken at least once. A line such
as `if not row: raise not_found()` can be fully covered as a line while the
"row exists" outcome is never tested, or the reverse. This report gives
the branch coverage of SCMS, lists every untaken branch and assesses it.

## 2. Tool and method

| Item | Value |
|---|---|
| Tool | coverage.py 7.17.3 with branch measurement (`.coveragerc`: `branch = True`) |
| Command | `python -m coverage run -m unittest discover -s tests -v`, then `python -m coverage report` (columns *Branch* and *BrPart*) |
| Branch definition | coverage.py arc analysis: each possible jump from a decision line to a destination line is one branch. A two-way `if` counts as 2 branches |
| Measured code | `scms/` package, 170 branches across 13 modules |
| CI enforcement | Combined line + branch coverage must stay at or above 90 % (`fail_under = 90`); the CI build fails otherwise |

## 3. Summary

| Measure | Before (76 tests) | After (96 tests) |
|---|---:|---:|
| Total branches | 170 | 170 |
| Branches taken | 146 | **156** |
| Branches never taken | 24 | **14** |
| Decision lines with at least one untaken outcome ("partial") | 22 | **14** |
| **Branch coverage** | 85.9 % | **91.8 %** |
| Combined line + branch | 93.0 % | **97.2 %** |

## 4. Branch coverage by module

| Module | Component | Branches | Taken before | Taken after | Branch coverage after | Partial decisions after |
|---|---|---:|---:|---:|---:|---:|
| `scms/__init__.py` | App factory | 4 | 3 | 4 | 100.0 % | 0 |
| `scms/api.py` | C02 Web API | 32 | 28 | 30 | 93.8 % | 2 |
| `scms/audit.py` | C06 Audit | 0 | – | – | no decisions | 0 |
| `scms/auth.py` | C03 AuthService | 30 | 25 | 28 | 93.3 % | 2 |
| `scms/cli.py` | Operator CLI | 0 | – | – | no decisions | 0 |
| `scms/complaints.py` | C04 ComplaintService | 30 | 27 | 27 | 90.0 % | 3 |
| `scms/db.py` | C09 transactions | 2 | 1 | 2 | 100.0 % | 0 |
| `scms/errors.py` | Error contract | 0 | – | – | no decisions | 0 |
| `scms/feedback.py` | C07 Feedback | 8 | 6 | 6 | 75.0 % | 2 |
| `scms/queries.py` | C08 Queries / SLA | 16 | 13 | 13 | 81.2 % | 3 |
| `scms/repository.py` | C09 Repository | 10 | 7 | 9 | 90.0 % | 1 |
| `scms/routing.py` | C05 RoutingPolicy | 6 | 6 | 6 | 100.0 % | 0 |
| `scms/validation.py` | Input validation | 32 | 30 | 31 | 96.9 % | 1 |
| **Total** | | **170** | **146** | **156** | **91.8 %** | **14** |

`db.py` has only 2 measured branches because its `try`/`except` handlers are
exception paths, which coverage.py counts as statements rather than
branches. All of those handlers are executed (statement coverage of `db.py`
is 100 %; see the [Code Coverage Report](Code_Coverage_Report.md)).

## 5. Decision logic with complete branch coverage

The decisions that encode the SRS business rules are fully covered (every
outcome taken):

| Rule | Code | Outcomes tested |
|---|---|---|
| Severity routing (REQ-3.1, 3.2) | `routing.initial_level` | Low → L1, Medium → L1, High → L2, unknown severity rejected |
| Escalation ceiling (REQ-4.3) | `routing.next_level` | L1 → L2, L2 → L3, L3 → refused |
| Appeal target (REQ-5.2, 5.4) | `routing.appeal_target` | Rejected at L1 → L2, at L2 → L3, at L3 → stays L3 with final review |
| Current-level authorization (REQ-4.4) | `complaints._load_for_handler` | Assigned level acts; other levels refused |
| Terminal states | `complaints._require_active` | Active complaint proceeds; Resolved and Rejected refused |
| Single appeal (REQ-5.1, 5.3) | `complaints.appeal` eligibility checks | Rejected and not appealed allowed; already appealed refused; not rejected refused |
| SLA permission (REQ-8) | `auth.can_review_sla` | Dean with permission allowed; Dean without, and non-Dean with the flag, refused |
| Overdue boundary (REQ-8.1) | `queries.sla_check` threshold comparison | Strictly over the threshold listed; exactly at the threshold not listed |
| Optimistic version | `update_complaint_state(...) != 1` | Current version accepted; stale version refused (resolve, appeal, SLA) |
| Transaction outcome (NFR-REL-02) | `db.transaction` | Commit; app error, SQLite error, other exception and commit failure all roll back |

## 6. Untaken branches (14) and assessment

The format is `file:line → destination`. "→ exit" means the outcome that
leaves the decision without entering its body.

| # | Branch | Outcome never taken | Assessment |
|---|---|---|---|
| 1 | `api.py:44 → 45` | Optional JSON body is completely empty | Only `/sla/check` allows it. The UI always sends `{}`. Low risk |
| 2 | `api.py:72 → 73` | Unsafe request with no session to the `logout` endpoint | **Infeasible.** `logout` is not public, so line 68 raises 401 first. The branch can never be taken. Dead defensive code |
| 3 | `auth.py:127 → 129` | Login when the caller has no pre-login session | The browser and tests always fetch a session (and CSRF token) first, so `old_session_id` is always set. Low risk: the false outcome simply skips a delete |
| 4 | `auth.py:144 → 145` | Session refers to a user that no longer exists | Users are never deleted. Low risk |
| 5 | `complaints.py:47 → 48` | Owner views a resolved complaint with no feedback yet (unit level) | Taken in the browser test (W5). Not asserted by a unit test |
| 6 | `complaints.py:144 → 147` | Stale version on *reject* | Same optimistic-update pattern is tested on resolve, appeal and SLA escalation |
| 7 | `complaints.py:183 → 184` | A visible non-owner (handler) attempts an appeal | Handlers are never offered the action; the 404 response is shared with other paths |
| 8 | `feedback.py:18 → 19` | A handler who can see the complaint submits feedback | Tested for another student (404), not for a handler |
| 9 | `feedback.py:44 → 45` | Read feedback before any exists | Low risk; returns 404 |
| 10 | `queries.py:69 → 67` | A candidate returned by SQL is not actually over the threshold | The SQL cutoff already filters these out, so in practice the Python re-check is always true. Defensive double-check |
| 11 | `queries.py:94 → 95` | SLA escalation of a non-existent complaint | Low risk; returns 404 |
| 12 | `queries.py:96 → 97` | SLA escalation of a Resolved or Rejected complaint | `/sla/check` never offers these. The general terminal-state rule is tested for handler actions |
| 13 | `repository.py:96 → 103` | Overdue query called without a cutoff | No caller does this. Unused default |
| 14 | `validation.py:49 → 51` | `text()` called with `strip=False` | No current caller uses `strip=False` |

**Classification:**

| Category | Count | Branches |
|---|---:|---|
| Infeasible or dead code | 3 | #2, #10, #13 |
| Unused parameter value | 1 | #14 |
| Covered only at system level | 1 | #5 |
| Defensive error paths with low risk | 9 | #1, #3, #4, #6, #7, #8, #9, #11, #12 |
| **Untested branches that implement an SRS rule** | **0** | – |

Excluding the 3 infeasible branches, achievable branch coverage is
156 / 167 = **93.4 %**.

## 7. Improvements made in this cycle

The first measurement had 24 untaken branches. Ten were closed by
`tests/test_operations.py`:

| Module | Branch closed (`line → destination`) | Outcome now tested | Test |
|---|---|---|---|
| `__init__.py` | 37 → 39 | App built with no test overrides (configuration from environment) | `test_app_reads_configuration_from_environment_when_no_overrides` |
| `api.py` | 71 → 72, 72 → 74 | Unsafe request arriving with no session at all is refused with `CSRF_FAILED` | `test_unsafe_request_without_session_is_rejected_before_any_work` |
| `auth.py` | 53 → 54, 55 → 56 | Registration with a missing password; with an invalid email | `test_registration_rejects_missing_password_and_bad_email` |
| `auth.py` | 65 → 66 | Direct staff creation with the Student role | `test_create_staff_rejects_student_role_even_when_called_directly` |
| `db.py` | 27 → 30 | `:memory:` database skips the file-only pragmas | `test_in_memory_database_skips_file_only_pragmas` |
| `repository.py` | 72 → 73, 156 → 157 | Unknown column refused; audit list for a complaint with no entries | `test_repository_refuses_unknown_columns_and_handles_empty_audit` |
| `validation.py` | 63 → 65 | Optional integer field absent | `test_field_validators_reject_wrong_types_and_bad_paging` |

The other new tests (health-check failure, invalid paging values,
non-text field values, the CLI and the transaction failure handlers) closed
statement gaps on exception paths, which coverage.py does not count as
branches. They are reported in the [Code Coverage Report](Code_Coverage_Report.md).

## 8. Recommendations

1. Remove the infeasible branch at `api.py:72–73` and the unused
   `cutoff=None` default in `repository.list_overdue_candidates` after the
   code freeze. They add decisions that can never be tested.
2. Add unit tests for #5 (`allowed_actions` contains `feedback` after
   resolution) and #6 (stale reject). Both are quick and would raise branch
   coverage to 92.9 %.
3. Keep `fail_under = 90` in CI so coverage cannot silently fall.

## 9. Conclusion

Branch coverage is **91.8 %** (156 of 170), up from 85.9 %, and 93.4 %
of the feasible branches. Every decision that implements an SRS business
rule has all of its outcomes tested. The 14 untaken branches are defensive,
unused or infeasible paths, each assessed above.
