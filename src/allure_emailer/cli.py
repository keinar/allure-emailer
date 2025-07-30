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
from typing import Optional, List, Dict

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
        help="Directory in which to write the configuration file",
        show_default=True,
    )
):
    """Interactively generate a configuration file for allure‑emailer.

    This command prompts you for the information needed to send
    Allure summaries by email.  It supports three authentication
    methods:

    * **smtp** – traditional SMTP using a username (full email
      address) and password.
    * **smtp-oauth2** – SMTP using XOAUTH2 with a bearer access
      token instead of a password.
    * **graph** – Microsoft Graph API using client credentials
      (tenant ID, client ID, client secret) and a sender address.

    Based on your choice, the command will ask the appropriate
    questions and write the collected values into a configuration
    file.  If a `.env` file already exists in the specified
    directory it will **not** be overwritten—instead a
    `.env.emailer` file will be created.  Existing lines in `.env`
    remain untouched.  The variables written to the configuration
    file are prefixed with ``AEMAILER_`` (for example,
    ``AEMAILER_HOST`` or ``AEMAILER_TENANT_ID``) to avoid clashing
    with existing environment variables.  When specifying an SMTP
    port, keep in mind that port ``465`` uses implicit TLS (SSL) and
    port ``587`` uses STARTTLS.  Custom fields may be added later by
    defining variables that start with ``AEMAILER_FIELD_`` in your
    `.env` or `.env.emailer` file.
    """
    typer.echo("Initializing configuration for allure-emailer...")
    # Ask the user which authentication method to configure.  Valid
    # options are smtp, smtp-oauth2 and graph.  Default to smtp.
    # Use Click's Choice type so that the user sees the valid options and
    # cannot enter an unexpected value.  Choices are case-insensitive.
    import click  # type: ignore
    method_choice = typer.prompt(
        "Select authentication method",
        type=click.Choice(["smtp", "smtp-oauth2", "graph"], case_sensitive=False),
        default="smtp",
        show_default=True,
    )
    method = method_choice.lower()

    config_values: Dict[str, str] = {}
    if method == "smtp":
        smtp_host = typer.prompt("SMTP host (e.g. smtp.example.com)")
        smtp_port = typer.prompt("SMTP port", type=int, default=587)
        smtp_user = typer.prompt("SMTP username (full email address)")
        smtp_password = typer.prompt(
            "SMTP password", hide_input=True, confirmation_prompt=False
        )
        config_values.update(
            {
                "host": smtp_host,
                "port": str(smtp_port),
                "user": smtp_user,
                "password": smtp_password,
            }
        )
    elif method == "smtp-oauth2":
        smtp_host = typer.prompt("SMTP host (e.g. smtp.example.com)")
        smtp_port = typer.prompt("SMTP port", type=int, default=587)
        smtp_user = typer.prompt("SMTP username (full email address)")
        oauth_token = typer.prompt(
            "OAuth2 access token", hide_input=True, confirmation_prompt=False
        )
        config_values.update(
            {
                "host": smtp_host,
                "port": str(smtp_port),
                "user": smtp_user,
                "oauth_token": oauth_token,
            }
        )
    else:  # graph
        tenant_id = typer.prompt("Azure tenant ID")
        client_id = typer.prompt("Azure client ID")
        client_secret = typer.prompt(
            "Azure client secret", hide_input=True, confirmation_prompt=False
        )
        # The from address is the email address used to send via Graph.  It
        # often corresponds to the service account.  Ask for it but allow
        # empty to fall back to the user address.
        from_address = typer.prompt(
            "Sender email address (From)", default="", show_default=False
        )
        config_values.update(
            {
                "tenant_id": tenant_id,
                "client_id": client_id,
                "client_secret": client_secret,
            }
        )
        if from_address:
            config_values["from_address"] = from_address

    # Prompt for settings common to all methods
    recipients = typer.prompt(
        "Recipient email address(es) (comma separated)",
        prompt_suffix=" : ",
    )
    json_path = typer.prompt(
        "Path to Allure summary JSON",
        default=DEFAULT_SUMMARY_PATH,
        show_default=True,
    )
    report_url = typer.prompt(
        "Public URL to the full Allure report (leave blank if none)",
        default="",
        show_default=False,
    )
    config_values.update(
        {
            "recipients": recipients,
            "json_path": json_path,
            "report_url": report_url,
        }
    )

    env_dir = Path(directory).expanduser().resolve()
    env_path = env_dir / ".env"
    alt_path = env_dir / ".env.emailer"
    # Determine destination: if .env exists and is not empty, write to .env.emailer
    dest: Path
    if env_path.exists() and env_path.stat().st_size > 0:
        dest = alt_path
        if dest.exists():
            typer.echo(
                f"Both {env_path.name} and {dest.name} exist; appending configuration to {dest.name}"
            )
        else:
            typer.echo(
                f"Existing {env_path.name} detected; creating {dest.name} for allure-emailer configuration"
            )
    else:
        dest = env_path

    save_env_file(dest, config_values)
    typer.echo(f"Configuration written to {dest}")


