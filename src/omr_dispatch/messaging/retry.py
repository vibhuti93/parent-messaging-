"""
Five-Class Error Classification and Bounded Exponential Backoff Engine (`src/omr_dispatch/messaging/retry.py`).

Compliant with:
- Part B Stage S9 Task 2 & Gate 9 requirements.
- Global Invariant 13: Fail closed: uncertain send outcome is UNKNOWN_NEEDS_REVIEW, never a blind retry.
- Global Invariant 18: No silent resends.
- ADR-0002: Zero float() calls in core and messaging packages. All delays in integer milliseconds or Decimal.
- ADR-0008: Structured typed error classification.
- Official Source Verification R-11, R-12, R-13, and provider_contract.json.
"""

from __future__ import annotations

import random
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

# Authoritative error codes from docs/research/provider_contract.json
RETRY_SAFE_CODES: frozenset[int] = frozenset({
    4,       # Application request limit reached
    80007,   # Rate limit hit for the WABA account
    130429,  # Cloud API message throughput rate limit exceeded
    131056,  # Rate limit hit for sending messages from this phone number to recipient
})

OUTCOME_UNKNOWN_CODES: frozenset[int] = frozenset({
    1,       # Possible server error
    2,       # Temporary service downtime or overload
    131000,  # Something went wrong (unclassified internal error)
    131016,  # Service temporarily unavailable
    131052,  # Media download error from provider
    133004,  # Server temporarily unavailable
    134102,  # Template sync error between Graph API and internal servers
})

OPERATOR_ACTION_CODES: frozenset[int] = frozenset({
    0, 3, 10, 33, 190, 200, 299, 368, 130403, 130497, 131005, 131031, 131037,
    131042, 131045, 131048, 131049, 131057, 131063, 131064, 132001, 132007,
    132015, 132016, 132068, 132069, 133000, 133005, 133006, 133008, 133009,
    133010, 133015, 133016, 134011, 134101, 1752041, 2388019, 2388039,
})

PERMANENT_CODES: frozenset[int] = frozenset({
    100, 130472, 131008, 131009, 131021, 131026, 131047, 131050, 131051,
    131053, 131055, 132000, 132005, 132012, 132018, 134100,
})


class ErrorClass(StrEnum):
    """
    Five-class error classification scheme (S9 Task 2 & R-11).
    Determines operational retry and state transition behavior.
    """

    RETRY_SAFE = "RETRY_SAFE"          # Safe to auto-retry with backoff (e.g. rate limits)
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"# Uncertain acceptance; NEVER auto-retry (e.g. 5xx, timeouts)
    OPERATOR_ACTION = "OPERATOR_ACTION"# Requires human action; fail closed (e.g. auth, billing)
    PERMANENT = "PERMANENT"            # Unrecoverable error; fail closed (e.g. invalid payload)
    UNKNOWN = "UNKNOWN"                # Unrecognized; defaults to OUTCOME_UNKNOWN handling


class ClassifiedError(BaseModel):
    """Structured result of error classification."""

    model_config = ConfigDict(extra="forbid")

    error_class: ErrorClass
    http_status: int | None = None
    provider_code: int | None = None
    message: str = ""
    retry_after_seconds: int | None = None
    is_retryable: bool = False
    requires_operator_action: bool = False


