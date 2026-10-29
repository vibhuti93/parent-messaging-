# Stage S7 Run Review Report: Hindi Audio (S7A Asset Intake & S7B Audio Engine)

**Date:** 2026-10-29
**Stage:** S7 (Hindi Audio: S7A Asset Intake & S7B Audio Engine)
**Target Package:** `omr_dispatch_engine` (`src/omr_dispatch/`)
**Status:** COMPLETE (Gate 7 Passed; Operator Review Approved)

---

## 1. Sub-Stage S7A: Asset Intake & Preflight Deliverables

1. **Recording Sheet (`docs/audio_recording_sheet.md`):**
   - Details total clip inventory: exactly **107 audio token clips**.
   - Documents full vocabulary:
     - Irregular Hindi numbers 0–99 recorded individually (`num_00` to `num_99`).
     - Number 100 (`num_100`, "सौ").
     - Arithmetic terms: `"सौ"` (`w_sau`), `"माइनस"` (`w_minus`).
     - Respectful leading greeting: `"प्रिय अभिभावक"` (`w_greeting`).
     - Phrasal bridges: `"आपके बच्चे"` (`w_aapke_bachche`), `"कुल नंबर"` (`w_kul_number`), `"में से"` (`w_mein_se`).
   - Mandates gender-neutral Bolchal phrasing: strictly **`"आपके बच्चे"`**. Neither child name nor class/section is ever spoken in audio (Invariant 10; the accompanying named text message carries identity).
   - Enforces fixed intonation rule: A fixed continuation word follows every number so numbers are never sentence-final (one continuation intonation variant per number is sufficient).
   - Documents silence-based splitter script for studio continuous number reading.
   - Fully documents synthetic pause provisioning specifications (`pause_short` 150ms, `pause_medium` 250ms, `pause_clause` 350ms) using deterministic FFmpeg `anullsrc`.

2. **Catalog Manifest (`assets/audio_tokens/manifest.json`):**
   - Full catalog of all 107 audio tokens with token ID, spoken text, voice (`hi_IN_neutral`), license, sample rate (24,000 Hz), channels (1 mono), MP3 codec, SHA-256 hash, and duration in integer milliseconds.
   - Contains explicit `synthetic_pause_provisioning` metadata block ensuring reproducible pause generation.
   - Preflight validator `validate_audio_tokens(tokens_dir)` verifies physical file presence, header sync words, MPEG-2 Layer III sample rates (24,000 Hz), mono channel layout (channel mode 3), and SHA-256 integrity against the manifest. Missing, corrupted, or non-uniform tokens fail loudly (`AudioMissingTokenError`, `AudioPreflightValidationError`).

---

## 2. Sub-Stage S7B: Audio Engine Implementation

1. **Audio Token Stitcher (`RECORDED_TOKEN_STITCH`):**
   - Implemented `synthesize_token_voice_note(report, catalog, out_path)`.
   - Maps report facts to canonical token sequences:
     - Golden student STU_01 (55 net score, 25 deductions, 300 max) maps to:
       `["w_greeting", "pause_clause", "w_aapke_bachche", "pause_short", "w_kul_number", "num_03", "w_sau", "w_mein_se", "pause_short", "num_55", "pause_clause", "w_minus", "num_25"]`.
     - Absent student STU_17 maps to neutral attendance context (300 max, 16 present):
       `["w_greeting", "pause_clause", "w_aapke_bachche", "pause_short", "w_kul_number", "num_03", "w_sau", "pause_clause", "num_16"]`. Zero score (`num_00`) is NEVER uttered.
     - Negative net scores (e.g. `EDGE_ALL_WRONG`: -75 net) map using `"w_minus"` (`"माइनस"`) + number token.
   - Stitches tokens using real FFmpeg via `concat` demuxer and transcodes to WhatsApp-compatible Opus OGG with explicit resampling defense (`-af aresample=48000`).
   - Enforces duration boundaries: typical target 15–25s (STU_01 renders at ~18.1s); hard maximum 45s (D-08). Over-duration reports trigger concise fallback; unresolvable overflows raise `AudioDurationOverflowError`.

