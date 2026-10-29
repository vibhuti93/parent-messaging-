"""
Gate 7 Test Suite: Hindi Audio Engine (`tests/test_stage7_audio_engine.py`).

Verifies:
1. Real FFmpeg stitching and OGG/Opus container headers (OggS, OpusHead, 48kHz mono).
2. Golden report fact matching (STU_01 score/deductions, STU_17 absence, EDGE_ALL_WRONG negative net).
3. Invariant 10 privacy hygiene: zero child names, roll numbers, or message text in cache keys/paths.
4. Secure caching and cache hit invariants.
5. Fail-closed paths: missing tokens, corrupted files, missing FFmpeg, non-zero exits, timeouts.
6. Duration overflow handling (D-08 hard 45s limit, concise fallback).
7. Network TTS opt-in provider interface and offline execution.
8. Human listening verification checklist presence in recording sheet.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from omr_dispatch.audio_engine import (
    OPUS_CHANNELS,
    OPUS_SAMPLE_RATE,
    TARGET_MAX_DURATION_MS,
    TARGET_MIN_DURATION_MS,
    AudioDurationOverflowError,
    AudioMissingTokenError,
    AudioMode,
    AudioPreflightValidationError,
    FFmpegExecutionError,
    FFmpegTimeoutError,
    NetworkTTSDisabledError,
    NetworkTTSError,
    map_report_to_tokens,
    number_to_tokens,
    probe_audio_stream,
    synthesize_network_tts,
    synthesize_token_voice_note,
    transcode_to_whatsapp_ogg,
    validate_audio_tokens,
)
from omr_dispatch.config import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIO_TOKENS_DIR = REPO_ROOT / "assets" / "audio_tokens"
GOLDEN_REPORTS_FILE = REPO_ROOT / "fixtures" / "golden" / "expected_reports.json"
EDGE_CASES_FILE = REPO_ROOT / "fixtures" / "golden" / "edge_cases.json"


@pytest.fixture(scope="module")
def audio_catalog():
    """Load and validate the real audio token catalog once for test suite."""
    return validate_audio_tokens(AUDIO_TOKENS_DIR)


@pytest.fixture(scope="module")
def golden_reports_data():
    """Load approved golden reports."""
    return json.loads(GOLDEN_REPORTS_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def edge_cases_data():
    """Load approved edge cases."""
    return json.loads(EDGE_CASES_FILE.read_text(encoding="utf-8"))


# ==============================================================================
# 1. Preflight Validation Tests
# ==============================================================================


@pytest.mark.audio
def test_validate_audio_tokens_catalog_success(audio_catalog):
    """Verify all 107 tokens are validated against manifest.json with matching hashes."""
    assert audio_catalog.token_count == 107
    assert len(audio_catalog.tokens) == 107
    assert "num_00" in audio_catalog.tokens
    assert "num_100" in audio_catalog.tokens
    assert "w_greeting" in audio_catalog.tokens
    assert "w_aapke_bachche" in audio_catalog.tokens
    assert "w_kul_number" in audio_catalog.tokens
    assert "w_mein_se" in audio_catalog.tokens
    assert "w_minus" in audio_catalog.tokens
    assert "w_sau" in audio_catalog.tokens


@pytest.mark.audio
def test_validate_audio_tokens_missing_file_fails(tmp_path):
    """Missing required token file fails loudly with AudioMissingTokenError."""
    # Create incomplete catalog dir
    manifest_src = AUDIO_TOKENS_DIR / "manifest.json"
    dest_manifest = tmp_path / "manifest.json"
    dest_manifest.write_text(manifest_src.read_text(encoding="utf-8"), encoding="utf-8")
    # No audio files copied -> missing tokens
    with pytest.raises(AudioMissingTokenError, match="missing from disk"):
        validate_audio_tokens(tmp_path)


@pytest.mark.audio
def test_validate_audio_tokens_corrupted_file_fails(tmp_path):
    """Corrupted audio token file fails hash validation."""
    # Copy manifest and create corrupted file
    manifest_src = AUDIO_TOKENS_DIR / "manifest.json"
    (tmp_path / "manifest.json").write_text(manifest_src.read_text(encoding="utf-8"), encoding="utf-8")
    for f in AUDIO_TOKENS_DIR.glob("*.mp3"):
        (tmp_path / f.name).write_bytes(f.read_bytes())

    # Corrupt one token
    (tmp_path / "num_00.mp3").write_bytes(b"\xff\xf3corrupted_bytes_for_testing")

    with pytest.raises(AudioPreflightValidationError, match="SHA-256 hash mismatch"):
        validate_audio_tokens(tmp_path)


# ==============================================================================
# 2. Token Grammar & Fact Mapping Tests
# ==============================================================================


@pytest.mark.audio
def test_number_to_tokens_bounds():
    """Verify integer number token conversions across all ranges."""
    assert number_to_tokens(0) == ["num_00"]
    assert number_to_tokens(7) == ["num_07"]
    assert number_to_tokens(55) == ["num_55"]
    assert number_to_tokens(100) == ["num_100"]
    assert number_to_tokens(300) == ["num_03", "w_sau"]
    assert number_to_tokens(-5) == ["w_minus", "num_05"]
    assert number_to_tokens(-75) == ["w_minus", "num_75"]


@pytest.mark.audio
def test_golden_report_stu01_token_mapping(golden_reports_data):
    """
    Assert token sequence for STU_01 matches expected score and deductions:
    Net 55 / 300, 25 marks deducted (bleed), gender-neutral 'आपके बच्चे'.
    """
    stu01 = next(s for s in golden_reports_data["student_reports"] if s["student_id"] == "STU_01")
    tokens = map_report_to_tokens(stu01)

    expected = [
        "w_greeting",
        "pause_clause",
        "w_aapke_bachche",
        "pause_short",
        "w_kul_number",
        "num_03",
        "w_sau",
        "w_mein_se",
        "pause_short",
        "num_55",
        "pause_clause",
        "w_minus",
        "num_25",
    ]
    assert tokens == expected

    # Invariant 10: child name 'आरव' and roll '01' must never be in spoken tokens
    assert "आरव" not in tokens
    assert "01" not in tokens
    assert "num_01" not in tokens  # roll number is 01, must not appear


@pytest.mark.audio
def test_golden_report_stu17_absence_token_mapping(golden_reports_data):
    """
    Assert token sequence for STU_17 (ABSENT):
    Stitch neutral absence facts (300 max, 16 present); zero score is NEVER uttered.
    """
    stu17 = next(s for s in golden_reports_data["student_reports"] if s["student_id"] == "STU_17")
    tokens = map_report_to_tokens(stu17)

    expected = [
        "w_greeting",
        "pause_clause",
        "w_aapke_bachche",
        "pause_short",
        "w_kul_number",
        "num_03",
        "w_sau",
        "pause_clause",
        "num_16",
    ]
    assert tokens == expected

    # Invariant 10 & D-08: Zero score must NEVER be included for absent students
    assert "num_00" not in tokens
    assert "w_minus" not in tokens


@pytest.mark.audio
def test_edge_case_negative_net_token_mapping(edge_cases_data):
    """Assert negative net score edge case maps to 'w_minus' + number."""
    all_wrong = edge_cases_data["all_wrong_student"]
    tokens = map_report_to_tokens(all_wrong)

    assert "w_minus" in tokens
    assert "num_75" in tokens
    assert "num_03" in tokens  # 300 max
    assert "w_sau" in tokens


# ==============================================================================
# 3. Real FFmpeg Stitching & OGG/Opus Inspection Tests
# ==============================================================================


@pytest.mark.audio
def test_synthesize_real_audio_stu01_container_and_stream(audio_catalog, golden_reports_data, tmp_path):
    """
    Synthesize real STU_01 voice note with FFmpeg and inspect stream properties:
    - OGG container header ('OggS').
    - Opus identification header ('OpusHead').
    - ffprobe: codec=opus, channels=1, sample_rate=48000, duration within target 15-25s.
    """
    stu01 = next(s for s in golden_reports_data["student_reports"] if s["student_id"] == "STU_01")
    out_file = tmp_path / "stu01_voice.ogg"

    result = synthesize_token_voice_note(stu01, audio_catalog, out_file)

    assert result.output_path == out_file
    assert out_file.exists()
    assert out_file.stat().st_size > 0

    # 1. Container Byte Header Verification
    file_bytes = out_file.read_bytes()
    assert file_bytes[:4] == b"OggS", "Output file must begin with OGG capture pattern 'OggS'"
    assert b"OpusHead" in file_bytes[:128], "Output file must contain 'OpusHead' identification header"

    # 2. ffprobe Inspection
    stream_info = probe_audio_stream(out_file)
    assert stream_info["codec"] == "opus"
    assert stream_info["channels"] == OPUS_CHANNELS  # 1 (mono)
    assert stream_info["sample_rate"] == OPUS_SAMPLE_RATE  # 48000 Hz
    assert stream_info["format"] == "ogg"

    # 3. Duration Bounds Verification (Target: 15–25 seconds)
    assert TARGET_MIN_DURATION_MS <= result.duration_ms <= TARGET_MAX_DURATION_MS
    assert result.duration_ms == stream_info["duration_ms"]
    assert not result.cache_hit
    assert not result.is_concise_fallback


@pytest.mark.audio
def test_transcode_to_whatsapp_ogg_real_conversion(tmp_path):
    """Verify transcode_to_whatsapp_ogg converts input audio to valid mono Opus OGG."""
    sample_mp3 = AUDIO_TOKENS_DIR / "num_55.mp3"
    out_ogg = tmp_path / "num_55_transcoded.ogg"

    res_path = transcode_to_whatsapp_ogg(sample_mp3, out_ogg)
    assert res_path == out_ogg
    assert out_ogg.exists()

    file_bytes = out_ogg.read_bytes()
    assert file_bytes.startswith(b"OggS")
    assert b"OpusHead" in file_bytes[:100]

    stream_info = probe_audio_stream(out_ogg)
    assert stream_info["codec"] == "opus"
    assert stream_info["channels"] == 1
    assert stream_info["sample_rate"] == 48000


@pytest.mark.audio
def test_direct_mp3_rename_to_ogg_fails_container_inspection(tmp_path):
    """
    Prove that renaming an MP3 to .ogg does NOT produce a valid Opus OGG file.
    (Catches Mutation 1).
    """
    fake_ogg = tmp_path / "fake.ogg"
    sample_mp3 = AUDIO_TOKENS_DIR / "num_00.mp3"
    fake_ogg.write_bytes(sample_mp3.read_bytes())  # Direct rename/copy without FFmpeg

    file_bytes = fake_ogg.read_bytes()
    # MP3 bytes do not start with 'OggS'
    assert not file_bytes.startswith(b"OggS"), "Renamed MP3 must not have OGG header"
    assert b"OpusHead" not in file_bytes, "Renamed MP3 must not have OpusHead"

    # ffprobe probe detects MP3 codec, not opus
    stream_info = probe_audio_stream(fake_ogg)
    assert stream_info["codec"] != "opus", "Directly renamed MP3 must not register as opus codec"


# ==============================================================================
# 4. Privacy & Secure Caching Invariants (Invariant 10)
# ==============================================================================


@pytest.mark.audio
def test_cache_keys_and_paths_have_zero_pii(audio_catalog, tmp_path):
    """
    Invariant 10: Cache keys, cache filenames, and paths must contain ZERO student names,
    roll numbers, or raw message text. (Catches Mutation 2).
    """
    cache_dir = tmp_path / ".secure_cache"
    out_file = tmp_path / "output.ogg"

    # Report with explicit student PII
    report_with_pii = {
        "student_id": "STU_01",
        "child_display_name": "आरव",
        "class_section": "कक्षा 10-A",
        "roll_number": "01",
        "message_text": "प्रिय अभिभावक, आरव (कक्षा 10-A)...",
        "status": "PRESENT",
        "net_marks": 55,
        "max_marks": 300,
        "bleed_marks": 25,
    }

    result = synthesize_token_voice_note(
        report_with_pii,
        audio_catalog,
        out_file,
        cache_dir=cache_dir,
    )
    assert result.output_path == out_file

    # Inspect all cached files
    cached_files = list(cache_dir.glob("*.ogg"))
    assert len(cached_files) == 1
    cache_name = cached_files[0].name

    # Cache filename must be strictly a 64-character SHA-256 hex digest + .ogg
    assert re.match(r"^[0-9a-f]{64}\.ogg$", cache_name), f"Invalid cache name format: {cache_name}"

    # Verify zero PII in filename or path
    for banned in ["आरव", "01", "10-A", "STU_01"]:
        assert banned not in cache_name
        assert banned not in str(cached_files[0])


@pytest.mark.audio
def test_cache_hit_avoids_second_synthesis(audio_catalog, tmp_path, monkeypatch):
    """Verify that a second call with identical report facts hits cache without FFmpeg."""
    report = {"status": "PRESENT", "net_marks": 40, "max_marks": 100}
    out_file1 = tmp_path / "out1.ogg"
    out_file2 = tmp_path / "out2.ogg"
    cache_dir = tmp_path / ".cache"

    # First synthesis (miss)
    res1 = synthesize_token_voice_note(report, audio_catalog, out_file1, cache_dir=cache_dir)
    assert not res1.cache_hit

    # Spy on subprocess.run: ffmpeg should NOT be called on cache hit
    original_run = subprocess.run
    calls = []

    def recording_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args")
        calls.append(cmd)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", recording_run)

    # Second synthesis (hit)
    res2 = synthesize_token_voice_note(report, audio_catalog, out_file2, cache_dir=cache_dir)
    assert res2.cache_hit
    assert res2.sha256 == res1.sha256

    # Verify no ffmpeg synthesis command was executed during cache hit
    for cmd in calls:
        cmd_str = " ".join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
        assert "-f concat" not in cmd_str, f"FFmpeg concat executed on cache hit: {cmd_str}"


# ==============================================================================
# 5. Resilience & Fail-Closed Paths
# ==============================================================================


@pytest.mark.audio
def test_missing_ffmpeg_binary_fails_closed(audio_catalog, tmp_path, monkeypatch):
    """Missing FFmpeg binary raises FFmpegExecutionError and produces no output."""
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    report = {"status": "PRESENT", "net_marks": 50, "max_marks": 100}
    out_file = tmp_path / "out_no_ffmpeg.ogg"

    with pytest.raises(FFmpegExecutionError, match="FFmpeg binary not found"):
        synthesize_token_voice_note(report, audio_catalog, out_file)

    assert not out_file.exists()


@pytest.mark.audio
def test_ffmpeg_non_zero_exit_fails_closed_and_removes_partial_file(audio_catalog, tmp_path, monkeypatch):
    """
    FFmpeg non-zero exit triggers controlled failure and removes partial output.
    (Catches Mutation 3).
    """
    out_file = tmp_path / "failed_out.ogg"
    real_run = subprocess.run

    # Simulate FFmpeg failing with exit code 1
    def fake_failing_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        if "ffmpeg" in str(cmd[0]):
            # Create a partial file then return code 1
            out_file.write_bytes(b"partial_corrupt_data")
            return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="Simulated FFmpeg fatal error")
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_failing_run)

    report = {"status": "PRESENT", "net_marks": 50, "max_marks": 100}

    with pytest.raises(FFmpegExecutionError, match="FFmpeg token stitching failed with code 1"):
        synthesize_token_voice_note(report, audio_catalog, out_file)

    # Partial file must be deleted to avoid poison success
    assert not out_file.exists()


@pytest.mark.audio
def test_ffmpeg_timeout_fails_closed(tmp_path, monkeypatch):
    """FFmpeg subprocess timeout raises FFmpegTimeoutError and cleans up output."""
    sample_mp3 = AUDIO_TOKENS_DIR / "num_55.mp3"
    out_ogg = tmp_path / "timeout.ogg"

    def fake_timeout_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_timeout_run)

    with pytest.raises(FFmpegTimeoutError, match="timed out"):
        transcode_to_whatsapp_ogg(sample_mp3, out_ogg, timeout_seconds=1)

    assert not out_ogg.exists()


# ==============================================================================
# 6. Duration Overflow & Concise Fallback Tests (D-08)
# ==============================================================================


@pytest.mark.audio
def test_duration_overflow_triggers_concise_fallback(audio_catalog, tmp_path, monkeypatch):
    """
    When primary duration exceeds 45s, concise fallback is automatically triggered.
    """
    report = {"status": "PRESENT", "net_marks": 50, "max_marks": 100, "bleed_marks": 20}
    out_file = tmp_path / "overflow.ogg"

    # Simulate ffprobe returning 48000ms (48s > 45s hard max) on first pass,
    # and 20000ms (20s) on concise second pass
    probe_calls = {"count": 0}
    real_probe = probe_audio_stream

    def simulated_probe(path):
        probe_calls["count"] += 1
        res = real_probe(path)
        if probe_calls["count"] == 1:
            res["duration_ms"] = 48000  # Trigger overflow
        else:
            res["duration_ms"] = 20000  # Concise pass fits
        return res

    monkeypatch.setattr("omr_dispatch.audio_engine.probe_audio_stream", simulated_probe)

    result = synthesize_token_voice_note(report, audio_catalog, out_file)
    assert result.is_concise_fallback
    assert result.duration_ms == 20000
    assert "w_minus" not in result.token_sequence  # bleed deductions stripped in concise mode


@pytest.mark.audio
def test_duration_overflow_unresolvable_raises_error(audio_catalog, tmp_path, monkeypatch):
    """
    When duration exceeds 45s and concise variant STILL exceeds 45s,
    AudioDurationOverflowError is raised per D-08. (Catches Mutation 4).
    """
    report = {"status": "PRESENT", "net_marks": 50, "max_marks": 100}
    out_file = tmp_path / "unresolvable_overflow.ogg"

    # Simulate both passes exceeding 45s
    def always_over_probe(path):
        res = probe_audio_stream(path)
        res["duration_ms"] = 52000  # 52s
        return res

    monkeypatch.setattr("omr_dispatch.audio_engine.probe_audio_stream", always_over_probe)

    with pytest.raises(AudioDurationOverflowError, match="exceeded 45s limit"):
        synthesize_token_voice_note(report, audio_catalog, out_file)

    assert not out_file.exists()


# ==============================================================================
# 7. Network TTS Interface & Offline Safety Tests
# ==============================================================================


@pytest.mark.audio
def test_network_tts_disabled_by_default(tmp_path):
    """Network TTS fails closed when disabled in settings (default safe switch)."""
    cfg = Settings(network_tts_enabled=False)
    out_file = tmp_path / "tts.ogg"

    with pytest.raises(NetworkTTSDisabledError, match="Network TTS is disabled by default"):
        synthesize_network_tts("कुछ पाठ", provider=None, out_path=out_file, settings=cfg)


@pytest.mark.audio
def test_network_tts_with_mock_provider(tmp_path):
    """
    Verify NetworkTTSProvider interface works when explicitly opted-in,
    and properly transcodes intermediate output to WhatsApp mono Opus OGG.
    """
    cfg = Settings(network_tts_enabled=True)
    out_file = tmp_path / "tts_success.ogg"

    class MockTTSProvider:
        def synthesize_speech(self, text: str, out_path: Path, **kwargs) -> Path:
            # Emit a real mono MP3 as intermediate payload
            sample_mp3 = AUDIO_TOKENS_DIR / "w_greeting.mp3"
            out_path.write_bytes(sample_mp3.read_bytes())
            return out_path

    res = synthesize_network_tts(
        "प्रिय अभिभावक",
        provider=MockTTSProvider(),
        out_path=out_file,
        settings=cfg,
    )

    assert res.mode == AudioMode.NETWORK_TTS
    assert out_file.exists()

    stream_info = probe_audio_stream(out_file)
    assert stream_info["codec"] == "opus"
    assert stream_info["channels"] == 1


@pytest.mark.audio
def test_network_tts_provider_failure_fails_closed(tmp_path):
    """Provider failure or timeout raises NetworkTTSError without leaving orphan file."""
    cfg = Settings(network_tts_enabled=True)
    out_file = tmp_path / "tts_fail.ogg"

    class FailingTTSProvider:
        def synthesize_speech(self, text: str, out_path: Path, **kwargs) -> Path:
            raise ConnectionError("Mock remote TTS endpoint timeout")

    with pytest.raises(NetworkTTSError, match="Network TTS synthesis failed"):
        synthesize_network_tts(
            "प्रिय अभिभावक",
            provider=FailingTTSProvider(),
            out_path=out_file,
            settings=cfg,
        )

    assert not out_file.exists()


# ==============================================================================
# 8. Human Listening Checklist Verification
# ==============================================================================


@pytest.mark.unit
def test_human_listening_checklist_documented():
    """Verify audio recording sheet contains the human listening verification checklist (W7)."""
    sheet_path = REPO_ROOT / "docs" / "audio_recording_sheet.md"
    assert sheet_path.exists(), "docs/audio_recording_sheet.md must exist"

    content = sheet_path.read_text(encoding="utf-8")
    for req in [
        "Pronunciation",
        "Smoothness",
        "Number Clarity",
        "Clipping",
        "Gender Neutrality",
    ]:
        assert req.lower() in content.lower(), f"Checklist item '{req}' missing from recording sheet"


@pytest.mark.unit
def test_synthetic_pause_provisioning_in_manifest_and_sheet(audio_catalog):
    """Verify synthetic pause provisioning is documented in manifest.json and recording sheet."""
    assert audio_catalog.synthetic_pause_provisioning is not None
    assert audio_catalog.synthetic_pause_provisioning["mechanism"] == "deterministic_ffmpeg_lavfi"
    assert "pause_short" in audio_catalog.synthetic_pause_provisioning["tokens"]

    sheet_path = REPO_ROOT / "docs" / "audio_recording_sheet.md"
    sheet_content = sheet_path.read_text(encoding="utf-8")
    assert "Synthetic Silence Provisioning" in sheet_content
    assert "anullsrc" in sheet_content


@pytest.mark.audio
def test_format_token_sequence_transcript_golden_cases(audio_catalog, golden_reports_data, edge_cases_data):
    """Verify exact Hindi word-by-word transcripts generated for STU_01, STU_17, and EDGE_ALL_WRONG."""
    from omr_dispatch.audio_engine import format_token_sequence_transcript

    # STU_01 (Present)
    stu01 = next(s for s in golden_reports_data["student_reports"] if s["student_id"] == "STU_01")
    tokens_stu01 = map_report_to_tokens(stu01)
    transcript_stu01 = format_token_sequence_transcript(tokens_stu01, audio_catalog)
    assert transcript_stu01 == "प्रिय अभिभावक ... आपके बच्चे ... कुल नंबर तीन सौ में से ... पचपन ... माइनस पच्चीस"

    # STU_17 (Absent)
    stu17 = next(s for s in golden_reports_data["student_reports"] if s["student_id"] == "STU_17")
    tokens_stu17 = map_report_to_tokens(stu17)
    transcript_stu17 = format_token_sequence_transcript(tokens_stu17, audio_catalog)
    assert transcript_stu17 == "प्रिय अभिभावक ... आपके बच्चे ... कुल नंबर तीन सौ ... सोलह"
    assert "शून्य" not in transcript_stu17  # Absent student never framed with zero score

    # EDGE_ALL_WRONG (Negative net score)
    edge_wrong = edge_cases_data["all_wrong_student"]
    tokens_edge = map_report_to_tokens(edge_wrong)
    transcript_edge = format_token_sequence_transcript(tokens_edge, audio_catalog)
    assert "माइनस पचहत्तर" in transcript_edge
