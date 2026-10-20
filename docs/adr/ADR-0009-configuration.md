# ADR-0009: Typed Configuration, Environment Validation, and SecretStr

## Status
`PROPOSED`

## Context
The engine requires configuration parameters for API endpoints, pinned Graph API version (`v21.0`), timeouts, rate limits, audio paths, and security switches (`LIVE_DISPATCH_ENABLED`, `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED`).
Reading environment variables via ad-hoc `os.environ.get("KEY")` calls throughout the codebase leads to late runtime crashes (missing keys discovered midway through a batch), insecure defaults, and accidental leakage of API keys into logs or error dumps.

## Options Considered

### Option 1: Ad-hoc `os.environ` Reads in Modules
- *Description*: Call `os.getenv()` wherever a configuration value is needed.
- *Pros*: Zero setup.
- *Cons*: Missing variables only crash when the specific line is executed; no type validation; values are easily leaked.

### Option 2: Single Centralized Typed `Settings` Object with `pydantic-settings` and `SecretStr`
- *Description*:
  - **Centralized Definition:** All settings defined in a single immutable Pydantic `Settings` class (`src/omr_dispatch/config.py`).
  - **Fail-Fast Validation:** Validated at application startup. If an invalid or missing value is encountered, the engine refuses to start.
  - **Secret Masking:** Sensitive credentials (`WHATSAPP_CLOUD_API_TOKEN`, `WHATSAPP_APP_SECRET`) wrapped in `pydantic.SecretStr`, preventing raw exposure in string representations, JSON dumps, or debuggers.
  - **Safe Defaults:** `LIVE_DISPATCH_ENABLED=False`, `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=False`.
  - **Guardrail:** Pre-commit lint rule strictly banning `os.environ` reads outside `src/omr_dispatch/config.py`.
- *Pros*: 100% type safety; immediate failure on misconfiguration; impossible to accidentally print tokens; centralized configuration schema.
- *Cons*: All configuration changes require editing the central settings class.

## Proposed Decision
We propose **Option 2 (Single Centralized Typed Settings Object with SecretStr)**.

### Settings Model Blueprint
```python
from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API & Provider Configuration
    whatsapp_cloud_api_version: str = Field(default="v21.0")
    whatsapp_phone_number_id: str = Field(default="")
    whatsapp_waba_id: str = Field(default="")
    whatsapp_cloud_api_token: SecretStr = Field(default=SecretStr(""))
    whatsapp_app_secret: SecretStr = Field(default=SecretStr(""))

    # Safety Gates (Default Disabled)
    live_dispatch_enabled: bool = Field(default=False)
    deployment_compliance_acknowledged: bool = Field(default=False)

    # Operational Parameters
    default_timezone: str = Field(default="Asia/Kolkata")
    sqlite_db_path: str = Field(default="omr_dispatch.db")
    audio_assets_dir: str = Field(default="assets/audio")
    max_batch_size: int = Field(default=200)

    class Config:
        env_file = ".env"
        extra = "forbid"
```

## Consequences
- **Positive**: Strict security; impossible to start the engine with malformed settings; complete protection against credential leaks.
- **Negative**: Extra Pydantic dependency (`pydantic-settings`).
- **Neutral**: Enforced via pre-commit guardrail.

## Revisit When
Revisit if enterprise secret managers (e.g. AWS Secrets Manager, HashiCorp Vault) are integrated.