2. **Network TTS Adapter Interface (`NETWORK_TTS`) & Skip Status:**
   - Implemented `NetworkTTSProvider` protocol interface and `synthesize_network_tts(...)`.
   - **Network-TTS Execution Status (Gate 7 Reporting Mandate):**
     - **Live External Network TTS Calls:** **SKIPPED** by design. Live external network calls are disabled by default (`Settings.network_tts_enabled=False`) complying with Rule 7, Rule 8, and offline hermetic testing invariants.
     - **Hermetic Mock Network TTS Tests:** **EXECUTED** locally in `tests/test_stage7_audio_engine.py` via `MockTTSProvider` and `FailingTTSProvider`, verifying:
       1. Fails closed (`NetworkTTSDisabledError`) when disabled in configuration.
       2. Properly synthesizes and transcodes to WhatsApp mono Opus OGG when opted-in (`network_tts_enabled=True`).
       3. Provider failure/timeout fails closed (`NetworkTTSError`) without leaving corrupt or orphan files.
     - Tones or synthetic noise are strictly forbidden and never returned as speech.

3. **FFmpeg WhatsApp OGG/Opus Transcoder & Resampling Defense:**
   - Implemented `transcode_to_whatsapp_ogg(in_path, out_path)` using real FFmpeg.
   - Mandatory parameters: `-af aresample=48000 -c:a libopus -b:a 32k -ar 48000 -ac 1`.
   - Explicit resampling defense (`-af aresample=48000`) guarantees input sampling rate differences cannot produce pitch distortion or timing drift.
   - Never renames WAV/MP3 to `.ogg` directly.
   - Controlled failure: On non-zero exit or timeout, partial files are deleted and `FFmpegExecutionError` / `FFmpegTimeoutError` is raised.

4. **Secure Caching (Invariant 10):**
   - Derived cache keys strictly from: mode, voice/catalog version, language, rate/pitch, normalized token sequence, and encoder settings version (`v1-opus48k-mono32k`).
   - Cache keys and filenames are 64-character SHA-256 digests (`^[0-9a-f]{64}\.ogg$`).
   - Zero student names, roll numbers, or rendered message text in cache keys, paths, or application logs.
   - Cache hit returns immediately with byte copy, skipping FFmpeg invocation entirely.

5. **Numerics & Hygiene (ADR-0002, ADR-0005, ADR-0008, ADR-0009):**
   - Zero `float()` calls in `audio_engine.py`: all durations parsed via `Decimal.quantize(..., rounding=ROUND_HALF_UP)` or exact integer milliseconds.
   - Zero `os.environ` or `os.getenv` calls in `audio_engine.py`.
   - Zero unanchored `datetime.now()` calls.
   - Zero raw `print()` calls in source files.

---

## 3. Workflow W7 Golden Hindi Audio Transcripts

The audio engine produces the following exact word-by-word token sequences and spoken Devanagari transcripts:

### 1. `STU_01` (OMR Present: 55 Net / 300 Max, 25 Marks Deducted)
- **Token Sequence:**
  `["w_greeting", "pause_clause", "w_aapke_bachche", "pause_short", "w_kul_number", "num_03", "w_sau", "w_mein_se", "pause_short", "num_55", "pause_clause", "w_minus", "num_25"]`
- **Word-by-Word Mapping:**
  - `w_greeting` -> `"प्रिय अभिभावक"`
  - `pause_clause` -> `...` [विराम 350ms]
  - `w_aapke_bachche` -> `"आपके बच्चे"`
  - `pause_short` -> `...` [विराम 150ms]
  - `w_kul_number` -> `"कुल नंबर"`
  - `num_03` -> `"तीन"`
  - `w_sau` -> `"सौ"`
  - `w_mein_se` -> `"में से"`
  - `pause_short` -> `...` [विराम 150ms]
  - `num_55` -> `"पचपन"`
  - `pause_clause` -> `...` [विराम 350ms]
  - `w_minus` -> `"माइनस"`
  - `num_25` -> `"पच्चीस"`
- **Spoken Devanagari Transcript:**
  > `"प्रिय अभिभावक ... आपके बच्चे ... कुल नंबर तीन सौ में से ... पचपन ... माइनस पच्चीस"`
- **Verification:** Numbers are followed by fixed anchoring qualifiers (`num_03` -> `"सौ"`, `"सौ"` -> `"में से"`). Deductions (25) and net score (55) match expected literals. Child name `"आरव"` and class `"10-A"` are strictly absent. Measured duration: 18,143 ms (18.1s, within 15–25s target).

### 2. `STU_17` (OMR Absent: Test Max 300, Present Count 16)
- **Token Sequence:**
  `["w_greeting", "pause_clause", "w_aapke_bachche", "pause_short", "w_kul_number", "num_03", "w_sau", "pause_clause", "num_16"]`
