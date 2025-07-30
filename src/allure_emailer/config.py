"""Configuration handling for the allure-emailer CLI.

This module encapsulates loading configuration from a ``.env`` file
and from process environment variables.  It exposes a ``Config``
dataclass and helper functions to load configuration, optionally
overriding values from command-line options.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from dotenv import dotenv_values, load_dotenv


@dataclass
class Config:
    """Runtime configuration for allure-emailer.

    Attributes correspond to environment variables defined in the
    generated ``.env`` file.  All values except ``recipients`` and
    ``port`` are strings.  The ``recipients`` attribute contains a
    list of email addresses split on commas.  The ``port`` attribute
    is converted to an integer.
    """

    host: str
    port: int
    user: str
    password: str
    sender: str
    recipients: List[str] = field(default_factory=list)
    json_path: str = "allure-report/widgets/summary.json"
    report_url: str = ""

    @classmethod
    def from_env(
        cls,
        env_file: Path | str | None = None,
        overrides: Optional[Dict[str, Optional[str]]] = None,
    ) -> "Config":
        """Load configuration from a .env file and process environment.

        This method first loads the given ``env_file`` (if provided)
        into the process environment using :func:`dotenv.load_dotenv`.
        It then reads configuration keys from the environment and
        applies any overrides passed via the ``overrides`` dictionary.
        Environment variable names are expected to be uppercase
        versions of the field names: ``HOST``, ``PORT``, ``USER``,
        ``PASSWORD``, ``SENDER``, ``RECIPIENTS``, ``JSON_PATH``, and
        ``REPORT_URL``.

        Parameters
        ----------
        env_file: Path | str | None
            Path to the ``.env`` file.  If ``None`` the current
            environment is used without loading a file.
        overrides: dict or None
            Mapping of configuration field names to override values.

        Returns
        -------
        Config
            An instantiated configuration object.
        """
        # Load from file into environment without overriding existing
        # environment variables.  This ensures explicit environment
        # variables (e.g. secrets injected by CI) take precedence over
        # values in the file.
        if env_file is not None:
            load_dotenv(env_file, override=False)

        env_map: Dict[str, Optional[str]] = {}
        for field_name in [
            "host",
            "port",
            "user",
            "password",
            "sender",
            "recipients",
            "json_path",
            "report_url",
        ]:
            env_key = field_name.upper()
            env_map[field_name] = os.getenv(env_key)

        # Apply overrides (command-line flags) if provided
        if overrides:
            for key, value in overrides.items():
                if value is not None:
                    env_map[key] = value

        # Validate required fields
        missing = [k for k in ["host", "port", "user", "password", "sender", "recipients"] if not env_map.get(k)]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing).upper()}")

        # Convert and normalise values
        port_value = env_map["port"]
        port_int: int
        try:
            port_int = int(port_value) if port_value is not None else 0
        except ValueError:
            raise ValueError(f"Invalid port value: {port_value}")

        recipients_list = [addr.strip() for addr in env_map["recipients"].split(",") if addr.strip()]
        return cls(
            host=env_map["host"],
            port=port_int,
            user=env_map["user"],
            password=env_map["password"],
            sender=env_map["sender"],
            recipients=recipients_list,
            json_path=env_map.get("json_path") or "allure-report/widgets/summary.json",
            report_url=env_map.get("report_url") or "",
        )


def save_env_file(path: Path, config_dict: Dict[str, str]) -> None:
    """Write a set of configuration values to a .env file.

    The values in ``config_dict`` should be plain strings.  Keys are
    uppercased when written so that they can be read back by
    :func:`python-dotenv.load_dotenv` and :func:`Config.from_env`.

    Parameters
    ----------
    path: Path
        Path to the file that should be created or overwritten.
    config_dict: dict
        Mapping of field names (lowercase) to string values to
        persist.
    """
    lines = []
    for key, value in config_dict.items():
        lines.append(f"{key.upper()}={value}\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines))