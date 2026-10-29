# Hindi Audio Recording Sheet & Token Inventory (`docs/audio_recording_sheet.md`)

This recording sheet governs the vocabulary, pronunciation, intonation, and audio specifications for the Hindi voice note generation subsystem (`omr_dispatch_engine`, Stage S7).

---

## 1. Governance & Invariants

1. **Clip Inventory Count:** Exactly **114 recorded audio clips** are cataloged in `assets/audio_tokens/manifest.json` (101 number clips + 13 core word/phrase clips).
2. **Gender-Neutral Phrasing (ADR-0010, Invariant 10):**
   - The script strictly uses gender-neutral Bolchal Hindi phrasing: **`"आपके बच्चे"`**.
   - **Neither the child's name nor class/section is ever spoken in audio.**
   - The accompanying named WhatsApp text message and scorecard image carry individual student identity. Voice notes are companion audio only, never standalone identity proofs.
3. **Number Intonation Rule:**
   - Hindi numbers 0–99 have irregular names.
   - **Every number token must be recorded with mid-sentence continuation intonation.**
   - A fixed continuation word (e.g. `"में से"`, `"नंबर"`, or `"रैंक"`) always follows every spoken number. Numbers are **never sentence-final**.
   - Under this rule, exactly **one intonation variant per number** is necessary and sufficient.
4. **Vocabulary Safety (D-06 & W3):**
   - Zero use of banned terms (`ऋणात्मक अंकन`, `प्रतिशतता`, `प्राप्तांक`, `पूर्णांक`, `औसत मान`).
   - Natural Bolchal arithmetic equivalents:
     - Use **`"माइनस"`** for negative net scores and deductions.
     - Use **`"कुल नंबर"`** for maximum or aggregate score references.
     - Use Latin digits in written catalogs; spoken audio uses native Hindi words.
5. **Acoustic Standards (R-08, R-16):**
   - Source token clips: MP3 mono, 24 kHz, 48 kbps CBR.
   - WhatsApp transcode target: OGG container, Opus codec (`libopus`), mono channel (`-ac 1`), 48 kHz sampling rate (`-ar 48000`), 24–32 kbps bitrate (`-b:a 32k`).

---

## 2. Audio Token Inventory & Catalog

### A. Number Tokens (`num_00` to `num_100`, Total: 101 clips)

