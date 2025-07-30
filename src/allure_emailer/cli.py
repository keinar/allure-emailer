"""Command‑line interface for allure-emailer.

The CLI is built with Typer and exposes two top‑level subcommands:
``init`` and ``send``.

* ``init``: prompts the user for SMTP and email settings and writes
  them to a ``.env`` file.
* ``send``: reads the configuration, parses the Allure summary JSON,
  builds an HTML email and sends it.
"""

from __future__ import annotations

import typer
from pathlib import Path
from typing import Optional

from .config import Config, save_env_file
from .emailer import build_html_email, parse_summary, send_email


# Create the Typer application
app = typer.Typer(help="Send Allure test run summaries via email")

# Default path to the Allure summary JSON relative to the project root
DEFAULT_SUMMARY_PATH = "allure-report/widgets/summary.json"


@app.command()
def init(
    directory: str = typer.Option(
        ".",
        help="Directory in which to write the .env file",
        show_default=True,
    )
):
    """Interactively generate a .env configuration file.

    This command prompts for SMTP host, port, user, password, sender
    and recipient addresses, the path to the Allure summary JSON and
    the URL to the full report.  It writes the collected values into
    ``.env`` under the specified directory.
    """
    typer.echo("Initializing configuration for allure-emailer...")
    smtp_host = typer.prompt("SMTP host (e.g. smtp.example.com)")
    smtp_port = typer.prompt("SMTP port", type=int, default=587)
    smtp_user = typer.prompt("SMTP username")
    smtp_password = typer.prompt("SMTP password", hide_input=True, confirmation_prompt=False)
    sender = typer.prompt("Sender email address")
    recipients = typer.prompt(
        "Recipient email address(es) (comma separated)",
        prompt_suffix=" : ",
    )
    json_path = typer.prompt(
        "Path to Allure summary JSON", default=DEFAULT_SUMMARY_PATH, show_default=True
    )
    report_url = typer.prompt(
        "Public URL to the full Allure report (leave blank if none)", default="", show_default=False
    )

    config_values = {
        "host": smtp_host,
        "port": str(smtp_port),
        "user": smtp_user,
        "password": smtp_password,
        "sender": sender,
        "recipients": recipients,
        "json_path": json_path,
        "report_url": report_url,
    }

    env_dir = Path(directory).expanduser().resolve()
    env_path = env_dir / ".env"
    save_env_file(env_path, config_values)
    typer.echo(f"Configuration written to {env_path}")


@app.command()
def send(
    env_file: str = typer.Option(
        ".env", "--env-file", help="Path to the .env configuration file", show_default=True
    ),
    host: Optional[str] = typer.Option(None, help="Override SMTP host"),
    port: Optional[int] = typer.Option(None, help="Override SMTP port"),
    user: Optional[str] = typer.Option(None, help="Override SMTP username"),
    password: Optional[str] = typer.Option(None, help="Override SMTP password"),
    sender: Optional[str] = typer.Option(None, help="Override sender email address"),
    recipients: Optional[str] = typer.Option(
        None, help="Override recipient email addresses (comma separated)"
    ),
    json_path: Optional[str] = typer.Option(
        None, help="Override path to the Allure summary JSON file"
    ),
    report_url: Optional[str] = typer.Option(
        None, help="Override public URL to the full Allure report"
    ),
    subject: str = typer.Option(
        "Allure Test Summary", help="Subject line for the email", show_default=True
    ),
):
    """Send an email summarising an Allure test run.

    This command reads configuration from the specified ``env_file``,
    applies any overrides provided on the command line, parses the
    Allure summary JSON, constructs an HTML email and delivers it via
    SMTP.  The subject line can also be overridden.
    """
    overrides = {
        "host": host,
        "port": str(port) if port is not None else None,
        "user": user,
        "password": password,
        "sender": sender,
        "recipients": recipients,
        "json_path": json_path,
        "report_url": report_url,
    }
    # Load configuration, merging overrides
    config = Config.from_env(env_file, overrides=overrides)
    # Parse summary JSON
    summary_stats = parse_summary(json_path or config.json_path)
    # Build email body
    html_body = build_html_email(summary_stats, report_url or config.report_url)
    # Send email
    send_email(config, html_body, subject=subject)
    typer.echo("Summary email sent successfully.")