def classify_provider_error(
    http_status: int | None = None,
    provider_code: int | None = None,
    message: str = "",
    retry_after_seconds: int | None = None,
    is_timeout: bool = False,
    is_connection_reset: bool = False,
) -> ClassifiedError:
    """
    Classify a provider HTTP status, payload error code, or network exception into
    exactly one of the five authoritative error classes (S9 Task 2).
    """
    # 1. Network timeouts and connection resets where receipt is ambiguous -> OUTCOME_UNKNOWN
    if is_timeout or is_connection_reset:
        return ClassifiedError(
            error_class=ErrorClass.OUTCOME_UNKNOWN,
            http_status=http_status,
            provider_code=provider_code,
            message=message or ("Network timeout after transmission" if is_timeout else "Connection reset"),
            is_retryable=False,
            requires_operator_action=False,
        )

    # 2. Check against explicit numeric provider codes from provider_contract.json
    if provider_code is not None:
        if provider_code in RETRY_SAFE_CODES:
            return ClassifiedError(
                error_class=ErrorClass.RETRY_SAFE,
                http_status=http_status,
                provider_code=provider_code,
                message=message,
                retry_after_seconds=retry_after_seconds,
                is_retryable=True,
                requires_operator_action=False,
            )
        if provider_code in OUTCOME_UNKNOWN_CODES:
            return ClassifiedError(
                error_class=ErrorClass.OUTCOME_UNKNOWN,
                http_status=http_status,
                provider_code=provider_code,
                message=message,
                is_retryable=False,
                requires_operator_action=False,
            )
        if provider_code in OPERATOR_ACTION_CODES:
            return ClassifiedError(
                error_class=ErrorClass.OPERATOR_ACTION,
                http_status=http_status,
                provider_code=provider_code,
                message=message,
                is_retryable=False,
                requires_operator_action=True,
            )
        if provider_code in PERMANENT_CODES:
            return ClassifiedError(
                error_class=ErrorClass.PERMANENT,
                http_status=http_status,
                provider_code=provider_code,
                message=message,
                is_retryable=False,
                requires_operator_action=False,
            )

    # 3. Fallback to HTTP status codes
    if http_status is not None:
        if http_status == 429:
            return ClassifiedError(
                error_class=ErrorClass.RETRY_SAFE,
                http_status=http_status,
                provider_code=provider_code,
                message=message or "HTTP 429 Rate limit exceeded",
                retry_after_seconds=retry_after_seconds,
                is_retryable=True,
                requires_operator_action=False,
            )
        if http_status in (401, 403):
            return ClassifiedError(
                error_class=ErrorClass.OPERATOR_ACTION,
                http_status=http_status,
                provider_code=provider_code,
                message=message or f"HTTP {http_status} Authentication or permission failure",
                is_retryable=False,
                requires_operator_action=True,
            )
        if 500 <= http_status <= 599:
            return ClassifiedError(
                error_class=ErrorClass.OUTCOME_UNKNOWN,
                http_status=http_status,
                provider_code=provider_code,
                message=message or f"HTTP {http_status} Internal server error",
                is_retryable=False,
                requires_operator_action=False,
            )
        if http_status in (400, 404, 405, 413, 415, 422):
            return ClassifiedError(
                error_class=ErrorClass.PERMANENT,
                http_status=http_status,
                provider_code=provider_code,
                message=message or f"HTTP {http_status} Permanent client error",
                is_retryable=False,
                requires_operator_action=False,
            )

    # 4. Default: unclassified error defaults to OUTCOME_UNKNOWN semantics (fail closed)
    return ClassifiedError(
        error_class=ErrorClass.UNKNOWN,
        http_status=http_status,
        provider_code=provider_code,
        message=message or "Unrecognized provider error structure",
        is_retryable=False,
        requires_operator_action=False,
    )


def compute_backoff_delay_ms(
    attempt: int,
    base_delay_ms: int = 1000,
    max_delay_ms: int = 32000,
    retry_after_seconds: int | None = None,
    seed: int | None = None,
) -> int:
    """
    Compute bounded exponential backoff delay with decorrelated/full jitter in integer milliseconds (ADR-0002).
    Zero float() calls.

    Rules:
      - If retry_after_seconds is provided, honors Retry-After (converted to ms, capped at max_delay_ms).
      - Otherwise, computes exponential delay: min(max_delay_ms, base_delay_ms * 2**(attempt - 1)).
      - Applies full jitter: random integer in range [base_delay_ms // 2, computed_delay].
    """
    if retry_after_seconds is not None and retry_after_seconds > 0:
        delay_from_header = retry_after_seconds * 1000
        return min(delay_from_header, max_delay_ms)

    safe_attempt = max(1, attempt)
    # Exponential factor: 2 ** (attempt - 1)
    exp_factor = 1 << min(10, safe_attempt - 1)
    target_delay = min(max_delay_ms, base_delay_ms * exp_factor)

    rng = random.Random(seed) if seed is not None else random
    min_bound = max(1, base_delay_ms // 2)
    max_bound = max(min_bound, target_delay)

    return rng.randint(min_bound, max_bound)


def should_auto_retry(error_class: ErrorClass, current_attempt: int, max_retries: int = 4) -> bool:
    """
    Strict retry policy (S9 Task 2 & Global Invariant 13):
    Only RETRY_SAFE errors may ever be auto-retried.
    OUTCOME_UNKNOWN, OPERATOR_ACTION, PERMANENT, and UNKNOWN must NEVER be auto-retried.
    """
    if error_class != ErrorClass.RETRY_SAFE:
        return False
    return current_attempt < max_retries
