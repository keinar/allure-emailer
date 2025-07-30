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
    # Optional OAuth2 access token for XOAUTH2 authentication.  When
    # provided, this token will be used instead of the password to
    # authenticate with the SMTP server via the XOAUTH2 mechanism.
    # The value should be a raw access token (not base64‑encoded).  If
    # ``oauth_token`` is ``None`` or empty, password‑based
    # authentication is used.
    oauth_token: Optional[str] = None

    # Optional Microsoft Graph API credentials.  When all four of
    # ``tenant_id``, ``client_id``, ``client_secret`` and
    # ``from_address`` are provided, the email will be sent via the
    # Microsoft Graph API instead of SMTP.  These correspond to
    # environment variables ``AEMAILER_TENANT_ID``, ``AEMAILER_CLIENT_ID``,
    # ``AEMAILER_CLIENT_SECRET`` and ``AEMAILER_FROM_ADDRESS`` (or the
    # legacy names without the prefix).  They are not required for
    # normal SMTP operation.
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    from_address: Optional[str] = None

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
        # avoid collisions with system variables like ``USER``.  In
        # addition, keys prefixed with ``AEMAILER_`` are preferred over
        # their unprefixed counterparts to avoid clashing with other
        # environment variables.  For example, ``AEMAILER_HOST`` will be
        # used before ``HOST``.
        file_vars: Dict[str, Optional[str]] = {}
        if env_file is not None:
            # ``dotenv_values`` reads key/value pairs from the file without
            # altering ``os.environ``.  We normalise keys to uppercase
            # later when merging.
            file_vars = dotenv_values(env_file)  # type: ignore[assignment]

        # Build a combined environment mapping where keys are
        # uppercased.  Begin with the process environment and then
        # overlay values from the file (file values override env vars).
        combined: Dict[str, Optional[str]] = {k.upper(): v for k, v in os.environ.items()}
        for k, v in file_vars.items():
            # Normalise file keys to uppercase when merging
            combined[k.upper()] = v

        # Define the configuration fields we expect
        fields = [
            "host",
            "port",
            "user",
            "password",
            "sender",
            "recipients",
            "json_path",
            "report_url",
            "oauth_token",
            "tenant_id",
            "client_id",
            "client_secret",
            "from_address",
        ]
        # Extract values from the combined mapping, preferring
        # ``AEMAILER_<KEY>`` over ``<KEY>``.  If neither is present the
        # value remains ``None``.
        env_map: Dict[str, Optional[str]] = {}
        for field_name in fields:
            prefixed = f"AEMAILER_{field_name.upper()}"
            unprefixed = field_name.upper()
            if prefixed in combined:
                env_map[field_name] = combined[prefixed]
            elif unprefixed in combined:
                env_map[field_name] = combined[unprefixed]
            else:
                env_map[field_name] = None

        # Apply CLI overrides if provided (these take highest precedence)
        if overrides:
            for key, value in overrides.items():
                if value is not None:
                    env_map[key] = value

        # Determine which authentication mechanism is configured.  If
        # ``tenant_id``, ``client_id`` and ``client_secret`` are all
        # present, assume the Microsoft Graph API will be used and
        # relax SMTP requirements.  Otherwise assume SMTP (password or
        # XOAUTH2) and require the usual fields.
        missing: List[str] = []
        using_graph = bool(
            env_map.get("tenant_id") and env_map.get("client_id") and env_map.get("client_secret")
        )
        if using_graph:
            # Graph API mode: require tenant_id, client_id, client_secret and
            # recipients.  Also require at least one of from_address or user
            for field_name in ["tenant_id", "client_id", "client_secret", "recipients"]:
                if not env_map.get(field_name):
                    missing.append(field_name)
            if not (env_map.get("from_address") or env_map.get("user")):
                missing.append("from_address/user")
            # Provide defaults for host/port/user if not supplied; they will
            # not be used but need to be set for type conversion below.
            env_map["host"] = env_map.get("host") or ""
            env_map["port"] = env_map.get("port") or "0"
            # In Graph mode ignore system USER; prefer from_address or existing
            env_map["user"] = env_map.get("from_address") or env_map.get("user") or ""
            env_map["password"] = env_map.get("password") or None
        else:
            # SMTP mode: require host, port, user, recipients
            for field_name in ["host", "port", "user", "recipients"]:
                if not env_map.get(field_name):
                    missing.append(field_name)
            # Require password when no OAuth token is provided
            if not env_map.get("oauth_token") and not env_map.get("password"):
                missing.append("password")
        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(name.upper() for name in missing)}"
            )

        # Convert and normalise values
        port_value = env_map["port"]
        try:
            port_int = int(port_value) if port_value is not None else 0
        except ValueError:
            raise ValueError(f"Invalid port value: {port_value}")

        recipients_raw = env_map["recipients"] or ""
        recipients_list = [addr.strip() for addr in recipients_raw.split(",") if addr.strip()]

        # Ensure the SMTP username is a full email address (contains '@')
        user_val = env_map["user"]
        # Only enforce email format for SMTP modes
        using_graph_final = bool(
            env_map.get("tenant_id") and env_map.get("client_id") and env_map.get("client_secret")
        )
        if not using_graph_final and "@" not in (user_val or ""):
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
            oauth_token=env_map.get("oauth_token") or None,
            tenant_id=env_map.get("tenant_id") or None,
            client_id=env_map.get("client_id") or None,
            client_secret=env_map.get("client_secret") or None,
            from_address=env_map.get("from_address") or None,
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
    uppercased and prefixed with ``AEMAILER_`` when written so that
    they can be read back by :func:`Config.from_env` without
    colliding with unrelated environment variables.  For example,
    the ``host`` field is written as ``AEMAILER_HOST``.

    Parameters
    ----------
    path: Path
        Path to the file that should be created or overwritten.
    config_dict: dict
        Mapping of field names (lowercase) to string values to
        persist.
    """
    lines: List[str] = []
    for key, value in config_dict.items():
        env_key = f"AEMAILER_{key.upper()}"
        lines.append(f"{env_key}={value}\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines))