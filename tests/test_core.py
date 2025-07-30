"""Unit tests for the core functionality of allure-emailer."""

import json
import os
from pathlib import Path

import pytest

from allure_emailer.config import Config
from allure_emailer.emailer import build_html_email, parse_summary


def test_parse_summary(tmp_path: Path) -> None:
    """The parse_summary function should return correct counts from JSON."""
    data = {
        "statistic": {
            "total": 10,
            "passed": 8,
            "failed": 1,
            "broken": 1,
            "skipped": 0,
        }
    }
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps(data))
    stats = parse_summary(summary_path)
    assert stats == {"total": 10, "passed": 8, "failed": 1, "broken": 1, "skipped": 0}


def test_build_html_email() -> None:
    """The HTML builder should include counts and link correctly."""
    stats = {"total": 5, "passed": 4, "failed": 1, "broken": 0, "skipped": 0}
    url = "http://example.com/report"
    html = build_html_email(stats, url)
    # Check that each count appears in the HTML
    for value in stats.values():
        assert str(value) in html
    # Check that the URL appears in a hyperlink
    assert f"href='{url}'" in html or f'href="{url}"' in html


def test_config_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Configuration should load from .env and apply overrides."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join([
            # use the AEMAILER_ prefix to avoid clobbering system variables
            "AEMAILER_HOST=smtp.test.com",
            "AEMAILER_PORT=2525",
            "AEMAILER_USER=ci@example.com",
            "AEMAILER_PASSWORD=secret",
            "AEMAILER_SENDER=ci@test.com",
            "AEMAILER_RECIPIENTS=dev1@test.com,dev2@test.com",
            "AEMAILER_JSON_PATH=report/summary.json",
            "AEMAILER_REPORT_URL=https://example.com/report",
        ])
    )
    # Ensure no conflicting variables are set in the current environment
    for var in [
        "AEMAILER_HOST",
        "AEMAILER_PORT",
        "AEMAILER_USER",
        "AEMAILER_PASSWORD",
        "AEMAILER_SENDER",
        "AEMAILER_RECIPIENTS",
        "AEMAILER_JSON_PATH",
        "AEMAILER_REPORT_URL",
        "AEMAILER_OAUTH_TOKEN",
        # Remove legacy names if present
        "HOST",
        "PORT",
        "USER",
        "PASSWORD",
        "SENDER",
        "RECIPIENTS",
        "JSON_PATH",
        "REPORT_URL",
        "OAUTH_TOKEN",
    ]:
        monkeypatch.delenv(var, raising=False)
    cfg = Config.from_env(env_file)
    assert cfg.host == "smtp.test.com"
    assert cfg.port == 2525
    assert cfg.user == "ci@example.com"
    assert cfg.password == "secret"
    assert cfg.sender == "ci@test.com"
    assert cfg.recipients == ["dev1@test.com", "dev2@test.com"]
    assert cfg.json_path == "report/summary.json"
    assert cfg.report_url == "https://example.com/report"
    # Apply overrides
    overrides = {"host": "smtp.override", "port": "587", "recipients": "user@acme.com"}
    cfg2 = Config.from_env(env_file, overrides=overrides)
    assert cfg2.host == "smtp.override"
    assert cfg2.port == 587
    assert cfg2.recipients == ["user@acme.com"]


def test_effective_sender_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When no SENDER is provided the effective sender should fall back to the USER."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join([
            "AEMAILER_HOST=smtp.test.com",
            "AEMAILER_PORT=2525",
            "AEMAILER_USER=ci@example.com",
            "AEMAILER_PASSWORD=secret",
            "AEMAILER_RECIPIENTS=dev@example.com",
        ])
    )
    for var in [
        "AEMAILER_HOST",
        "AEMAILER_PORT",
        "AEMAILER_USER",
        "AEMAILER_PASSWORD",
        "AEMAILER_RECIPIENTS",
        "AEMAILER_SENDER",
        "AEMAILER_JSON_PATH",
        "AEMAILER_REPORT_URL",
        "AEMAILER_OAUTH_TOKEN",
        # legacy names
        "HOST",
        "PORT",
        "USER",
        "PASSWORD",
        "RECIPIENTS",
        "SENDER",
        "JSON_PATH",
        "REPORT_URL",
        "OAUTH_TOKEN",
    ]:
        monkeypatch.delenv(var, raising=False)
    cfg = Config.from_env(env_file)
    assert cfg.sender == ""
    # effective_sender should use the USER when sender is missing
    assert cfg.effective_sender() == "ci@example.com"