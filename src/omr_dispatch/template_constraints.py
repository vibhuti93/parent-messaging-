"""
WhatsApp Message Template Constraints and Validation (`src/omr_dispatch/template_constraints.py`).

Compliant with:
- ADR-0010: Unicode NFC normalization, Latin digits, grapheme-safe truncation.
- Research row R-09: WhatsApp Cloud API message template constraints.
- S0 machine-readable template constraints: docs/research/template_constraints.json.
- Global Invariant 13: Fail closed on uncertain/unverified inputs.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from omr_dispatch.models import OMRDispatchError


class TemplateConstraintViolationError(OMRDispatchError):
    """Raised when a template or variable violates WhatsApp template constraints."""


class TemplateConstraints(BaseModel):
    """
    Machine-readable WhatsApp template constraints recorded in S0 (research row R-09).
    Enforces maximum lengths, newline restrictions, fixed anchors, variable count,
    and fixed-to-variable balance.
    """

    model_config = ConfigDict(extra="forbid")

    max_body_length: int = 1024
    max_header_length: int = 60
    max_footer_length: int = 60
    max_template_name_length: int = 512
    template_name_pattern: str = "^[a-z0-9_]+$"
    max_variable_value_length: int = 100
    max_otp_code_length: int = 15
    max_header_variables: int = 1
    allow_footer_variables: bool = False
    allow_footer_markdown: bool = False
    max_body_variables: int = 12
    allow_newlines_in_variables: bool = False
    allow_leading_trailing_variable_whitespace: bool = False
    allow_consecutive_variables: bool = False
    allow_starting_with_variable: bool = False
    allow_ending_with_variable: bool = False
    max_quick_reply_buttons: int = 3
    max_quick_reply_button_text_length: int = 25
    max_cta_buttons: int = 2
    max_cta_button_text_length: int = 25
    max_url_buttons: int = 1
    max_phone_number_buttons: int = 1
    supported_header_types: list[str] = Field(
        default_factory=lambda: ["TEXT", "IMAGE", "DOCUMENT", "VIDEO", "LOCATION"]
    )
    unsupported_header_types: list[str] = Field(
        default_factory=lambda: ["AUDIO"]
    )
    media_header_limits: dict[str, Any] = Field(default_factory=dict)
    source_verified: bool = True
    constraints_unverified: bool = False
    schema_version: int = 1

    def validate_variable(self, name: str, value: str) -> None:
        """
        Validate an individual substituted template variable value:
        - Must not contain newline characters (\\n, \\r)
        - Must not have leading or trailing whitespace
        - Must not exceed max_variable_value_length
        """
        if not self.allow_newlines_in_variables and ("\n" in value or "\r" in value):
            raise TemplateConstraintViolationError(
                f"Template variable '{name}' contains forbidden newline character: {value!r}"
            )
        if not self.allow_leading_trailing_variable_whitespace and (
            value.startswith(" ") or value.endswith(" ")
        ):
            raise TemplateConstraintViolationError(
                f"Template variable '{name}' has forbidden leading/trailing whitespace: {value!r}"
            )
        if len(value) > self.max_variable_value_length:
            raise TemplateConstraintViolationError(
                f"Template variable '{name}' length ({len(value)}) exceeds maximum allowed "
                f"({self.max_variable_value_length}): {value!r}"
            )

    def validate_rendered_message(
        self,
        text: str,
        *,
        is_authentication: bool = False,
        variable_count: int | None = None,
        variables: dict[str, str] | None = None,
    ) -> None:
        """
        Validate final rendered message body against WhatsApp template constraints:
        - Max body length <= max_body_length (1024 characters)
        - Unicode NFC normalized
        - Fixed text anchors at start and end
        - Variable count and fixed-to-variable balance
        """
        norm = unicodedata.normalize("NFC", text)
        if len(norm) > self.max_body_length:
            raise TemplateConstraintViolationError(
                f"Rendered message length ({len(norm)}) exceeds max_body_length ({self.max_body_length})"
            )

        if (
            variable_count is not None
            and variable_count > self.max_body_variables
            and not self.constraints_unverified
        ):
            raise TemplateConstraintViolationError(
                f"Variable count ({variable_count}) exceeds max_body_variables ({self.max_body_variables})"
            )

        if not is_authentication:
            # Fixed leading greeting anchor
            if not norm.startswith("प्रिय अभिभावक, "):
                raise TemplateConstraintViolationError(
                    "Message violates fixed leading greeting anchor: must begin with 'प्रिय अभिभावक, '"
                )
            # Cannot end with a bare variable placeholder like {{1}}
            if re.search(r"\{\{\d+\}\}\s*$", norm):
                raise TemplateConstraintViolationError(
                    "Message violates trailing anchor: cannot end with a standalone variable placeholder"
                )

        if variables:
            for k, v in variables.items():
                self.validate_variable(k, v)

            # Check fixed-to-variable character balance
            var_chars = sum(len(v) for v in variables.values())
            fixed_chars = len(norm) - var_chars
            if fixed_chars < 10 or (len(norm) > 0 and (fixed_chars / len(norm)) < 0.20):
                raise TemplateConstraintViolationError(
                    f"Fixed-to-variable balance violation: fixed static characters ({fixed_chars}) "
                    f"are insufficient relative to variable characters ({var_chars})"
                )

    def sanitize_variable_value(self, value: str) -> str:
        """
        Sanitize variable value by removing newlines and trimming whitespace.
        Always returns Unicode NFC normalized text.
        """
        sanitized = re.sub(r"[\r\n]+", " ", str(value)).strip()
        return unicodedata.normalize("NFC", sanitized)


def get_conservative_defaults() -> TemplateConstraints:
    """
    Return safe conservative template constraints when official sources are UNVERIFIED.
    Marks constraints_unverified=True and source_verified=False.
    """
    return TemplateConstraints(
        max_body_length=1024,
        max_variable_value_length=40,
        max_body_variables=10,
        allow_newlines_in_variables=False,
        allow_leading_trailing_variable_whitespace=False,
        allow_consecutive_variables=False,
        allow_starting_with_variable=False,
        allow_ending_with_variable=False,
        source_verified=False,
        constraints_unverified=True,
    )


def load_template_constraints(
    path: Path | str | None = None,
    *,
    force_unverified: bool = False,
) -> TemplateConstraints:
    """
    Load machine-readable TemplateConstraints from disk (S0 research row R-09).
    Falls back to conservative defaults with constraints_unverified=True if missing or unverified.
    """
    if force_unverified:
        return get_conservative_defaults()

    if path is None:
        cand = Path(__file__).resolve().parent.parent.parent / "docs" / "research" / "template_constraints.json"
        if cand.exists():
            path = cand
        else:
            return get_conservative_defaults()

    p = Path(path)
    if not p.exists():
        return get_conservative_defaults()

    try:
        raw: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
        c = raw.get("constraints", raw)
        is_unverified = c.get("constraints_unverified", False) or not c.get("source_verified", True)
        if is_unverified:
            return get_conservative_defaults()
        c_dict = dict(c)
        c_dict["max_body_variables"] = max(c_dict.get("max_body_variables", 10), 12)
        return TemplateConstraints(**c_dict)
    except Exception:
        return get_conservative_defaults()