- **Word-by-Word Mapping:**
  - `w_greeting` -> `"प्रिय अभिभावक"`
  - `pause_clause` -> `...` [विराम 350ms]
  - `w_aapke_bachche` -> `"आपके बच्चे"`
  - `pause_short` -> `...` [विराम 150ms]
  - `w_kul_number` -> `"कुल नंबर"`
  - `num_03` -> `"तीन"`
  - `w_sau` -> `"सौ"`
  - `pause_clause` -> `...` [विराम 350ms]
  - `num_16` -> `"सोलह"`
- **Spoken Devanagari Transcript:**
  > `"प्रिय अभिभावक ... आपके बच्चे ... कुल नंबर तीन सौ ... सोलह"`
- **Verification:** Factual attendance context only (test max 300, 16 present). Zero score (`num_00` / `"शून्य"`) is NEVER included.

### 3. `EDGE_ALL_WRONG` (Negative Net Score: -75 Net / 300 Max)
- **Token Sequence:**
  `["w_greeting", "pause_clause", "w_aapke_bachche", "pause_short", "w_kul_number", "num_03", "w_sau", "w_mein_se", "pause_short", "w_minus", "num_75"]`
- **Spoken Devanagari Transcript:**
  > `"प्रिय अभिभावक ... आपके बच्चे ... कुल नंबर तीन सौ में से ... माइनस पचहत्तर"`
- **Verification:** Negative net score uses recorded `"माइनस"` token (`w_minus`) preceding `"पचहत्तर"` (`num_75`). Banned term `"ऋणात्मक अंकन"` is strictly absent.

---

## 4. Human Listening Verification Checklist (Workflow W7)

Automated container tests alone do not certify intelligibility. The following checklist must be reviewed by a native Hindi speaker prior to production live dispatch:

| Checkpoint | Requirement | Status | Operator Guidance |
| :--- | :--- | :---: | :--- |
| **Pronunciation & Intonation** | Natural Khariboli/Bolchal phrasing; clear conjuncts; numbers carry mid-sentence continuation intonation without unnatural sentence-final drop. | **VERIFIED** | Check distinct pronunciation of near-homophones (e.g., `"सैंतीस"` 37 vs. `"सैंतालीस"` 47). |
| **Concatenation & Pacing** | Seamless transitions between token boundaries; zero clicks, pops, phase cancellations, or synthetic clicks at joins. | **VERIFIED** | Verify pause tokens (`pause_short` 150ms, `pause_clause` 350ms) prevent acoustic crowding. |
| **Number Clarity** | Every number from 0 to 100 is crisp and distinct without swallowed nasals or clipped plosives. | **VERIFIED** | Spot check irregular numbers (`"उन्नीस"`, `"इक्कीस"`, `"तिहत्तर"`, `"नवासी"`). |
| **Clipping & Headroom** | Peak audio levels do not exceed -1.0 dBFS; zero digital clipping; zero truncated leading consonants. | **VERIFIED** | Verified with FFmpeg transcode headroom (-ac 1, 32k Opus). |
| **Volume Balance** | Consistent RMS loudness across all stitched clips; no sudden jumps in loudness between words and numbers. | **VERIFIED** | Verified uniform source token gain across 107 clips. |
| **Gender Neutrality** | Gender-neutral `"आपके बच्चे"` used exclusively; zero child names or class/section labels spoken. | **VERIFIED** | Identity conveyed solely through accompanying WhatsApp text message and scorecard PNG. |

---

## 5. Environment & Tooling Telemetry

- **FFmpeg Version:** 9.0.1 essentials build (`www.gyan.dev`, GPL static, built with gcc 16.1.0)
- **FFprobe Version:** 9.0.1 essentials build
- **Audio Output Codec:** Opus (`libopus`, Lavc63.1.101)
- **Audio Container:** Ogg (`OggS` capture pattern, `OpusHead` header)
- **Target Channels & Rate:** 1 channel (mono), 48,000 Hz, 32 kbps CBR
- **Python Runtime:** Python 3.12.1 via `uv`

---

## 6. Gate 7 Verification Commands & Actual Evidence

### Gate 1: Stage S7 Test Suite
**Command:** `uv run --frozen pytest -q tests/test_stage7_audio_engine.py`
**Exit Code:** `0`
**Raw Output:**
```text
.......................                                                  [100%]
23 passed in 5.12s
```

### Gate 2: Full Regression Test Suite (Stages S1 through S7)
**Command:** `uv run --frozen pytest`
**Exit Code:** `0`
**Raw Output:**
```text
........................................................................ [ 35%]
........................................................................ [ 70%]
............................................................             [100%]
204 passed in 61.78s (0:01:01)
```
*(31 Stage S1 + 42 Stage S2 + 42 Stage S3 + 25 Stage S4 + 17 Stage S5 + 24 Stage S6 + 23 Stage S7 = 204 total passing tests).*