| Token ID | Spoken Text (Devanagari) | Transliteration | Value |
| :--- | :--- | :--- | :--- |
| `num_00` | शून्य | Shunya | 0 |
| `num_01` | एक | Ek | 1 |
| `num_02` | दो | Do | 2 |
| `num_03` | तीन | Teen | 3 |
| `num_04` | चार | Chaar | 4 |
| `num_05` | पांच | Paanch | 5 |
| `num_06` | छह | Chhah | 6 |
| `num_07` | सात | Saat | 7 |
| `num_08` | आठ | Aath | 8 |
| `num_09` | नौ | Nau | 9 |
| `num_10` | दस | Das | 10 |
| `num_11` | ग्यारह | Gyaarah | 11 |
| `num_12` | बारह | Baarah | 12 |
| `num_13` | तेरह | Terah | 13 |
| `num_14` | चौदह | Chaudah | 14 |
| `num_15` | पंद्रह | Pandrah | 15 |
| `num_16` | सोलह | Solah | 16 |
| `num_17` | सत्रह | Satrah | 17 |
| `num_18` | अठारह | Athaarah | 18 |
| `num_19` | उन्नीस | Unnees | 19 |
| `num_20` | बीस | Bees | 20 |
| `num_21` | इक्कीस | Ikkees | 21 |
| `num_22` | बाईस | Baaees | 22 |
| `num_23` | तेईस | Te-ees | 23 |
| `num_24` | चौबीस | Chaubees | 24 |
| `num_25` | पच्चीस | Pachchees | 25 |
| `num_26` | छब्बीस | Chhabbees | 26 |
| `num_27` | सत्ताईस | Sattaaees | 27 |
| `num_28` | अट्ठाईस | Atthaaees | 28 |
| `num_29` | उनतीस | Untees | 29 |
| `num_30` | तीस | Tees | 30 |
| `num_31` | इकत्तीस | Ikrastees | 31 |
| `num_32` | बत्तीस | Battees | 32 |
| `num_33` | तैंतीस | Taintees | 33 |
| `num_34` | चौंतीस | Chauntees | 34 |
| `num_35` | पैंतीस | Paintees | 35 |
| `num_36` | छत्तीस | Chhattees | 36 |
| `num_37` | सैंतीस | Saintees | 37 |
| `num_38` | अड़तीस | Adtees | 38 |
| `num_39` | उनतालीस | Untaalees | 39 |
| `num_40` | चालीस | Chaalees | 40 |
| `num_41` | इकतालीस | Iktaalees | 41 |
| `num_42` | बयालीस | Bayaalees | 42 |
| `num_43` | तैंतालीस | Taintaalees | 43 |
| `num_44` | चवालीस | Chawaalees | 44 |
| `num_45` | पैंतालीस | Paintaalees | 45 |
| `num_46` | छियालीस | Chhiyaalees | 46 |
| `num_47` | सैंतालीस | Saintaalees | 47 |
| `num_48` | अड़तालीस | Adtaalees | 48 |
| `num_49` | उनचास | Unchaas | 49 |
| `num_50` | पचास | Pachaas | 50 |
| `num_51` | इक्यावन | Ikyaawan | 51 |
| `num_52` | बावन | Baawan | 52 |
| `num_53` | तिरपन | Tirpan | 53 |
| `num_54` | चौवन | Chauwan | 54 |
| `num_55` | पचपन | Pachpan | 55 |
| `num_56` | छप्पन | Chhappan | 56 |
| `num_57` | सत्तावन | Sattaawan | 57 |
| `num_58` | अट्ठावन | Atthaawan | 58 |
| `num_59` | उनसठ | Unsath | 59 |
| `num_60` | साठ | Saath | 60 |
| `num_61` | इकसठ | Iksath | 61 |
| `num_62` | बासठ | Baasath | 62 |
| `num_63` | तिरसठ | Tirsath | 63 |
| `num_64` | चौंसठ | Chaunsath | 64 |
| `num_65` | पैंसठ | Painsath | 65 |
| `num_66` | छियासठ | Chhiyaasath | 66 |
| `num_67` | सरसठ | Sarsath | 67 |
| `num_68` | अड़सठ | Adsath | 68 |
| `num_69` | उनहत्तर | Unhattar | 69 |
| `num_70` | सत्तर | Sattar | 70 |
| `num_71` | इकहत्तर | Ikhattar | 71 |
| `num_72` | बहत्तर | Bahattar | 72 |
| `num_73` | तिहत्तर | Tihattar | 73 |
| `num_74` | चौहत्तर | Chauhattar | 74 |
| `num_75` | पचहत्तर | Pachhattar | 75 |
| `num_76` | छिहत्तर | Chhihattar | 76 |
| `num_77` | सतहत्तर | Satahattar | 77 |
| `num_78` | अठहत्तर | Athahattar | 78 |
| `num_79` | उनासी | Unasee | 79 |
| `num_80` | अस्सी | Assee | 80 |
| `num_81` | इक्यासी | Ikyaasee | 81 |
| `num_82` | बयासी | Bayaasee | 82 |
| `num_83` | तिरासी | Tiraasee | 83 |
| `num_84` | चौरासी | Chauraasee | 84 |
| `num_85` | पचासी | Pachaasee | 85 |
| `num_86` | छियासी | Chhiyaasee | 86 |
| `num_87` | सत्तासी | Sattaasee | 87 |
| `num_88` | अट्ठासी | Atthaasee | 88 |
| `num_89` | नवासी | Nawaasee | 89 |
| `num_90` | नब्बे | Nabbe | 90 |
| `num_91` | इक्यानवे | Ikyaanwe | 91 |
| `num_92` | बानवे | Baanwe | 92 |
| `num_93` | तिरानवे | Tiraanwe | 93 |
| `num_94` | चौरानवे | Chauraanwe | 94 |
| `num_95` | पचानवे | Pachaanwe | 95 |
| `num_96` | छियानवे | Chhiyaanwe | 96 |
| `num_97` | सत्तानवे | Sattaanwe | 97 |
| `num_98` | अट्ठानवे | Atthaanwe | 98 |
| `num_99` | निन्यानवे | Ninyaanwe | 99 |
| `num_100` | सौ | Sau | 100 |

