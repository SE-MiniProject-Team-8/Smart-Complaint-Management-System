# Product integration verification

Verified on 2 November 2026 after merging PRs #16, #19, #20 and #21.
The application remains a Flask and SQLite modular monolith following the SRS
and the architecture and software design documents. No existing database is
used by the browser checks; test accounts and complaints are disposable.

## Results

- 76 real Flask/SQLite tests pass, including authorization, rollback, persistence,
  immutable audit, concurrency versions, dashboard paging and performance checks.
- 10 original simulation tests pass.
- The Node browser-controller smoke test and JavaScript syntax checks pass.
- Real headless Chromium completes the following workflows with no uncaught
  page JavaScript errors:

| Workflow | Result |
|---|---|
| Student registration and automatic login | Passed |
| Invalid submission and field-specific errors | Passed |
| Low submission, reference ID, tracking and escaped audit display | Passed |
| Faculty queue, in-app notice and resolution | Passed |
| Student feedback after resolution | Passed |
| Medium routing, rejection and appeal to Committee | Passed |
| Committee escalation, Dean resolution and escalation ceiling | Passed |
| High routing and appeal of Dean rejection for final review | Passed |
| Manual SLA review and authorized overdue escalation | Passed |
| 390-pixel mobile viewport without horizontal overflow | Passed after layout fix |
| Expired-session recovery clears private views | Passed |

The real browser check found a narrow-screen staff filter overflow. The fix
only permits the existing filter controls to shrink or wrap; it changes no
workflow, data model, or role policy.

## Reproduce

Run the Python tests and controller smoke test from the repository root:

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m unittest test_scms -v
node --check scms/static/app.js
node --test tests/browser_smoke.cjs
```

For real browser checks, install Node.js and the development-only browser tools.
The following commands use a POSIX shell; GitHub Actions runs the same test:

```sh
npm install --prefix /tmp/scms-browser-tests playwright@1.64.1
/tmp/scms-browser-tests/node_modules/.bin/playwright install --with-deps chromium
NODE_PATH=/tmp/scms-browser-tests/node_modules python tests/run_product_browser.py
```

The runner starts a local server on a free port, provisions test staff, runs the
browser, then stops the server and removes the temporary database. An optional
`SCMS_BROWSER_EXECUTABLE` selects an already-installed Chromium binary.

## Limits

These checks validate the listed functional paths in Chromium and automated
server-side tests. They do not establish compatibility with every browser,
production capacity, external hosting readiness, or a full accessibility audit.
The performance tests describe a mini-project workload, not a production load test.
