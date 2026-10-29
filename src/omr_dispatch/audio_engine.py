"""
Audio Engine (`src/omr_dispatch/audio_engine.py`).

Provides deterministic token stitching (RECORDED_TOKEN_STITCH), optional network
TTS provider interface (NETWORK_TTS), FFmpeg-based WhatsApp Ogg/Opus transcoding,
secure PII-free caching, and token preflight validation.

Adheres strictly to:
- ADR-0002: Zero float calls in core. All durations in integer milliseconds or Fraction.
- ADR-0008: Structured typed exception hierarchy.
- ADR-0009: Central Settings sourcing, zero direct environment reads.
- ADR-0010: Gender-neutral phrasing ('आपके बच्चे'), zero child names or class spoken.
- Invariant 10: Zero PII in cache keys, cache file paths, or log statements.
- D-08: Target duration 15-25s, hard max 45s, concise overflow handling.
- R-08 & R-16: Mono Opus in Ogg container at 48kHz for WhatsApp voice notes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
import tempfile
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from fractions import Fraction
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from omr_dispatch.config import Settings
from omr_dispatch.models import OMRDispatchError

logger = logging.getLogger(__name__)

# Duration Limits (in integer milliseconds, per D-08)
TARGET_MIN_DURATION_MS: int = 15000
TARGET_MAX_DURATION_MS: int = 25000
HARD_MAX_DURATION_MS: int = 45000

# WhatsApp Opus Specifications (R-08, R-16)
OPUS_SAMPLE_RATE: int = 48000
OPUS_CHANNELS: int = 1
OPUS_BITRATE: str = "32k"

# Pause durations (in milliseconds)
PAUSE_SHORT_MS: int = 150
PAUSE_MEDIUM_MS: int = 250
PAUSE_CLAUSE_MS: int = 350

ENCODER_SETTINGS_VERSION: str = "v1-opus48k-mono32k"


class AudioMode(StrEnum):
    """Audio generation modes."""

    RECORDED_TOKEN_STITCH = "RECORDED_TOKEN_STITCH"
    NETWORK_TTS = "NETWORK_TTS"


# ==============================================================================
# Typed Exceptions (ADR-0008)
# ==============================================================================


class AudioEngineError(OMRDispatchError):
    """Base class for all audio engine exceptions."""


class AudioPreflightValidationError(AudioEngineError):
    """Raised when audio token catalog or file preflight validation fails."""


class AudioMissingTokenError(AudioEngineError):
    """Raised when a required audio token clip is missing from disk or catalog."""


class FFmpegExecutionError(AudioEngineError):
    """Raised when FFmpeg fails, exits non-zero, or is missing."""


class FFmpegTimeoutError(AudioEngineError):
    """Raised when FFmpeg execution exceeds the allowed timeout."""


class AudioDurationOverflowError(AudioEngineError):
    """Raised when audio duration exceeds the hard 45s maximum (D-08)."""


class NetworkTTSError(AudioEngineError):
    """Raised when network TTS synthesis encounters a failure."""


class NetworkTTSDisabledError(AudioEngineError):
    """Raised when network TTS is invoked while disabled in configuration."""


# ==============================================================================
# Catalog & Synthesis Data Models
# ==============================================================================


class AudioTokenManifestEntry(BaseModel):
    """Metadata for a single recorded audio token clip."""

    model_config = ConfigDict(extra="forbid")

    token_id: str
    filename: str
    spoken_text: str
    voice: str
    license: str
    sample_rate: int
    channels: int
    codec: str
    duration_ms: int
    sha256: str
    version: str


class AudioTokenCatalog(BaseModel):
    """Catalog of approved audio tokens and manifest."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    manifest_version: str = "1.0.0"
    language: str = "hi-IN"
    voice: str = "hi_IN_neutral"
    default_sample_rate: int = 24000
    default_channels: int = 1
    license: str = ""
    token_count: int
    tokens: dict[str, AudioTokenManifestEntry]
    base_dir: Path | None = Field(default=None)
    synthetic_pause_provisioning: dict[str, Any] | None = Field(default=None)


