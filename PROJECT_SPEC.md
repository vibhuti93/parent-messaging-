# PROJECT_SPEC.md — Project Specification and Decisions

## Product Boundary
The system imports/validates roster, answer key, decoded OMR responses and source scans; computes diagnostics; produces Hindi text, PNG scorecards, A4 PTM PDF, audio; quarantines unsafe contacts; dispatches only what verified WhatsApp rules and recorded consent permit; tracks status; offers optional QR confirmation. It does **not** perform bubble detection or scan alignment; decoded answers come from an external OMR service whose contract is defined in S2.

---

# Part B — Project Specification (Frozen Decisions)

Items tagged `OWNER-CONFIRM` are proposals you must approve or change before S1 freezes anything. The agent must not alter any decision itself; contradictions go to `docs/DECISIONS_OPEN.md`.

**D-01 Status bands.** For PRESENT students, using full-precision net percentage: `< 30.0%` RED; `30.0%–60.0%` inclusive YELLOW; `> 60.0%` GREEN. Net score may be negative, so percentage may be negative; negative nets are RED. ABSENT students have a separate band `ABSENT` (neutral grey `#5F6368`, white text); they have no score, rank, or percentage (all null).

**D-02 Easy questions.** `accuracy = correct among PRESENT / PRESENT count`; easy iff `accuracy >= 0.75` at full precision (exactly 0.75 qualifies). Absent students are excluded from numerator and denominator. If there are zero present students, no question is easy and batch average/topper are null.

**D-03 Subject labels.** Compute `attempt_ratio = attempted/subject_questions`, `accuracy_ratio = correct/attempted`. Evaluate in this order:
1. `attempted == 0` → `NO_ATTEMPT`
2. `attempt_ratio >= 0.60 and accuracy_ratio < 0.65` → `ACCURACY_BLEED`
3. `attempt_ratio < 0.50 and accuracy_ratio >= 0.75` → `CONCEPTUAL_SPEED_GAP`
4. `attempt_ratio < 0.50 and accuracy_ratio < 0.65` → `FOUNDATIONAL_CRISIS`
5. `attempt_ratio >= 0.60 and accuracy_ratio >= 0.75` → `MASTERY_ZONE`
6. otherwise → `MODERATE_ZONE`

Labels are internal; parent-facing copy describes observable facts only (see D-06).

**D-04 Rank and PTM.** Standard competition rank: `1 + count(present students with strictly higher net)`. PTM slip required iff ABSENT, or RED, or `rank > floor(0.75 * present_count)`. Rank applies to PRESENT only. `OWNER-CONFIRM`: bottom-quarter rule applies even when a whole batch is GREEN.

**D-05 Arithmetic.** `gross = Σ positive marks of correct`; `bleed = Σ magnitude of negative marks of wrong`; `net = gross − bleed`; `percentage = net / max_positive_marks × 100`. Internal values are full precision; display is one decimal. `positive_marks_not_earned` = Σ positive marks of easy questions that were wrong or blank (never described as "marks gained if fixed").

**D-06 Hindi wording.** Conversational Bolchal Hindi for non-specialist parents. Banned user-facing terms: `ऋणात्मक अंकन`, `प्रतिशतता`, `प्राप्तांक`, `पूर्णांक`, `औसत मान`. Preferred: "कुल नंबर", "गलत जवाबों से कटे नंबर", "क्लास का औसत स्कोर", "कम-से-कम 75% बच्चों ने सही किया". Never claim lying, deliberate guessing, laziness, or psychological cause. Never say "more than 75%" for a threshold of ≥ 75%. Never print `None`. Always give denominators ("300 में से", "N उपस्थित बच्चों में से").

**D-07 Banner colours.** RED `#D93025`, YELLOW `#F9AB00` (dark text), GREEN `#1E8E3E`, ABSENT `#5F6368`. Contrast must be checked.

**D-08 Audio.** Primary mode `RECORDED_TOKEN_STITCH` (human-supplied recorded Hindi tokens). Optional `NETWORK_TTS` adapter, off by default. Typical note 15–25 s; hard maximum 45 s. On overflow: use the approved concise script variant (score + max + absence/rank facts only); if still over, return `AUDIO_UNAVAILABLE` and keep text. Never truncate material score facts. Negative net uses a recorded "minus" token.

**D-09 Messaging.** Live dispatch disabled by default (config flag + separately configured provider). Text/image template first; audio only where S0 verification proves the message type supports it; otherwise defer audio or use a secure authenticated link if permitted.

**D-10 Schedule.** `Asia/Kolkata`. Primary: Sunday 20:30 IST after the result is finalised. Monday 10:00 IST only when the event has `reminder_enabled = true`, as a distinct reminder identity. Example: event `2026-10-18 14:15+05:30` → primary `2026-10-18 20:30+05:30`; reminder (if enabled) `2026-10-19 10:00+05:30`.

**D-11 Parent confirmation (QR).** Default **disabled**. If enabled: opaque random token, scoped to student/test/PTM event, stored hashed, TTL default 72 h (`OWNER-CONFIRM`), single use, ≤ 5 attempts per token, revocable, HTTPS only, OTP challenge to the already verified guardian number. OTP delivery channel is `OWNER-CONFIRM` (WhatsApp authentication template vs SMS; deferred to pre-deployment checklist).

**D-12 Disclosure to parents.** Own child's report + class average + topper score + rank "X out of N present". No other student's response-level data. `OWNER-CONFIRM`: topper score may be shown.

**D-13 Retention (development default; legal review deferred, see docs/PRE_DEPLOYMENT_CHECKLIST.md).** Scans and reports: current academic year. Message/audit logs: 90 days, masked. Deletion on verified request unless a documented legal hold applies.

**D-14 Scale.** Up to 200 students per batch; test maximum configurable; golden exam is 300.
