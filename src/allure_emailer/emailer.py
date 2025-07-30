"""Core functionality for reading Allure summaries and sending emails."""

from __future__ import annotations

import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from .config import Config

try:
    # ``requests`` is used for OAuth2 token acquisition and sending
    # messages via the Microsoft Graph API.  It is declared as a
    # dependency in pyproject.toml.
    import requests  # type: ignore
except ImportError:
    requests = None  # will raise later if Graph API is used


def parse_summary(path: Path | str) -> Dict[str, int]:
    """Parse an Allure summary JSON file and return statistic counts.

    The Allure report writes a JSON file called ``summary.json`` under
    ``widgets/`` containing various metadata about the run.  This
    function loads the file and returns a dictionary with keys
    ``total``, ``passed``, ``failed``, ``broken`` and ``skipped``.  If
    any field is missing it defaults to ``0``.

    Parameters
    ----------
    path: Path or str
        Path to the JSON file.

    Returns
    -------
    dict
        Mapping of test outcome names to integer counts.
    """
    summary_path = Path(path)
    if not summary_path.is_file():
        raise FileNotFoundError(f"Allure summary JSON not found: {summary_path}")
    data = json.loads(summary_path.read_text())
    stats = data.get("statistic", {})
    return {
        "total": int(stats.get("total", 0)),
        "passed": int(stats.get("passed", 0)),
        "failed": int(stats.get("failed", 0)),
        "broken": int(stats.get("broken", 0)),
        "skipped": int(stats.get("skipped", 0)),
    }


def build_html_email(
    stats: Dict[str, int],
    report_url: str,
    custom_fields: Optional[Dict[str, str]] = None,
) -> str:
    """Construct an HTML email body summarising test results.

    The returned HTML includes a heading, a simple borderless table of
    counts, an optional section for custom key–value fields and a
    hyperlink to the full Allure report.  It can be used as the
    content of a ``text/html`` MIME part.

    Parameters
    ----------
    stats: dict
        Dictionary containing counts for ``total``, ``passed``,
        ``failed``, ``broken`` and ``skipped`` tests.
    report_url: str
        URL to the full Allure report.  If empty, the line with the
        hyperlink is omitted.
    custom_fields: dict, optional
        Additional key–value pairs to display below the summary table.
        The keys should be strings and the values will be converted
        to strings.  If ``None`` or empty no custom section is
        included.

    Returns
    -------
    str
        A string of HTML ready to be sent in an email.
    """
    table_rows = (
        f"<tr><td><strong>Total</strong></td><td>{stats['total']}</td></tr>"
        f"<tr><td><strong>Passed</strong></td><td style='color: #28a745;'>{stats['passed']}</td></tr>"
        f"<tr><td><strong>Failed</strong></td><td style='color: #dc3545;'>{stats['failed']}</td></tr>"
        f"<tr><td><strong>Broken</strong></td><td style='color: #ffc107;'>{stats['broken']}</td></tr>"
        f"<tr><td><strong>Skipped</strong></td><td style='color: #6c757d;'>{stats['skipped']}</td></tr>"
    )
    link_html = (
        f"<p>You can view the full report <a href='{report_url}'>here</a>.</p>"
        if report_url
        else ""
    )
    custom_html = ""
    if custom_fields:
        # Build a small table or list for custom fields
        rows = "".join(
            f"<tr><td><strong>{key}</strong></td><td>{value}</td></tr>"
            for key, value in custom_fields.items()
        )
        custom_html = f"<h3>Additional Information</h3><table border='0' cellpadding='6' cellspacing='0'>{rows}</table>"
    html = f"""
<html>
  <body style="font-family: Arial, sans-serif;">
    <h2>Allure Test Report Summary</h2>
    <table border="0" cellpadding="6" cellspacing="0">
      {table_rows}
    </table>
    {custom_html}
    {link_html}
  </body>
</html>
"""
    return html


