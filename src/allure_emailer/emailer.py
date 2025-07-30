"""Core functionality for reading Allure summaries and sending emails."""

from __future__ import annotations

import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from .config import Config


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
    # Create message container
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = config.effective_sender()
    message["To"] = ", ".join(config.recipients)
    message.attach(MIMEText(html, "html"))
    # Connect using SSL or STARTTLS depending on port
    if config.port == 465:
        # Implicit TLS (SSL) connection
        with smtplib.SMTP_SSL(config.host, config.port) as server:
            server.login(config.user, config.password)
            server.sendmail(
                config.effective_sender(), config.recipients, message.as_string()
            )
    else:
        # Explicit TLS via STARTTLS (default for port 587)
        with smtplib.SMTP(config.host, config.port) as server:
            server.starttls()
            server.login(config.user, config.password)
            server.sendmail(
                config.effective_sender(), config.recipients, message.as_string()
            )