@app.command()
def send(
    env_file: Optional[str] = typer.Option(
        None,
        "--env-file",
        help=(
            "Path to the configuration file (.env or .env.emailer). "
            "If omitted, `.env.emailer` will be used if present, otherwise `.env`."
        ),
        show_default=False,
    ),
    host: Optional[str] = typer.Option(None, help="Override SMTP host"),
    port: Optional[int] = typer.Option(None, help="Override SMTP port"),
    user: Optional[str] = typer.Option(None, help="Override SMTP username"),
    password: Optional[str] = typer.Option(None, help="Override SMTP password"),
    sender: Optional[str] = typer.Option(
        None,
        help="Override sender email address. Defaults to the SMTP username if omitted.",
    ),
    recipients: Optional[str] = typer.Option(
        None, help="Override recipient email addresses (comma separated)"
    ),
    json_path: Optional[str] = typer.Option(
        None, help="Override path to the Allure summary JSON file"
    ),
    report_url: Optional[str] = typer.Option(
        None, help="Override public URL to the full Allure report"
    ),
    oauth_token: Optional[str] = typer.Option(
        None,
        help=(
            "Override OAuth2 access token for XOAUTH2 authentication.  "
            "When provided, the token will be used instead of the SMTP password to "
            "authenticate with the server.  You must also set the SMTP username "
            "to the full email address."
        ),
    ),
    subject: str = typer.Option(
        "Allure Test Summary",
        help=(
            "Subject line for the email.  You may use environment"
            " variable placeholders such as $CI_PIPELINE_ID which will be"
            " expanded at runtime."
        ),
        show_default=True,
    ),
    field: List[str] = typer.Option(
        None,
        "--field",
        help=(
            "Custom key=value pairs to include in the email body.  May be"
            " specified multiple times.  Values defined in the configuration"
            " file using the AEMAILER_FIELD_ prefix (or the legacy FIELD_"
            " prefix) will also be included."
        ),
    ),
    tenant_id: Optional[str] = typer.Option(
        None,
        help=(
            "Override Microsoft tenant ID for Graph API authentication.  "
            "When provided together with client ID and client secret, the email will "
            "be sent via the Microsoft Graph API instead of SMTP."
        ),
    ),
    client_id: Optional[str] = typer.Option(
        None,
        help="Override Microsoft client ID for Graph API authentication",
    ),
    client_secret: Optional[str] = typer.Option(
        None,
        help="Override Microsoft client secret for Graph API authentication",
    ),
    from_address: Optional[str] = typer.Option(
        None,
        help=(
            "Override the sender email address when using the Microsoft Graph API. "
            "Defaults to the SMTP username if omitted."
        ),
    ),
):
    """Send an email summarising an Allure test run.

    This command reads configuration from a file and environment
    variables, applies any overrides provided on the command line,
    parses the Allure summary JSON, constructs an HTML email and
    delivers it via SMTP.  When ``--env-file`` is not provided, the
    command automatically chooses between `.env.emailer` (if it
    exists) and `.env`.  A warning is printed if both files are
    present, indicating which one will be used.  The SMTP username
    must be a full email address and will be used as the default
    sender (``From``) address.  Connections on port ``465`` are made
    using SSL; all other ports (e.g. ``587``) use STARTTLS.  You can
    override the subject line with ``--subject`` and insert
    additional custom fields into the body using ``--field KEY=VALUE``
    or by defining ``AEMAILER_FIELD_<KEY>=VALUE`` entries in your
    configuration file.  (Legacy ``FIELD_<KEY>`` entries are still
    recognised for backward compatibility.)  If you wish to use
    OAuth 2.0 for authentication (for example, with Gmail or Office 365),
    you can supply an access token via the ``AEMAILER_OAUTH_TOKEN``
    variable in your configuration file or via the ``--oauth-token``
    option when sending.  When an OAuth token is provided the password
    is not used.
    
    You can also send email via the Microsoft Graph API by providing a
    tenant ID, client ID and client secret.  When these values (and
    optionally ``from_address``) are available in the configuration or
    provided via command‑line options, the tool will authenticate
    against Microsoft and send the message using Graph instead of SMTP.
    """
    # Determine which env file to load if not explicitly provided
    selected_env = env_file
    if env_file is None:
        default_env = Path(".env")
        emailer_env = Path(".env.emailer")
        if emailer_env.exists() and default_env.exists():
            typer.echo(
                f"Both {emailer_env.name} and {default_env.name} exist; using {emailer_env.name}"
            )
            selected_env = str(emailer_env)
        elif emailer_env.exists():
            selected_env = str(emailer_env)
        else:
            selected_env = str(default_env)

    overrides = {
        "host": host,
        "port": str(port) if port is not None else None,
        "user": user,
        "password": password,
        # The `sender` override may be provided to override the inferred
        # address; it is stored under the key 'sender'.
        "sender": sender,
        "recipients": recipients,
        "json_path": json_path,
        "report_url": report_url,
        # Support overriding the OAuth token on the CLI
        "oauth_token": oauth_token,
        # Graph API overrides
        "tenant_id": tenant_id,
        "client_id": client_id,
        "client_secret": client_secret,
        "from_address": from_address,
    }
    # Load configuration, merging overrides
    config = Config.from_env(selected_env, overrides=overrides)
    # Parse summary JSON (prefer CLI override if provided)
    summary_stats = parse_summary(json_path or config.json_path)
    # Collect custom fields from the configuration file and CLI.  We
    # support both the new ``AEMAILER_FIELD_`` prefix and the legacy
    # ``FIELD_`` prefix.  Values defined under the new prefix take
    # precedence over legacy entries if the same key appears twice.
    custom_fields: Dict[str, str] = {}
    if selected_env:
        # parse file vars using dotenv_values
        from dotenv import dotenv_values  # imported lazily to avoid overhead

        try:
            file_vars = dotenv_values(selected_env)  # type: ignore[assignment]
        except Exception:
            file_vars = {}
        # Normalise keys for comparison
        for k, v in file_vars.items():
            if not isinstance(k, str):
                continue
            key_upper = k.upper()
            # New prefix: AEMAILER_FIELD_ followed by the field name
            if key_upper.startswith("AEMAILER_FIELD_"):
                key_name = k[len("AEMAILER_FIELD_"):]
                custom_fields[key_name] = str(v) if v is not None else ""
        # Process legacy FIELD_ only if a corresponding AEMAILER_FIELD_ was
        # not already set
        for k, v in file_vars.items():
            if not isinstance(k, str):
                continue
            key_upper = k.upper()
            if key_upper.startswith("FIELD_"):
                key_name = k[len("FIELD_"):]
                if key_name not in custom_fields:
                    custom_fields[key_name] = str(v) if v is not None else ""
    # Parse CLI-provided fields.  CLI values override file values.
    if field:
        for item in field:
            if "=" not in item:
                raise typer.BadParameter(
                    f"Invalid field format '{item}'. Expected KEY=VALUE."
                )
            key, value = item.split("=", 1)
            custom_fields[key] = value
    # Expand environment variables in subject string
    from string import Template
    from dotenv import dotenv_values
    import os

    mapping = dict(os.environ)
    # incorporate variables from env file for subject substitution
    if selected_env:
        try:
            file_vars_for_subj = dotenv_values(selected_env)  # type: ignore[assignment]
            mapping.update(file_vars_for_subj)  # type: ignore[arg-type]
        except Exception:
            pass
    expanded_subject = Template(subject).safe_substitute(mapping)
    # Build email body with custom fields
    html_body = build_html_email(
        summary_stats,
        report_url or config.report_url,
        custom_fields=custom_fields if custom_fields else None,
    )
    # Send email
    send_email(config, html_body, subject=expanded_subject)
    typer.echo("Summary email sent successfully.")