# Sprint demo videos

| Video | Runtime | Build shown | Script |
|---|---|---|---|
| [Sprint 1 demo](sprint1-demo.mp4) | 1:24 | `35e4919`, the Sprint 1 merge result | [sprint1-script.md](sprint1-script.md) |
| [Sprint 2 demo](sprint2-demo.mp4) | 2:58 | Final build | [sprint2-script.md](sprint2-script.md) |

## Common setup (run once per video, from the repository root)

Use a fresh demo database so no real data appears on screen. The commands
below are for Bash. For PowerShell, use `$env:NAME = "value"` instead of
`export NAME=value`.

```sh
python -m venv .venv && source .venv/bin/activate     # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
export SCMS_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export SCMS_INSECURE_COOKIES=1
export SCMS_DATABASE=instance/demo.db
rm -f instance/demo.db*
python -m flask --app scms init-db
python -m flask --app scms create-staff --university-id FAC001 --name "Faculty Demo" --email faculty@example.edu --role Faculty
python -m flask --app scms create-staff --university-id COM001 --name "Committee Demo" --email committee@example.edu --role Committee
python -m flask --app scms create-staff --university-id DEAN01 --name "Dean Demo" --email dean@example.edu --role Dean --sla-review
python run.py      # open http://127.0.0.1:5000
```

Each `create-staff` asks for a password. Use the same one for all three
accounts, for example `Demo@1234`.

### Making a complaint overdue for the SLA scene

A complaint becomes overdue only after 7 days in one status. For the demo,
age one complaint in the demo database (not a real one). Replace `1` with
the complaint ID shown on screen:

```sh
python -c "import os,sqlite3; c=sqlite3.connect(os.environ['SCMS_DATABASE']); c.execute(\"UPDATE complaints SET status_updated_at='2026-01-01T00:00:00Z' WHERE complaint_id=1\"); c.commit()"
```

Say on the recording that this complaint was aged for the demo.

## Recording tips

* Use a browser window at about 1280 × 800 and zoom to 110 % so the text is
  readable.
* Prepare the accounts and the complaints that are not the focus of a scene
  before recording. Show live only the action the scene is about.
* Keep the narration to what is on screen. Each script gives about 130 words
  per minute.
