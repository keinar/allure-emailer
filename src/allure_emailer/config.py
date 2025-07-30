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
    generated configuration file.  All values except ``recipients`` and
    ``port`` are strings.  The ``recipients`` attribute contains a
    list of email addresses split on commas.  The ``port`` attribute
    is converted to an integer.

    The ``sender`` field is optional.  If left empty or undefined, the
    SMTP ``user`` will be used as the effective sender address.  This
    behaviour simplifies configuration by inferring the "From" address
    from the authentication username, which is typical for many SMTP
    providers.  Call :py:meth:`effective_sender` to obtain the final
    address used when sending email.
    """

    host: str
    port: int
    user: str
    password: str
    recipients: List[str] = field(default_factory=list)
    json_path: str = "allure-report/widgets/summary.json"
    report_url: str = ""
    sender: str = ""

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
        # Load configuration from the .env file (if provided) and from
        # the process environment.  The values in the file take
        # precedence over the environment variables of the same name to
        # avoid collisions with system variables like ``USER``.
        file_vars: Dict[str, Optional[str]] = {}
        if env_file is not None:
            # dotenv_values reads key/value pairs from the file without
            # altering os.environ
            file_vars = dotenv_values(env_file)  # type: ignore[assignment]

        # Start with a copy of the current environment; values from the
        # file override these.
        env_map: Dict[str, Optional[str]] = {k.lower(): v for k, v in os.environ.items()}
        for k, v in file_vars.items():
            env_map[k.lower()] = v

        # Extract only the keys we care about
        keys = [
            "host",
            "port",
            "user",
            "password",
            "sender",
            "recipients",
            "json_path",
            "report_url",
        ]
        env_map = {k: env_map.get(k) for k in keys}

        # Apply CLI overrides if provided (these take highest precedence)
        if overrides:
            for key, value in overrides.items():
                if value is not None:
                    env_map[key] = value

        # Validate required fields.  ``sender`` is optional and will
        # default to the SMTP user if not provided.
        required_keys = ["host", "port", "user", "password", "recipients"]
        missing = [k for k in required_keys if not env_map.get(k)]
        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing).upper()}"
            )

        # Convert and normalise values
        port_value = env_map["port"]
        try:
            port_int = int(port_value) if port_value is not None else 0
        except ValueError:
            raise ValueError(f"Invalid port value: {port_value}")

        recipients_list = [addr.strip() for addr in env_map["recipients"].split(",") if addr.strip()]
        # Ensure the SMTP username is a full email address (contains '@')
        user_val = env_map["user"]
        if "@" not in (user_val or ""):
            raise ValueError(
                "SMTP USER must be a full email address (e.g. contact@example.com)"
            )

        return cls(
            host=env_map["host"],
            port=port_int,
            user=user_val,
            password=env_map["password"],
            recipients=recipients_list,
            json_path=env_map.get("json_path") or "allure-report/widgets/summary.json",
            report_url=env_map.get("report_url") or "",
            sender=env_map.get("sender") or "",
        )

    def effective_sender(self) -> str:
        """Return the email address used as the From header.

        If a ``sender`` was provided via configuration or overrides it
        takes precedence.  Otherwise, the SMTP ``user`` value is used.

        Returns
        -------
        str
            The address to use as the ``From`` header when sending
            email.
        """
        return self.sender or self.user


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