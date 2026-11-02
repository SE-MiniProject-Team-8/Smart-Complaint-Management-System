# Smart Complaint Management System (SCMS)

A university complaint portal built with **Python, Flask and SQLite**, following
the SRS and software architecture/design documents in this repository. Students
submit and track complaints; Faculty-in-Charge, the Grievance Committee and the
Dean handle them through the specified escalation hierarchy.

Flask serves both the browser interface and API. No separate frontend build,
Node server, MySQL/PostgreSQL installation, or external email service is needed.

## Prerequisites

- Git, Python **3.12**, and a modern browser. CI verifies Python 3.12.
- Internet access to install dependencies.
- Node.js **22** only for JavaScript and real-browser tests, not to run the app.

Choose **one** terminal setup below, then continue with **Initialize and run**.
Run commands from the repository root. If already cloned, open the existing
folder and run `git pull --ff-only` instead of cloning again.

## Windows PowerShell

```powershell
git clone https://github.com/SE-MiniProject-Team-8/Smart-Complaint-Management-System.git
cd Smart-Complaint-Management-System
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
$env:SCMS_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
$env:SCMS_INSECURE_COOKIES = "1"
```

If PowerShell blocks activation, activation is optional: use
`.\.venv\Scripts\python.exe` instead of `python` in the remaining commands.
If `py` is unavailable, use your installed Python 3.12 executable to create `.venv`.

## Windows Command Prompt

These commands are for **CMD**, not PowerShell:

```bat
git clone https://github.com/SE-MiniProject-Team-8/Smart-Complaint-Management-System.git
cd Smart-Complaint-Management-System
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
for /f %K in ('python -c "import secrets; print(secrets.token_hex(32))"') do set "SCMS_SECRET_KEY=%K"
set "SCMS_INSECURE_COOKIES=1"
```

Use `%%K` instead of `%K` if the key-generation command is saved in a `.bat` file.

## Linux or macOS

Use a Bash-compatible terminal with Python 3.12 installed:

```bash
git clone https://github.com/SE-MiniProject-Team-8/Smart-Complaint-Management-System.git
cd Smart-Complaint-Management-System
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
export SCMS_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export SCMS_INSECURE_COOKIES=1
```

If Linux reports that `venv` or `ensurepip` is missing, install the venv package
for your Python version through your distribution, then recreate `.venv`.

## Initialize and run

After your terminal setup above, run these commands in the **same terminal**.
They work in PowerShell, CMD and Bash:

```sh
python -m flask --app scms init-db
python -m flask --app scms create-staff --university-id FAC001 --name "Faculty Demo" --email faculty@example.edu --role Faculty
python -m flask --app scms create-staff --university-id GC001 --name "Committee Demo" --email committee@example.edu --role Committee
python -m flask --app scms create-staff --university-id DEAN01 --name "Dean Demo" --email dean@example.edu --role Dean --sla-review
python run.py
```

Each `create-staff` command prompts for a password and confirmation. Choose your
own passwords and remember them. There are **no built-in accounts or default
passwords**. Staff account creation is a one-time step: repeating an existing
ID/email returns a duplicate-account error, not a password reset.

Keep the terminal running and open **http://127.0.0.1:5000/**. Stop the server with
**Ctrl+C**. Opening the HTML file directly or viewing GitHub does not run Flask.

## Try the complete workflow

1. Select **Create student account**. Enter your university ID, name, email and
   password. You are signed in as a Student; public registration cannot choose
   a privileged role.
2. Submit a category, description and severity; keep the reference ID. Low and
   Medium go to Faculty, while High goes directly to Committee.
3. Sign out, then sign in as `FAC001` or `GC001` using your chosen password.
   Check the notification and open **View Details & Actions**.
4. Resolve with remarks, reject with a reason, or escalate. Faculty escalates to
   Committee, Committee to Dean; the Dean cannot escalate further.
5. Return as the student to see status and audit history. An eligible rejection
   permits **one appeal**. A Dean rejection can be appealed for final review at
   Dean level. Resolved complaints accept one rating and optional comment.
6. Sign in as `DEAN01` for **Overdue Review**. Checks are manual; the default SLA
   is seven days. New complaints are not immediately overdue. Only active
   overdue complaints below Dean level can be escalated.

## Restart or update

On later visits, open the repository, activate `.venv`, and set the environment
variables using your terminal's syntax above, then run:

```sh
python run.py
```

Environment variables apply to the current terminal and its child processes.
Keep the same signing secret for browser sessions that should survive a restart.
Generating a new secret signs out existing browsers but **does not delete**
accounts or complaints. A `.env` file is not loaded automatically.

To update, stop the server, preserve any local changes, then run these commands
with your environment variables already set:

```sh
git pull --ff-only
python -m pip install -r requirements.txt
python -m flask --app scms init-db
python run.py
```

`init-db` is safe to rerun and preserves records; startup also initializes missing
tables/indexes. Do not delete the database to update the application.

## Configuration and persistent data

| Variable | Meaning |
|---|---|
| `SCMS_SECRET_KEY` | Required signing secret; generate it outside source control. |
| `SCMS_INSECURE_COOKIES` | Set to `1` for local HTTP. Otherwise cookies require HTTPS. |
| `SCMS_DATABASE` | Optional SQLite path; default `instance/scms.db`, relative to the working directory. |

To choose another database, set the path **before** initialization, staff creation
and startup in the same terminal:

```powershell
# PowerShell
$env:SCMS_DATABASE = "C:\scms-data\scms.db"
```

```bat
REM CMD
set "SCMS_DATABASE=C:\scms-data\scms.db"
```

```bash
# Bash
export SCMS_DATABASE="$HOME/scms-data/scms.db"
```

SQLite ships with Python. This file holds users, sessions, complaints, assignments,
audit history, notifications, appeals and feedback. The trusted-operator setting
`settings.sla_threshold_days` controls the SLA; no threshold-editing UI is included.

An optional consistent backup can be created from the repository root:

```sh
python -c "import os, sqlite3; from pathlib import Path; Path('backups').mkdir(exist_ok=True); src=sqlite3.connect(os.environ.get('SCMS_DATABASE', 'instance/scms.db')); dst=sqlite3.connect('backups/scms-backup.db'); src.backup(dst); dst.close(); src.close()"
```

This overwrites that backup filename. Use dated filenames to keep multiple
versions. Keep backups private; copying only an active `.db` file can miss WAL
contents. Local databases, backups, `.venv` and browser test tools are gitignored.

## Run the tests

With Python dependencies installed, run from the repository root:

```sh
python -m unittest discover -s tests -v
python -m unittest test_scms -v
```

The first command tests the real Flask/SQLite app, including persistence, rollback,
authorization, immutable audit and workflows. The second tests the original
in-memory simulation. These tests supply their own secrets and disposable
databases; they do not use your app's complaints database or require its key.

With Node.js 22 installed:

```sh
node --check scms/static/app.js
node --test tests/browser_smoke.cjs
```

The controller smoke test uses DOM/API stand-ins. To run the **real Chromium UI
test**, install the development-only browser tools:

```sh
npm install --prefix .browser-tools playwright@1.64.1
```

Then run the commands for your terminal:

```powershell
# PowerShell
& .\.browser-tools\node_modules\.bin\playwright.cmd install chromium
$env:NODE_PATH = (Resolve-Path .\.browser-tools\node_modules).Path
python tests/run_product_browser.py
```

```bat
REM CMD
.browser-tools\node_modules\.bin\playwright.cmd install chromium
set "NODE_PATH=%CD%\.browser-tools\node_modules"
python tests/run_product_browser.py
```