def send_email(config: Config, html: str, subject: str = "Allure Test Summary") -> None:
    """Send an HTML email with the given subject and content.

    This function creates a ``MIMEMultipart`` message with only an
    HTML part (no plain text) and sends it via the SMTP server defined
    in the provided configuration.  When connecting on port ``465`` it
    uses :class:`smtplib.SMTP_SSL` (implicit TLS) and otherwise
    performs an explicit TLS upgrade using ``starttls()`` (commonly
    used with port ``587``).  The sender (``From``) address defaults
    to the SMTP ``user`` unless a specific sender was provided via
    configuration or command‑line override.

    Parameters
    ----------
    config: Config
        Loaded configuration specifying SMTP and email parameters.
    html: str
        HTML content to send.
    subject: str, optional
        The subject line for the email.  Defaults to
        ``"Allure Test Summary"``.
    """
    # Determine if we should send via Microsoft Graph API or SMTP.  If
    # Microsoft Graph credentials are provided (tenant_id, client_id,
    # client_secret) we send via Graph API.  Otherwise we use SMTP.
    use_graph = all([
        getattr(config, "tenant_id", None),
        getattr(config, "client_id", None),
        getattr(config, "client_secret", None),
    ])

    # Use config.from_address if provided, otherwise default to the SMTP user
    from_addr = config.from_address or config.user

    if use_graph:
        if requests is None:
            raise RuntimeError(
                "The 'requests' library is required for sending mail via the Microsoft Graph API"
            )
        # Acquire an access token from Microsoft Identity Platform
        token_url = (
            f"https://login.microsoftonline.com/{config.tenant_id}/oauth2/v2.0/token"
        )
        token_data = {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        token_headers = {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            token_resp = requests.post(
                token_url, data=token_data, headers=token_headers, timeout=30
            )
            token_resp.raise_for_status()
            token_json = token_resp.json()
            access_token = token_json.get("access_token")
            if not access_token:
                raise RuntimeError("Failed to obtain OAuth2 access token from Microsoft")
        except Exception as e:
            raise RuntimeError(f"OAuth2 token acquisition failed: {e}") from e

        # Build Graph API email message
        email_message = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": html,
                },
                "toRecipients": [
                    {"emailAddress": {"address": r}} for r in config.recipients
                ],
            }
        }
        graph_url = f"https://graph.microsoft.com/v1.0/users/{from_addr}/sendMail"
        graph_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(
                graph_url, json=email_message, headers=graph_headers, timeout=30
            )
            resp.raise_for_status()
        except Exception as e:
            # Attempt to extract error message from response if available
            error_detail = str(e)
            try:
                err_json = resp.json()
                error_detail = err_json.get("error", {}).get("message", error_detail)
            except Exception:
                pass
            raise RuntimeError(f"Failed to send email via Microsoft Graph API: {error_detail}") from e
        return  # Successfully sent via Graph API

    # Fallback to SMTP if Graph is not used
    # Create message container
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = config.effective_sender()
    message["To"] = ", ".join(config.recipients)
    message.attach(MIMEText(html, "html"))
    # Determine whether to use SSL implicitly or to start TLS after connecting.
    use_ssl = config.port == 465
    # Choose appropriate SMTP class
    SMTPClass = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with SMTPClass(config.host, config.port) as server:
        # For explicit TLS, upgrade the connection before authenticating
        if not use_ssl:
            server.starttls()
        # If an OAuth2 token is provided, authenticate using XOAUTH2
        if getattr(config, "oauth_token", None):
            import base64
            # Compose the SASL XOAUTH2 initial client response.  Use \x01
            # (Control+A) as field separators as required by the protocol.
            auth_string = f"user={config.user}\x01auth=Bearer {config.oauth_token}\x01\x01"
            b64_auth = base64.b64encode(auth_string.encode("ascii")).decode("ascii")
            # Issue the AUTH XOAUTH2 command
            server.ehlo()
            code, response = server.docmd("AUTH", "XOAUTH2 " + b64_auth)
            # Check for success (2xx code).  Gmail returns 235 on success.
            if code // 100 != 2:
                raise smtplib.SMTPAuthenticationError(code, response)
        else:
            # Password-based authentication
            server.login(config.user, config.password)
        # Send the email
        server.sendmail(
            config.effective_sender(), config.recipients, message.as_string()
        )