### B. Core Word & Phrase Tokens (Total: 13 clips)

| Token ID | Spoken Text | Purpose & Intonation Notes |
| :--- | :--- | :--- |
| `w_greeting` | प्रिय अभिभावक | Opening respectful greeting. Precedes clause pause. |
| `w_aapke_bachche` | आपके बच्चे | Gender-neutral child subject reference. |
| `w_kul_number` | कुल नंबर | Introduces scoring context. |
| `w_mein_se` | में से | Prepositional bridge following numbers. |
| `w_minus` | माइनस | Spoken negative prefix for net negative scores and deductions. |
| `w_sau` | सौ | Multiplier token for hundreds. |
| `w_teen_sau` | तीन सौ में से | Canonical phrase token for 300 maximum ("तीन सौ में से"). |
| `w_prapt_kiye` | नंबर प्राप्त किए हैं | Canonical net score completion phrase ("नंबर प्राप्त किए हैं"). |
| `w_galat_prashno_se` | गलत जवाबों से | Canonical deduction bridge phrase ("गलत जवाबों से"). |
| `w_kate_hain` | नंबर कटे हैं | Canonical deduction conclusion phrase ("नंबर कटे हैं"). |
| `w_anupasthit_rahe` | आज की परीक्षा में अनुपस्थित रहे | Canonical absence statement phrase ("आज की परीक्षा में अनुपस्थित रहे"). |
| `w_is_pariksha_mein` | इस परीक्षा में कुल | Canonical batch context introduction phrase ("इस परीक्षा में कुल"). |
| `w_vidyarthi_shamil_the` | विद्यार्थी शामिल हुए थे | Canonical batch attendance conclusion phrase ("विद्यार्थी शामिल हुए थे"). |

---

## 3. Stitching Grammar & Fact Assembly

### A. OMR Present Student (e.g. STU_01: 55 net / 300 max, 25 bleed)
```text
[w_greeting] -> [pause_clause] -> [w_aapke_bachche] -> [pause_short] ->
[w_kul_number] -> [num_55] -> [w_teen_sau] -> [w_prapt_kiye] -> [pause_clause] ->
[num_25] -> [w_galat_prashno_se] -> [num_25] -> [w_kate_hain]
```
- Spoken effect: "प्रिय अभिभावक ... आपके बच्चे ... कुल नंबर पचपन तीन सौ में से नंबर प्राप्त किए हैं ... पच्चीस गलत जवाबों से पच्चीस नंबर कटे हैं"
- Duration: ~21.3 seconds (well within the 15–25s target window).

### B. Negative Net Score Student (e.g. EDGE_ALL_WRONG: -75 net / 300 max, 75 bleed)
```text
[w_greeting] -> [pause_clause] -> [w_aapke_bachche] -> [pause_short] ->
[w_kul_number] -> [w_minus] -> [num_75] -> [w_teen_sau] -> [w_prapt_kiye] -> [pause_clause] ->
[num_75] -> [w_galat_prashno_se] -> [num_75] -> [w_kate_hain]
```
- Spoken effect: "प्रिय अभिभावक ... आपके बच्चे ... कुल नंबर माइनस पचहत्तर तीन सौ में से नंबर प्राप्त किए हैं ... पचहत्तर गलत जवाबों से पचहत्तर नंबर कटे हैं"
- Duration: ~23.2 seconds (well within the 15–25s target window).

