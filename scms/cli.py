"""Operator commands. Staff accounts are provisioned here, never through public registration.

    flask --app scms init-db
    flask --app scms create-staff --university-id FAC001 --name "Prof. Bob" \
          --email bob@univ.edu --role Faculty
    flask --app scms create-staff ... --role Dean --sla-review
"""
import click

from . import auth, db
from .errors import AppError


def register_cli(app):
    @app.cli.command("init-db")
    def init_db_command():
        """Create the database tables if they do not exist (safe to re-run)."""
        db.init_db(app.config["DATABASE"])
        click.echo(f"Database ready at {app.config['DATABASE']}")

    @app.cli.command("create-staff")
    @click.option("--university-id", required=True)
    @click.option("--name", required=True)
    @click.option("--email", required=True)
    @click.option("--role", type=click.Choice(auth.STAFF_ROLES), required=True)
    @click.option("--sla-review", is_flag=True, help="Grant the SLA_REVIEW permission (Dean/Admin).")
    @click.password_option()
    def create_staff_command(university_id, name, email, role, sla_review, password):
        """Provision a Faculty, Committee or Dean account."""
        conn = db.connect(app.config["DATABASE"])
        try:
            user = auth.create_staff(conn, university_id, name, email, password, role,
                                     sla_review, app.config["PASSWORD_HASH_METHOD"])
        except AppError as exc:
            raise click.ClickException(exc.message)
        finally:
            conn.close()
        click.echo(f"Created {user['role']} account {user['university_id']}.")
