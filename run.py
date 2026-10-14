"""Local development entry point.

    export SCMS_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
    export SCMS_INSECURE_COOKIES=1      # plain-HTTP local dev only
    python run.py

For shared deployment use a WSGI server (e.g. `waitress-serve --call run:create_app`)
behind HTTPS; do not use the Flask development server.
"""
from scms import create_app

if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