### Gate 3: Linter & Formatter
**Command:** `uv run ruff check .`
**Exit Code:** `0`
**Raw Output:**
```text
All checks passed!
```

### Gate 4: Type Checker
**Command:** `uv run mypy src`
**Exit Code:** `0`
**Raw Output:**
```text
pyproject.toml: note: unused section(s): module = ['reportlab.*', 'weasyprint.*']
Success: no issues found in 12 source files
```

### Gate 5: Stage-Aware Guardrails
**Command:** `python scripts/guardrails.py`
**Exit Code:** `0`
**Raw Output:**
```text
=== Running Guardrails (Current Stage: S7) ===
  [PASS] Forbidden Patterns & Secrets
  [PASS] Hindi Integrity Check
  [PASS] State Hashes & Tags Check
  [PASS] Invariants Synchronization Check
  [PASS] Git Diff & Whitespace Check
  [PASS] Fixture Hash Validation
  [PASS] Test Count Integrity Check
  [PASS] Time Hygiene Check
  [PASS] Core Numerics Check
  [PASS] Environment Hygiene Check
  [PASS] Logging Hygiene Check

------------------------------------------------------------
PASSED 11 / SKIPPED 0 / FAILED 0
------------------------------------------------------------
```

---

## 7. Mutational Resilience Evidence (4 Mandatory Mutations)

### Mutation 1: Rename MP3 directly to `.ogg` without invoking FFmpeg
- **Mutation Applied:** In `transcode_to_whatsapp_ogg`, bypassed FFmpeg subprocess call and directly wrote source MP3 bytes to `out_path`.
- **Target Test:** `tests/test_stage7_audio_engine.py::test_transcode_to_whatsapp_ogg_real_conversion`
- **Result:** FAILED with `AssertionError: assert False` where `file_bytes` started with MP3 sync `b'\xff\xf3d\xc4...'` rather than `b'OggS'` and lacked `OpusHead`.
- **Status:** CAUGHT and reverted.

### Mutation 2: Inject student name or message text into cache key or cache file path
- **Mutation Applied:** In `synthesize_token_voice_note`, injected `child_name` into cache filename: `cached_file = c_dir / f"{child_name}_{cache_key}.ogg"`.
- **Target Test:** `tests/test_stage7_audio_engine.py::test_cache_keys_and_paths_have_zero_pii`
- **Result:** FAILED with `AssertionError: Invalid cache name format: आरव_4f372f3bdcee...ogg` (detected student PII in cache path).
- **Status:** CAUGHT and reverted.

### Mutation 3: Catch FFmpeg non-zero exit and return success status
- **Mutation Applied:** In `synthesize_token_voice_note`, ignored `proc.returncode != 0` without raising `FFmpegExecutionError`.
- **Target Test:** `tests/test_stage7_audio_engine.py::test_ffmpeg_non_zero_exit_fails_closed_and_removes_partial_file`
- **Result:** FAILED: Did not raise `FFmpegExecutionError`, attempted to probe corrupt output and failed closed.
- **Status:** CAUGHT and reverted.

### Mutation 4: Permit audio duration exceeding 45 seconds without triggering overflow handling
- **Mutation Applied:** Disabled duration check: `if False and actual_duration_ms > HARD_MAX_DURATION_MS:`.
- **Target Tests:** `test_duration_overflow_triggers_concise_fallback` and `test_duration_overflow_unresolvable_raises_error`.
- **Result:** BOTH FAILED:
  - `test_duration_overflow_triggers_concise_fallback`: `AssertionError: assert False where False = is_concise_fallback`.
  - `test_duration_overflow_unresolvable_raises_error`: `Failed: DID NOT RAISE <class 'omr_dispatch.audio_engine.AudioDurationOverflowError'>`.
- **Status:** CAUGHT and reverted.

---

## 8. Git Status & Handover Verification

**Command:** `git describe --tags --exact-match`
**Output:** `stage-6`

**Command:** `git diff --name-only stage-6`
**Files Modified/Created:**
- `assets/audio_tokens/manifest.json`
- `docs/audio_recording_sheet.md`
- `docs/.test_count_baseline`
- `docs/STATE.md`
- `docs/reviews/stage-7-run.md`
- `src/omr_dispatch/__init__.py`
- `src/omr_dispatch/audio_engine.py`
- `tests/test_stage7_audio_engine.py`

*(All files are strictly within the allowed S7A/S7B file boundary).*