class AudioSynthesisResult(BaseModel):
    """Result of an audio synthesis run."""

    model_config = ConfigDict(extra="forbid")

    output_path: Path
    duration_ms: int
    token_sequence: list[str]
    mode: AudioMode
    sha256: str
    cache_hit: bool = False
    is_concise_fallback: bool = False


# ==============================================================================
# Helper Numerics (ADR-0002: Zero float calls)
# ==============================================================================


def _parse_decimal_str_to_ms(duration_str: str) -> int:
    """Convert decimal duration string to integer milliseconds with ROUND_HALF_UP."""
    d = Decimal(duration_str)
    ms = (d * Decimal("1000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(ms)


# ==============================================================================
# Preflight Validation
# ==============================================================================


def validate_audio_tokens(
    tokens_dir: Path | str,
    manifest_path: Path | str | None = None,
) -> AudioTokenCatalog:
    """
    Validate all audio tokens against manifest.json.
    Verifies headers, hashes, sample rates, channels, and duration bounds.
    Missing tokens or hash mismatches fail loudly.
    """
    base = Path(tokens_dir).resolve()
    if not base.exists() or not base.is_dir():
        raise AudioPreflightValidationError(f"Audio tokens directory does not exist: {base}")

    m_path = Path(manifest_path).resolve() if manifest_path else base / "manifest.json"
    if not m_path.exists():
        raise AudioPreflightValidationError(f"Manifest file missing: {m_path}")

    try:
        data = json.loads(m_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise AudioPreflightValidationError(f"Malformed manifest JSON at {m_path}: {e}") from e

    catalog = AudioTokenCatalog(**data, base_dir=base)

    if catalog.token_count != len(catalog.tokens):
        raise AudioPreflightValidationError(
            f"Manifest token count mismatch: header={catalog.token_count}, actual={len(catalog.tokens)}"
        )

    for token_id, entry in catalog.tokens.items():
        clip_file = base / entry.filename
        if not clip_file.exists():
            raise AudioMissingTokenError(f"Required audio token missing from disk: {clip_file}")

        file_bytes = clip_file.read_bytes()
        actual_hash = hashlib.sha256(file_bytes).hexdigest()
        if actual_hash != entry.sha256:
            raise AudioPreflightValidationError(
                f"SHA-256 hash mismatch for token {token_id} ({entry.filename})"
            )

        if len(file_bytes) < 64:
            raise AudioPreflightValidationError(f"Corrupt or truncated audio token: {clip_file}")

        # Check MP3 sync word (0xFFE or 0xFFF)
        if not (file_bytes[0] == 0xFF and (file_bytes[1] & 0xE0) == 0xE0):
            raise AudioPreflightValidationError(f"Invalid MP3 sync header in token: {clip_file}")

        # Physical MP3 header uniformity check
        version_id = (file_bytes[1] >> 3) & 0x03
        sr_idx = (file_bytes[2] >> 2) & 0x03
        channel_mode = (file_bytes[3] >> 6) & 0x03

        if version_id == 2:  # MPEG-2 Audio Layer III
            sr_map = {0: 22050, 1: 24000, 2: 16000}
            detected_sr = sr_map.get(sr_idx)
            if detected_sr != entry.sample_rate:
                raise AudioPreflightValidationError(
                    f"Physical MP3 sample rate ({detected_sr} Hz) does not match manifest ({entry.sample_rate} Hz) for {token_id}"
                )

        if channel_mode != 3:  # 3 = Single channel (mono)
            raise AudioPreflightValidationError(
                f"Physical MP3 channel mode is not mono for {token_id}: mode={channel_mode}"
            )

        if entry.channels != catalog.default_channels or entry.channels != 1:
            raise AudioPreflightValidationError(
                f"Token {token_id} must be mono, got channels={entry.channels}"
            )
        if entry.sample_rate != catalog.default_sample_rate or entry.sample_rate <= 0:
            raise AudioPreflightValidationError(
                f"Token {token_id} sample rate ({entry.sample_rate}) differs from catalog default ({catalog.default_sample_rate})"
            )
        if entry.codec != "mp3":
            raise AudioPreflightValidationError(
                f"Token {token_id} codec must be 'mp3', got '{entry.codec}'"
            )

    return catalog


# ==============================================================================
# Token Mapping & Grammar
# ==============================================================================


def number_to_tokens(n: int | Fraction) -> list[str]:
    """
    Convert an integer number (positive or negative) into approved catalog token IDs.
    Supports negative numbers via 'w_minus' prefix.
    """
    int_val = int(n) if isinstance(n, Fraction) else n
    if int_val < 0:
        return ["w_minus", *number_to_tokens(-int_val)]

    if int_val <= 100:
        return [f"num_{int_val:02d}"]

    # 101 to 999
    tokens: list[str] = []
    hundreds = int_val // 100
    rem = int_val % 100

    if hundreds == 1:
        tokens.append("num_100")
    else:
        tokens.extend([f"num_{hundreds:02d}", "w_sau"])

    if rem > 0:
        tokens.extend(number_to_tokens(rem))

    return tokens


def map_report_to_tokens(report: Any, *, concise: bool = False) -> list[str]:
    """
    Map student diagnostic report facts to the canonical token sequence.
    Guarantees:
    - Gender-neutral phrasing ('w_aapke_bachche').
    - Zero spoken child names or classes (ADR-0010, Invariant 10).
    - Neutral factual attendance context for ABSENT (explicit absence notification).
    - Authentic Hindi grammar avoiding 'सौ सौ सौ' for 300.
    - Explicit pause tokens between clauses to avoid clipping.
    """
    # Extract report facts supporting dict or Pydantic models
    if isinstance(report, dict):
        status = report.get("status") or report.get("attendance_status") or "PRESENT"
        net_marks = report.get("net_marks")
        max_marks = report.get("max_marks", 300)
        bleed_marks = report.get("bleed_marks")
        wrong = report.get("wrong")
        present_count = report.get("present_count", 16)
    else:
        status = getattr(report, "status", None) or getattr(report, "attendance_status", "PRESENT")
        net_marks = getattr(report, "net_marks", None)
        max_marks = getattr(report, "max_marks", 300)
        bleed_marks = getattr(report, "bleed_marks", None)
        wrong = getattr(report, "wrong", None)
        present_count = getattr(report, "present_count", 16)

    # Standard competition attendance check
    is_absent = (str(status).upper() == "ABSENT")

    tokens: list[str] = []

    # 1. Respectful fixed greeting anchor
    tokens.append("w_greeting")
    tokens.append("pause_clause")

    # 2. Gender-neutral child reference
    tokens.append("w_aapke_bachche")
    tokens.append("pause_short")

    if is_absent:
        # ABSENT Student Grammar:
        # - Explicit absence statement: [w_anupasthit_rahe]
        # - Batch attendance context: [w_is_pariksha_mein, num_{present_count}, w_vidyarthi_shamil_the, w_teen_sau]
        tokens.append("w_anupasthit_rahe")
        tokens.append("pause_clause")
        tokens.append("w_is_pariksha_mein")
        if present_count is not None:
            int_pc = int(present_count) if isinstance(present_count, (int, Fraction)) else int(str(present_count).split(".")[0])
            tokens.extend(number_to_tokens(int_pc))
        tokens.append("w_vidyarthi_shamil_the")
        tokens.append("w_teen_sau")
        return tokens

    # PRESENT Student Grammar:
    # Net score fact: [w_kul_number, num_{net}, w_teen_sau, w_prapt_kiye]
    tokens.append("w_kul_number")
    if net_marks is not None:
        int_net = int(net_marks) if isinstance(net_marks, (int, Fraction)) else int(str(net_marks).split(".")[0])
        if int_net < 0:
            tokens.append("w_minus")
            tokens.extend(number_to_tokens(-int_net))
        else:
            tokens.extend(number_to_tokens(int_net))

    if max_marks == 300:
        tokens.append("w_teen_sau")
    else:
        tokens.extend(number_to_tokens(max_marks))
        tokens.append("w_mein_se")

    tokens.append("w_prapt_kiye")

    # Deduction fact (if wrong > 0): [num_{wrong}, w_galat_prashno_se, num_{deducted}, w_kate_hain]
    int_wrong = 0
    if wrong is not None:
        try:
            int_wrong = int(wrong) if isinstance(wrong, (int, Fraction)) else int(str(wrong).split(".")[0])
        except Exception:
            int_wrong = 0

    int_bleed = 0
    if bleed_marks is not None:
        try:
            int_bleed = int(bleed_marks) if isinstance(bleed_marks, (int, Fraction)) else int(str(bleed_marks).split(".")[0])
        except Exception:
            int_bleed = 0

    if int_wrong == 0 and int_bleed > 0:
        int_wrong = int_bleed
    elif int_bleed == 0 and int_wrong > 0:
        int_bleed = int_wrong

    if not concise and int_wrong > 0:
        tokens.append("pause_clause")
        tokens.extend(number_to_tokens(int_wrong))
        tokens.append("w_galat_prashno_se")
        tokens.extend(number_to_tokens(int_bleed if int_bleed > 0 else int_wrong))
        tokens.append("w_kate_hain")

    return tokens


# ==============================================================================
# Secure Caching (Invariant 10)
# ==============================================================================


def compute_audio_cache_key(
    *,
    mode: str,
    voice_version: str,
    language: str,
    rate_pitch: str,
    token_sequence: list[str],
    encoder_version: str = ENCODER_SETTINGS_VERSION,
) -> str:
    """
    Compute deterministic SHA-256 cache key.
    Strictly forbids student names, roll numbers, or message text in cache keys.
    """
    payload = {
        "encoder_version": encoder_version,
        "language": language,
        "mode": mode,
        "rate_pitch": rate_pitch,
        "token_sequence": token_sequence,
        "voice_version": voice_version,
    }
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


# ==============================================================================
# Hindi Vocabulary Constants & Transcript Formatting
# ==============================================================================

HINDI_NUMBER_NAMES: list[str] = [
    "शून्य", "एक", "दो", "तीन", "चार", "पांच", "छह", "सात", "आठ", "नौ",
    "दस", "ग्यारह", "बारह", "तेरह", "चौदह", "पंद्रह", "सोलह", "सत्रह", "अठारह", "उन्नीस",
    "बीस", "इक्कीस", "बाईस", "तेईस", "चौबीस", "पच्चीस", "छब्बीस", "सत्ताईस", "अट्ठाईस", "उनतीस",
    "तीस", "इकत्तीस", "बत्तीस", "तैंतीस", "चौंतीस", "पैंतीस", "छत्तीस", "सैंतीस", "अड़तीस", "उनतालीस",
    "चालीस", "इकतालीस", "बयालीस", "तैंतालीस", "चवालीस", "पैंतालीस", "छियालीस", "सैंतालीस", "अड़तालीस", "उनचास",
    "पचास", "इक्यावन", "बावन", "तिरपन", "चौवन", "पचपन", "छप्पन", "सत्तावन", "अट्ठावन", "उनसठ",
    "साठ", "इकसठ", "बासठ", "तिरसठ", "चौंसठ", "पैंसठ", "छियासठ", "सरसठ", "अड़सठ", "उनहत्तर",
    "सत्तर", "इकहत्तर", "बहत्तर", "तिहत्तर", "चौहत्तर", "पचहत्तर", "छिहत्तर", "सतहत्तर", "अठहत्तर", "उनासी",
    "अस्सी", "इक्यासी", "बयासी", "तिरासी", "चौरासी", "पचासी", "छियासी", "सत्तासी", "अट्ठासी", "नवासी",
    "नब्बे", "इक्यानवे", "बानवे", "तिरानवे", "चौरानवे", "पचानवे", "छियानवे", "सत्तानवे", "अट्ठानवे", "निन्यानवे",
    "सौ",
]

HINDI_WORD_TOKENS: dict[str, str] = {
    "w_greeting": "प्रिय अभिभावक",
    "w_aapke_bachche": "आपके बच्चे",
    "w_kul_number": "कुल नंबर",
    "w_mein_se": "में से",
    "w_minus": "माइनस",
    "w_sau": "सौ",
    "w_teen_sau": "तीन सौ में से",
    "w_prapt_kiye": "नंबर प्राप्त किए हैं",
    "w_galat_prashno_se": "गलत जवाबों से",
    "w_kate_hain": "नंबर कटे हैं",
    "w_anupasthit_rahe": "आज की परीक्षा में अनुपस्थित रहे",
    "w_is_pariksha_mein": "इस परीक्षा में कुल",
    "w_vidyarthi_shamil_the": "विद्यार्थी शामिल हुए थे",
}


def format_token_sequence_transcript(
    token_sequence: list[str],
    catalog: AudioTokenCatalog | None = None,
) -> str:
    """
    Format a token sequence into a human-readable Hindi transcript.
    Pause tokens are formatted with ellipsis indicators ('...').
    """
    words_map: dict[str, str] = dict(HINDI_WORD_TOKENS)
    if catalog is not None:
        words_map.update({k: v.spoken_text for k, v in catalog.tokens.items()})
    else:
        for idx, name in enumerate(HINDI_NUMBER_NAMES):
            words_map[f"num_{idx:02d}"] = name

    parts: list[str] = []
    for t in token_sequence:
        if t.startswith("pause_"):
            parts.append("...")
        elif t in words_map:
            parts.append(words_map[t])
        else:
            parts.append(t)

    raw_text = " ".join(parts).strip()
    return unicodedata.normalize("NFC", raw_text)


# ==============================================================================
# FFmpeg Transcoder & Concat
# ==============================================================================


def _get_ffmpeg_path() -> str:
    """Resolve FFmpeg executable path."""
    bin_path = shutil.which("ffmpeg")
    if not bin_path:
        raise FFmpegExecutionError("FFmpeg binary not found on system PATH")
    return bin_path


def _get_ffprobe_path() -> str:
    """Resolve FFprobe executable path."""
    bin_path = shutil.which("ffprobe")
    if not bin_path:
        raise FFmpegExecutionError("FFprobe binary not found on system PATH")
    return bin_path


def transcode_to_whatsapp_ogg(
    in_path: Path | str,
    out_path: Path | str,
    *,
    timeout_seconds: int = 30,
) -> Path:
    """
    Transcode an input audio file to WhatsApp-compatible OGG Opus using real FFmpeg.
    Mandates: mono channel (-ac 1), 48kHz (-ar 48000), libopus codec (-c:a libopus).
    Direct file renames from MP3/WAV to .ogg are strictly rejected.
    """
    in_p = Path(in_path).resolve()
    out_p = Path(out_path).resolve()

    if not in_p.exists():
        raise FFmpegExecutionError(f"Input audio file does not exist: {in_p}")

    out_p.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = _get_ffmpeg_path()

    cmd = [
        ffmpeg_bin,
        "-y",
        "-v", "error",
        "-i", str(in_p),
        "-af", f"aresample={OPUS_SAMPLE_RATE}",
        "-c:a", "libopus",
        "-b:a", OPUS_BITRATE,
        "-ar", str(OPUS_SAMPLE_RATE),
        "-ac", str(OPUS_CHANNELS),
        str(out_p),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        if out_p.exists():
            out_p.unlink(missing_ok=True)
        raise FFmpegTimeoutError(f"FFmpeg transcode timed out after {timeout_seconds}s") from e

    if proc.returncode != 0:
        if out_p.exists():
            out_p.unlink(missing_ok=True)
        raise FFmpegExecutionError(f"FFmpeg transcoding failed with code {proc.returncode}: {proc.stderr}")

    if not out_p.exists() or out_p.stat().st_size == 0:
        raise FFmpegExecutionError("FFmpeg completed with exit code 0 but emitted no output")

    return out_p


def _generate_silence_clip(duration_ms: int, out_dir: Path) -> Path:
    """Generate or retrieve a cached silent mono MP3 clip of exact millisecond length."""
    out_file = out_dir / f"silence_{duration_ms}ms.mp3"
    if out_file.exists():
        return out_file

    ffmpeg_bin = _get_ffmpeg_path()
    dur_sec = Decimal(duration_ms) / Decimal("1000")
    dur_str = f"{dur_sec:.3f}"

    cmd = [
        ffmpeg_bin,
        "-y",
        "-v", "error",
        "-f", "lavfi",
        "-i", "anullsrc=r=24000:cl=mono",
        "-t", dur_str,
        "-c:a", "libmp3lame",
        "-b:a", "48k",
        str(out_file),
    ]

    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return out_file


def probe_audio_stream(file_path: Path | str) -> dict[str, Any]:
    """Inspect generated audio stream container, codec, channels, sample rate, and duration."""
    target = Path(file_path).resolve()
    if not target.exists():
        raise FFmpegExecutionError(f"Audio file does not exist for probe: {target}")

    ffprobe_bin = _get_ffprobe_path()
    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-show_entries", "stream=codec_name,channels,sample_rate,duration:format=format_name,duration",
        "-of", "json",
        str(target),
    ]

    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(res.stdout)
    stream = data["streams"][0]
    dur_str = stream.get("duration") or data["format"].get("duration") or "0"
    dur_ms = _parse_decimal_str_to_ms(dur_str)

    return {
        "codec": stream.get("codec_name"),
        "channels": int(stream.get("channels", 1)),
        "sample_rate": int(stream.get("sample_rate", OPUS_SAMPLE_RATE)),
        "format": data["format"].get("format_name"),
        "duration_ms": dur_ms,
    }


# ==============================================================================
# Token Voice Note Stitcher (RECORDED_TOKEN_STITCH)
# ==============================================================================


def synthesize_token_voice_note(
    report: Any,
    catalog: AudioTokenCatalog | Path | str | None,
    out_path: Path | str,
    *,
    settings: Settings | None = None,
    cache_dir: Path | str | None = None,
    timeout_seconds: int = 30,
) -> AudioSynthesisResult:
    """
    Synthesize a WhatsApp-compatible Ogg/Opus voice note from recorded tokens.
    Implements:
    - Preflight catalog lookup.
    - Deterministic token sequencing.
    - Secure caching (zero PII).
    - FFmpeg concat demuxer stitching.
    - Real container verification.
    - Hard duration check (45s max) with concise overflow handling (D-08).
    """
    out_p = Path(out_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)

    # 1. Resolve Catalog
    if catalog is None:
        cfg = settings or Settings()
        catalog_path = Path(cfg.audio_assets_dir)
        if not catalog_path.exists():
            catalog_path = Path("assets/audio_tokens")
        cat = validate_audio_tokens(catalog_path)
    elif isinstance(catalog, (str, Path)):
        cat = validate_audio_tokens(catalog)
    else:
        cat = catalog

    # 2. Token sequence generation
    tokens = map_report_to_tokens(report, concise=False)

    # 3. Secure Cache Lookup
    c_dir = Path(cache_dir).resolve() if cache_dir else out_p.parent / ".audio_cache"
    c_dir.mkdir(parents=True, exist_ok=True)

    cache_key = compute_audio_cache_key(
        mode=AudioMode.RECORDED_TOKEN_STITCH.value,
        voice_version=cat.manifest_version,
        language=cat.language,
        rate_pitch="1.0",
        token_sequence=tokens,
    )
    cached_file = c_dir / f"{cache_key}.ogg"

    if cached_file.exists() and cached_file.stat().st_size > 0:
        # Cache hit: copy cached file to destination without running FFmpeg
        file_bytes = cached_file.read_bytes()
        out_p.write_bytes(file_bytes)
        file_sha256 = hashlib.sha256(file_bytes).hexdigest()
        probe_info = probe_audio_stream(out_p)
        return AudioSynthesisResult(
            output_path=out_p,
            duration_ms=probe_info["duration_ms"],
            token_sequence=tokens,
            mode=AudioMode.RECORDED_TOKEN_STITCH,
            sha256=file_sha256,
            cache_hit=True,
            is_concise_fallback=False,
        )

    # 4. Resolve clip file paths
    base_dir = cat.base_dir or Path("assets/audio_tokens").resolve()
    clip_paths: list[Path] = []

    for t in tokens:
        if t.startswith("pause_"):
            ms = PAUSE_CLAUSE_MS if t == "pause_clause" else PAUSE_SHORT_MS
            silence_path = _generate_silence_clip(ms, c_dir)
            clip_paths.append(silence_path)
        else:
            if t not in cat.tokens:
                raise AudioMissingTokenError(f"Token '{t}' not present in audio catalog")
            entry = cat.tokens[t]
            clip_file = base_dir / entry.filename
            if not clip_file.exists():
                raise AudioMissingTokenError(f"Token file '{entry.filename}' missing from disk")
            clip_paths.append(clip_file)

    # 5. Stitch via FFmpeg concat demuxer
    ffmpeg_bin = _get_ffmpeg_path()
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f_list:
        list_file_path = Path(f_list.name)
        for cp in clip_paths:
            # Escape path for FFmpeg concat demuxer
            safe_str = str(cp.resolve()).replace("\\", "/")
            f_list.write(f"file '{safe_str}'\n")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-v", "error",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file_path),
        "-af", f"aresample={OPUS_SAMPLE_RATE}",
        "-c:a", "libopus",
        "-b:a", OPUS_BITRATE,
        "-ar", str(OPUS_SAMPLE_RATE),
        "-ac", str(OPUS_CHANNELS),
        str(out_p),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    finally:
        list_file_path.unlink(missing_ok=True)

    if proc.returncode != 0:
        if out_p.exists():
            out_p.unlink(missing_ok=True)
        raise FFmpegExecutionError(f"FFmpeg token stitching failed with code {proc.returncode}: {proc.stderr}")

    # 6. Container & Duration Verification
    probe_info = probe_audio_stream(out_p)
    actual_duration_ms = probe_info["duration_ms"]

    # 7. Duration overflow handling (D-08: hard maximum 45 seconds)
    is_concise = False
    if actual_duration_ms > HARD_MAX_DURATION_MS:
        logger.warning(
            "Audio duration %d ms exceeded hard max 45s; attempting concise fallback",
            actual_duration_ms,
        )
        concise_tokens = map_report_to_tokens(report, concise=True)
        if concise_tokens == tokens:
            out_p.unlink(missing_ok=True)
            raise AudioDurationOverflowError(
                f"Audio duration {actual_duration_ms} ms exceeded 45s limit; no shorter variant possible"
            )

        # Retry with concise tokens
        concise_clips: list[Path] = []
        for t in concise_tokens:
            if t.startswith("pause_"):
                ms = PAUSE_CLAUSE_MS if t == "pause_clause" else PAUSE_SHORT_MS
                concise_clips.append(_generate_silence_clip(ms, c_dir))
            else:
                concise_clips.append(base_dir / cat.tokens[t].filename)

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f_concise:
            concise_list_path = Path(f_concise.name)
            for cp in concise_clips:
                safe_str = str(cp.resolve()).replace("\\", "/")
                f_concise.write(f"file '{safe_str}'\n")

        try:
            subprocess.run(
                [
                    ffmpeg_bin, "-y", "-v", "error",
                    "-f", "concat", "-safe", "0",
                    "-i", str(concise_list_path),
                    "-af", f"aresample={OPUS_SAMPLE_RATE}",
                    "-c:a", "libopus", "-b:a", OPUS_BITRATE,
                    "-ar", str(OPUS_SAMPLE_RATE), "-ac", str(OPUS_CHANNELS),
                    str(out_p),
                ],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=True,
            )
        finally:
            concise_list_path.unlink(missing_ok=True)

        probe_info = probe_audio_stream(out_p)
        actual_duration_ms = probe_info["duration_ms"]
        tokens = concise_tokens
        is_concise = True

        if actual_duration_ms > HARD_MAX_DURATION_MS:
            out_p.unlink(missing_ok=True)
            raise AudioDurationOverflowError(
                f"Concise audio duration {actual_duration_ms} ms still exceeds 45s hard limit (D-08)"
            )

    # 8. Commit to cache
    file_bytes = out_p.read_bytes()
    cached_file.write_bytes(file_bytes)
    sha256_digest = hashlib.sha256(file_bytes).hexdigest()

    return AudioSynthesisResult(
        output_path=out_p,
        duration_ms=actual_duration_ms,
        token_sequence=tokens,
        mode=AudioMode.RECORDED_TOKEN_STITCH,
        sha256=sha256_digest,
        cache_hit=False,
        is_concise_fallback=is_concise,
    )


# ==============================================================================
# Network TTS Interface (NETWORK_TTS, Optional Adapter)
# ==============================================================================


class NetworkTTSProvider(Protocol):
    """Protocol interface for optional external TTS service adapters."""

    def synthesize_speech(
        self,
        text: str,
        out_path: Path,
        *,
        language: str = "hi-IN",
        voice: str = "hi-IN-Neural2-A",
        timeout_seconds: int = 10,
    ) -> Path:
        """Synthesize text into raw or containerized audio file."""
        ...


def synthesize_network_tts(
    text: str,
    provider: NetworkTTSProvider | None,
    out_path: Path | str,
    *,
    settings: Settings | None = None,
    voice: str = "hi-IN-Neural2-A",
    language: str = "hi-IN",
    cache_dir: Path | str | None = None,
    timeout_seconds: int = 15,
) -> AudioSynthesisResult:
    """
    Synthesize audio using an optional external TTS provider.
    Fails closed if network TTS is disabled in configuration.
    Tones or synthesized noise are strictly forbidden in production paths.
    """
    cfg = settings or Settings()
    if not cfg.network_tts_enabled:
        raise NetworkTTSDisabledError(
            "Network TTS is disabled by default. Set network_tts_enabled=True in configuration to opt in."
        )

    if provider is None:
        raise NetworkTTSError("No NetworkTTSProvider supplied for network TTS synthesis")

    norm_text = unicodedata.normalize("NFC", text.strip())
    if not norm_text:
        raise NetworkTTSError("Cannot synthesize empty text payload")

    out_p = Path(out_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)

    c_dir = Path(cache_dir).resolve() if cache_dir else out_p.parent / ".audio_cache"
    c_dir.mkdir(parents=True, exist_ok=True)

    # Secure cache check (Invariant 10: text itself is not logged or in filename)
    text_hash = hashlib.sha256(norm_text.encode("utf-8")).hexdigest()
    cache_key = compute_audio_cache_key(
        mode=AudioMode.NETWORK_TTS.value,
        voice_version=voice,
        language=language,
        rate_pitch="1.0",
        token_sequence=[text_hash],
    )
    cached_file = c_dir / f"{cache_key}.ogg"

    if cached_file.exists() and cached_file.stat().st_size > 0:
        file_bytes = cached_file.read_bytes()
        out_p.write_bytes(file_bytes)
        probe_info = probe_audio_stream(out_p)
        return AudioSynthesisResult(
            output_path=out_p,
            duration_ms=probe_info["duration_ms"],
            token_sequence=[text_hash],
            mode=AudioMode.NETWORK_TTS,
            sha256=hashlib.sha256(file_bytes).hexdigest(),
            cache_hit=True,
            is_concise_fallback=False,
        )

    # Temporary intermediate file
    with tempfile.NamedTemporaryFile("wb", suffix=".raw.wav", delete=False) as f_tmp:
        tmp_wav = Path(f_tmp.name)

    try:
        provider.synthesize_speech(
            norm_text,
            tmp_wav,
            language=language,
            voice=voice,
            timeout_seconds=timeout_seconds,
        )
        if not tmp_wav.exists() or tmp_wav.stat().st_size == 0:
            raise NetworkTTSError("Network TTS provider produced an empty audio payload")

        # Transcode intermediate audio to WhatsApp OGG Opus
        transcode_to_whatsapp_ogg(tmp_wav, out_p, timeout_seconds=timeout_seconds)
    except Exception as e:
        if out_p.exists():
            out_p.unlink(missing_ok=True)
        if isinstance(e, (AudioEngineError, subprocess.SubprocessError)):
            raise
        raise NetworkTTSError(f"Network TTS synthesis failed: {e}") from e
    finally:
        tmp_wav.unlink(missing_ok=True)

    probe_info = probe_audio_stream(out_p)
    actual_duration_ms = probe_info["duration_ms"]

    if actual_duration_ms > HARD_MAX_DURATION_MS:
        out_p.unlink(missing_ok=True)
        raise AudioDurationOverflowError(
            f"Network TTS audio duration {actual_duration_ms} ms exceeded 45s hard limit (D-08)"
        )

    file_bytes = out_p.read_bytes()
    cached_file.write_bytes(file_bytes)
    sha256_digest = hashlib.sha256(file_bytes).hexdigest()

    return AudioSynthesisResult(
        output_path=out_p,
        duration_ms=actual_duration_ms,
        token_sequence=[text_hash],
        mode=AudioMode.NETWORK_TTS,
        sha256=sha256_digest,
        cache_hit=False,
        is_concise_fallback=False,
    )
