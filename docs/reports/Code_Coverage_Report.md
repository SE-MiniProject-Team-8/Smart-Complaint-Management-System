# Code Coverage Report

**Project:** Smart Complaint Management System (SCMS)
**Team:** SE-MiniProject-Team-8
**Report ID:** SCMS-CCR-1.0
**Date of measurement:** 15-11-2026
**Build measured:** `main` at `75d93e6` plus the test additions in this change

## 1. Purpose

This report states how much of the application source is executed by the
automated test suite (statement or line coverage), identifies the code that
is not executed, and explains whether each gap matters. Decision-level
coverage is reported separately in the
[Branch Coverage Report](Branch_Coverage_Report.md).

## 2. Tool and configuration

| Item | Value |
|---|---|
| Tool | coverage.py 7.17.3 (`requirements-dev.txt`) |
| Configuration | `.coveragerc`: `branch = True`, `source = scms`, `fail_under = 90` |
| Command | `python -m coverage run -m unittest discover -s tests -v`, then `python -m coverage report` |
| Measured code | Every module in the `scms/` package (13 files, 808 executable statements). Tests, `run.py` and `test_scms.py` are not measured |
| Suite | 96 tests in `tests/` (see the [Unit Testing Report](Unit_Testing_Report.md)) |
| Continuous integration | The `application` job in `.github/workflows/ci.yml` runs the same command on every push and pull request, writes the table to the job summary, uploads `htmlcov/` and `coverage.xml` as the `coverage-report` artifact, and **fails the build if combined coverage falls below 90 %** |

`test_scms.py` is excluded because it tests an in-file model rather than
the `scms` package. Including it would not change the numbers, because it
never imports `scms`.

## 3. Summary

| Measure | Before (76 tests) | After (96 tests) |
|---|---:|---:|
| Statements | 808 | 808 |
| Statements executed | 764 | **795** |
| Statements missed | 44 | **13** |
| **Statement coverage** | 94.6 % | **98.4 %** |
| Combined line + branch (coverage.py "Cover") | 93.0 % | **97.2 %** |

"Before" is the suite as merged on 2 November 2026. "After" includes
`tests/test_operations.py`, which was written to close the gaps this
measurement found (section 5).

## 4. Coverage by module

| Module | Component (SAD 3.3) | Statements | Missed before | Missed after | Statement coverage after |
|---|---|---:|---:|---:|---:|
| `scms/__init__.py` | App factory | 24 | 0 | 0 | 100.0 % |
| `scms/api.py` | C02 Web API | 176 | 6 | 2 | 98.9 % |
| `scms/audit.py` | C06 Audit | 11 | 0 | 0 | 100.0 % |
| `scms/auth.py` | C03 AuthService | 120 | 4 | 1 | 99.2 % |
| `scms/cli.py` | Operator CLI | 23 | **9** | 0 | 100.0 % |
| `scms/complaints.py` | C04 ComplaintService | 132 | 5 | 5 | 96.2 % |
| `scms/db.py` | C09 transactions | 51 | **8** | 0 | 100.0 % |
| `scms/errors.py` | Error contract | 17 | 0 | 0 | 100.0 % |
| `scms/feedback.py` | C07 Feedback | 32 | 2 | 2 | 93.8 % |
| `scms/queries.py` | C08 Queries / SLA | 60 | 4 | 2 | 96.7 % |
| `scms/repository.py` | C09 Repository | 72 | 3 | 1 | 98.6 % |
| `scms/routing.py` | C05 RoutingPolicy | 23 | 0 | 0 | 100.0 % |
| `scms/validation.py` | Input validation | 67 | 3 | 0 | 100.0 % |
| **Total** | | **808** | **44** | **13** | **98.4 %** |

Raw report: [`evidence/coverage-report.txt`](evidence/coverage-report.txt).
A browsable HTML report and `coverage.xml` (Cobertura format) are attached to every CI run as the `coverage-report` artifact.

## 5. Gaps found and closed

The first measurement showed two modules well below the rest:

* **`cli.py` at 61 %.** The `init-db` and `create-staff` commands were only
  run by hand. Staff accounts can only be created this way (there is no
  public route), so a broken command would block every deployment. It is
  now covered by `StaffProvisioningCliTests` (5 tests), including the
  duplicate-account error path.
* **`db.py` at 83 %.** The failure paths of `transaction()` (a failed
  `BEGIN`, a failed `COMMIT`, and a failed `ROLLBACK` after a failed
  `COMMIT`) were never executed. These paths are what guarantee NFR-REL-02,
  that the system never reports success unless the data was stored. They
  are now covered by `TransactionBoundaryTests` (7 tests) using a
  connection wrapper that injects the failures.

Smaller gaps in `api.py`, `auth.py`, `validation.py`, `repository.py` and
`queries.py` were closed by `BoundaryAndEdgeBranchTests` (8 tests). No
defects were found: every new test passed against the existing code.

## 6. Remaining uncovered statements (13)

| Location | Code | Why it is not covered | Risk |
|---|---|---|---|
| `api.py:45` | `return {}` when an optional body is empty | Only `POST /sla/check` accepts an empty body. The UI and tests always send `{}` | Low. The non-empty path is tested |
| `api.py:73` | 401 "session expired" for logout with no session | **Unreachable.** `logout` is not a public endpoint, so `current_actor()` on line 68 already raises 401 before this line. Defensive duplicate | None. Candidate for removal after the code freeze |
| `auth.py:145` | 401 when a session points to a deleted user | Users are never deleted by the application | Low |
| `complaints.py:48` | Adds `feedback` to a resolved complaint's allowed actions | Exercised by the browser test (workflow W5) but not by a unit test asserting `allowed_actions` | Low. Covered at system level |
| `complaints.py:147` | Stale-version error inside *reject* | The stale-version check is tested for resolve, appeal and SLA escalation; reject uses the same optimistic `update_complaint_state` call | Low |
| `complaints.py:184` | A handler (non-owner) tries to appeal | Handlers are never shown the appeal action, and the 404 path is tested for other actions | Low |
| `complaints.py:207-208` | Unique-constraint race on `appeals` | Needs two simultaneous appeals. The database constraint itself is tested (`AppealTests.test_database_enforces_one_appeal_even_if_service_check_is_bypassed`) | Low |
| `feedback.py:19` | A handler submits feedback on a complaint they can see | Tested for another *student*, not for a handler | Low |
| `feedback.py:45` | Reading feedback that does not exist | No test reads feedback before it is submitted | Low |
| `queries.py:95, 97` | SLA escalation on a missing or terminal complaint | The check endpoint excludes terminal complaints. Stale and permission paths are tested | Low |
| `repository.py:103` | Overdue query with no cutoff | Every caller passes a cutoff | None. Unused default |

None of the uncovered statements implements an SRS requirement that lacks
a passing test at unit or system level.

## 7. How to reproduce

```sh
python -m pip install -r requirements-dev.txt
python -m coverage run -m unittest discover -s tests -v
python -m coverage report          # table with missing lines
python -m coverage html            # browsable report in htmlcov/index.html
```

## 8. Conclusion

Statement coverage of the application is **98.4 %** (795 of 808), up from
94.6 %. Every module is at or above 93.8 %, and eight modules are at 100 %.
The remaining 13 statements are defensive or race-condition paths with low
risk, one of which is unreachable. Coverage is enforced in CI with a 90 %
minimum.