```bash
# Linux Bash; --with-deps may request permission to install system packages
./.browser-tools/node_modules/.bin/playwright install --with-deps chromium
export NODE_PATH="$PWD/.browser-tools/node_modules"
python tests/run_product_browser.py
```

On macOS use `playwright install chromium` without `--with-deps`. The runner
starts its own local server on a free port, creates disposable staff and data,
runs the workflows, then removes its database. You do not need `run.py` running.
`NODE_PATH` tells Node where these test-only packages were installed.

GitHub Actions runs application and browser jobs on pushes and pull requests.
You can also select **Actions → Application checks → Run workflow** on GitHub.
CI uses Ubuntu, Python 3.12 and Node.js 22; Windows setup commands are not tested
by a Windows CI runner. See [product verification](docs/product-verification.md)
for results, reproduction and limits, and [Sprint 1 evidence](docs/sprint1/verification.md)
for earlier screenshots and workload details. Mini-project performance checks do
not establish production capacity or full accessibility compliance.

## Troubleshooting

| Symptom | What to check |
|---|---|
| `SCMS_SECRET_KEY must be set` | Set the key in the terminal starting Flask; new terminals need their environment configured. |
| `No module named flask` | Activate `.venv` or use its Python executable, then run `python -m pip install -r requirements.txt`. |
| Staff login fails | Create the account once in the same database; use the password entered at the prompt. No default password exists. |
| CSRF error or sign-in does not persist on local HTTP | Set `SCMS_INSECURE_COOKIES=1`, restart Flask and reload. Use one hostname consistently, such as `127.0.0.1`. |
| Complaint absent from a staff queue | Check its severity/current level and status filter. Historic access does not grant current handler actions. |
| No overdue complaints | New and terminal complaints are excluded from the active overdue list; the default threshold is seven days. |
| Port 5000 already in use | Stop the other server or run `python -m flask --app scms run --host 127.0.0.1 --port 5001`, then open port 5001. |
| `Cannot find module 'playwright'` | Install `.browser-tools` and set `NODE_PATH` as above in the terminal running the browser test. |
| Browser executable missing | Run your platform's Playwright browser-install command above. |

## Architecture and references

| Module | Component | Responsibility |
|---|---|---|
| `scms/api.py` | C02 | API routes, session/CSRF guards, error envelopes and request logging |
| `scms/auth.py` | C03 | Registration, hashing, atomic session rotation and access policy |
| `scms/complaints.py` | C04 | Submission, resolution, rejection, escalation and appeal transactions |
| `scms/routing.py` | C05 | Shared severity routing, level transitions and Dean ceiling |
| `scms/audit.py` | C06 | Append-only audit history and authorized reads |
| `scms/feedback.py` | C07 | Resolved-complaint feedback with identity-suppressed handler projection |
| `scms/queries.py` | C08 | Scoped dashboards, manual SLA checks and in-app notifications |
| `scms/repository.py`, `scms/db.py`, `scms/schema.sql` | C09 | SQL, connections, transactions, constraints and audit triggers |

Complaint mutations commit state and required audit/assignment/notification records
in one transaction. Failed writes roll back; success is reported after commit.
Permissions are enforced server-side, not just by hidden UI controls. API routes
are under `/api/v1`; `/healthz` is a minimal readiness check.

References: [SRS](SRS.docx), [architecture](Member3-Architecture/),
[software design](Member%204/), and [test plan](SCMS_Test_Plan_2.0.docx).

## Scope and deployment

`python run.py` is for local development and demonstrations. Shared deployment
needs a production WSGI server behind HTTPS, a stable secret, durable SQLite
storage outside the web root, and backups. Remove `SCMS_INSECURE_COOKIES=1`
when serving through HTTPS. External hosting and a production WSGI server are not
provisioned by this repository.

Login throttling and an SLA threshold administration screen remain future
extensions, not completed features. The implemented scope has no background SLA
scheduler, fifth public Admin role, SSO, or external email notifications.