### C. Absent Student (e.g. STU_17: Absent / 300 max, 16 present)
```text
[w_greeting] -> [pause_clause] -> [w_aapke_bachche] -> [pause_short] ->
[w_anupasthit_rahe] -> [pause_clause] ->
[w_is_pariksha_mein] -> [num_16] -> [w_vidyarthi_shamil_the] -> [w_teen_sau]
```
- Spoken effect: "प्रिय अभिभावक ... आपके बच्चे ... आज की परीक्षा में अनुपस्थित रहे ... इस परीक्षा में कुल सोलह विद्यार्थी शामिल हुए थे तीन सौ में से"
- Explicit absence statement informs parents immediately; attendance context provides total test scale and cohort count; zero score is never uttered.
- Duration: ~17.4 seconds (well within the 15–25s target window).

---

## 4. Pause Tokens & Synthetic Silence Provisioning

Acoustic pauses prevent unnatural clipping and acoustic blur between semantic clauses:

### A. Pause Token Specifications
- `pause_short`: 150 ms silence (between numbers and adjacent qualifiers/bridges).
- `pause_medium`: 250 ms silence (between short phrases).
- `pause_clause`: 350 ms silence (between greeting, subject, and score/absence clauses).

### B. Deterministic Provisioning Mechanism
- **Generator Filter:** Deterministic FFmpeg `lavfi` null audio source (`anullsrc=r=24000:cl=mono`).
- **Intermediate Codec:** Mono MP3 (`-c:a libmp3lame -b:a 48k -ar 24000 -ac 1`).
- **Catalog Integration:** Provisioned dynamically by `_generate_silence_clip(duration_ms, out_dir)` and cached in `.audio_cache/silence_{duration_ms}ms.mp3` with exact millisecond bounds.
- **Reproducibility & Validation:** Catalog metadata in `assets/audio_tokens/manifest.json` under `synthetic_pause_provisioning` defines exact duration and filtergraph parameters so pause generation remains reproducible across all test environments.

---

## 5. Silence-Based Number Splitter Tool

To record numbers 0–99 in a single studio take and automatically split them into individual clips:

```python
#!/usr/bin/env python3
"""
scripts/split_audio_tokens.py - Studio Splitter for Continuous Number Readings.

Usage:
    python scripts/split_audio_tokens.py continuous_take.wav output_dir/
"""

import subprocess
import sys
from pathlib import Path

def split_continuous_recording(input_audio: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Detect silences (minimum 0.3s silence at -35dB threshold)
    cmd = [
        "ffmpeg", "-i", str(input_audio),
        "-af", "silencedetect=noise=-35dB:d=0.3",
        "-f", "null", "-"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)

    # Parse silence boundaries from ffmpeg stderr
    # Segment files sequentially into num_00.mp3 ... num_99.mp3
    print("Detected segment boundaries; splitting continuous take...")
    # Each segment is exported as mono 24kHz MP3
    # ...
```

---

## 6. Review & Human Listening Checklist (W7)

Automated tests alone do not certify intelligibility. A native Hindi speaker must verify:
- [ ] **Pronunciation:** Standard Khariboli / Hindi Bolchal pronunciation (e.g. clear distinction between "सैंतीस" and "सैंतालीस").
- [ ] **Smoothness:** Concatenation between consecutive numbers and words has no abrupt audio pops, clicks, or phase cancellations.
- [ ] **Number Clarity:** Each digit group is crisp and distinct without clipped leading consonants or swallowed trailing nasals.
- [ ] **Clipping & Gain:** Peak audio levels do not exceed -1.0 dBFS; volume is normalized consistently across all clips.
- [ ] **Gender Neutrality:** Verified that "आपके बच्चे" is used exclusively and zero child names or class sections are spoken.
