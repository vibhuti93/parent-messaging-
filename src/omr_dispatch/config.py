"""
Configuration and Environment Settings (`src/omr_dispatch/config.py`).

ADR-0009: Typed Configuration, Environment Validation, and SecretStr.
Validates environment parameters at startup, wraps sensitive credentials
in SecretStr, and enforces safe-by-default switches (live dispatch disabled).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class Settings(BaseModel):
    """
    Centralized, typed application settings.
    Strict extra='forbid' ensures no unknown configuration keys are silently accepted.
    """

    model_config = ConfigDict(extra="forbid")

    # API & Provider Configuration (ADR-0009, README.md)
    whatsapp_cloud_api_version: str = Field(default="")
    whatsapp_phone_number_id: str = Field(default="")
    whatsapp_waba_id: str = Field(default="")
    whatsapp_cloud_api_token: SecretStr = Field(default=SecretStr(""))
    whatsapp_access_token: SecretStr = Field(default=SecretStr(""))
    whatsapp_app_secret: SecretStr = Field(default=SecretStr(""))
    facebook_app_secret: SecretStr = Field(default=SecretStr(""))
    whatsapp_webhook_verify_token: SecretStr = Field(default=SecretStr(""))

    # Safety Gates (Default Disabled per D-09, Rule 8, README.md)
    live_dispatch_enabled: bool = Field(default=False)
    deployment_compliance_acknowledged: bool = Field(default=False)
    network_tts_enabled: bool = Field(default=False)

    # Parent Confirmation & QR Configuration (D-11, DECISIONS_OPEN item 2)
    qr_confirmation_enabled: bool = Field(default=False)
    qr_token_ttl_hours: int = Field(default=72)
    qr_hmac_secret: SecretStr = Field(default=SecretStr(""))

    # Carrier SMS / TRAI DLT Prerequisites (Deferred, PRE_DEPLOYMENT_CHECKLIST)
    trai_dlt_pe_id: str = Field(default="")
    trai_dlt_template_id: str = Field(default="")

    # Data Retention & Operational Parameters (D-13, ADR-0005, ADR-0007)
    data_retention_days_logs: int = Field(default=90)
    default_timezone: str = Field(default="Asia/Kolkata")
    sqlite_db_path: str = Field(default="omr_dispatch.db")
    audio_assets_dir: str = Field(default="assets/audio")
    max_batch_size: int = Field(default=200)

    # Per-Organization / Tenant Settings (S1-BLOCK-06, ADR-0010, ADR-0017)
    include_roll_in_text: bool = Field(default=False)


def _parse_bool(val: str | bool | None) -> bool:
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    return val.strip().lower() in ("true", "1", "yes", "on")


def load_settings(
    env_file: str | Path | None = None,
    **overrides: Any,
) -> Settings:
    """
    Load and validate settings from environment variables and an optional .env file.
    All unknown environment keys are filtered out to satisfy extra='forbid'.
    """
    if env_file is not None and Path(env_file).exists():
        load_dotenv(dotenv_path=env_file, override=False)
    else:
        load_dotenv(override=False)

    # Map environment variables to Settings fields
    values: dict[str, Any] = {}

    def get_env_val(key: str, default: Any = None) -> Any:
        return os.environ.get(key, os.environ.get(key.upper(), default))

    # String fields
    for field in (
        "whatsapp_cloud_api_version",
        "whatsapp_phone_number_id",
        "whatsapp_waba_id",
        "trai_dlt_pe_id",
        "trai_dlt_template_id",
        "default_timezone",
        "sqlite_db_path",
        "audio_assets_dir",
    ):
        v = get_env_val(field)
        if v is not None:
            values[field] = v

    # Secret fields
    for field in (
        "whatsapp_cloud_api_token",
        "whatsapp_access_token",
        "whatsapp_app_secret",
        "facebook_app_secret",
        "whatsapp_webhook_verify_token",
        "qr_hmac_secret",
    ):
        v = get_env_val(field)
        if v is not None:
            values[field] = SecretStr(v)

    # Boolean fields
    for field in (
        "live_dispatch_enabled",
        "deployment_compliance_acknowledged",
        "network_tts_enabled",
        "qr_confirmation_enabled",
        "include_roll_in_text",
    ):
        v = get_env_val(field)
        if v is not None:
            values[field] = _parse_bool(v)

    import contextlib

    # Integer fields
    for field in ("qr_token_ttl_hours", "data_retention_days_logs", "max_batch_size"):
        v = get_env_val(field)
        if v is not None:
            with contextlib.suppress(ValueError):
                values[field] = int(v)

    # Apply explicit overrides
    values.update(overrides)

    return Settings(**values)
