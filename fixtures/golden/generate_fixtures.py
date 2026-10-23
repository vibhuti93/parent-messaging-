"""
Deterministic golden fixture generator for omr_dispatch_engine Stage S1.

Generates:
  1. test_paper_300.json
  2. admissions_300.json
  3. submissions_300.json
  4. expected_reports.json
  5. marks_entry_50.json
  6. expected_marks_reports.json
  7. isolation_two_orgs.json
  8. edge_cases.json
  9. README.md
 10. manifest.json

Guarantees 100% byte-identical reproduction across runs.
Uses exact integer / fraction values, zero floats, and Unicode NFC normalization.
"""

from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent
REPO_ROOT = FIXTURES_DIR.parent.parent


def nfc(text: str) -> str:
    """Normalize text to Unicode NFC."""
    return unicodedata.normalize("NFC", text)


def dump_json(path: Path, data: dict) -> None:
    """Write json with sorted keys, 2-space indentation, and newline at EOF with POSIX line endings."""
    content = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    path.write_text(content, encoding="utf-8", newline="\n")


def generate_test_paper_300() -> dict:
    """
    75 questions, IDs 1–75.
    Q1–25 PHYSICS, Q26–50 CHEMISTRY, Q51–75 MATHS.
    +4 correct, −1 wrong, 0 blank.
    correct_option = ["A","B","C","D"][(q−1) % 4]
    Synthetic 800×600 geometry:
      col = (q−1)//15
      row = (q−1)%15
      col_x = 30 + col * 150
      center_y = 255 + row * 17
      option centre x = col_x + 35 + opt_index * 24
    """
    options = ["A", "B", "C", "D"]
    questions = []

    for q in range(1, 76):
        if 1 <= q <= 25:
            subject = "PHYSICS"
        elif 26 <= q <= 50:
            subject = "CHEMISTRY"
        else:
            subject = "MATHS"

        correct_opt = options[(q - 1) % 4]
        col = (q - 1) // 15
        row = (q - 1) % 15
        col_x = 30 + col * 150
        center_y = 255 + row * 17

        opt_coords = {}
        for opt_idx, opt_letter in enumerate(options):
            opt_coords[opt_letter] = {
                "x": col_x + 35 + opt_idx * 24,
                "y": center_y,
            }

        questions.append({
            "question_id": q,
            "subject": subject,
            "question_type": "SINGLE_CORRECT",
            "correct_option": correct_opt,
            "positive_marks": 4,
            "negative_marks": 1,
            "blank_marks": 0,
            "bubble_coordinates": {
                "col": col,
                "row": row,
                "col_x": col_x,
                "center_y": center_y,
                "options": opt_coords,
            },
        })

    return {
        "schema_version": 1,
        "test_id": "TEST_300",
        "org_id": "DEFAULT_INSTITUTION",
        "name": nfc("टर्म 1 डायग्नोस्टिक टेस्ट"),
        "total_questions": 75,
        "total_max_marks": 300,
        "subjects": ["PHYSICS", "CHEMISTRY", "MATHS"],
        "max_marks_per_subject": {
            "PHYSICS": 100,
            "CHEMISTRY": 100,
            "MATHS": 100,
        },
        "questions": questions,
    }


def generate_admissions_300() -> dict:
    """
    20 students (STU_01 to STU_20).
    Roster contains inputs only: student_id, roll_number, child_display_name,
    class_section, raw_student_phone, raw_guardian_phone, consent_status,
    guardian_verification, verified_sibling.
    Quarantine flags, reason codes, and dispatch eligibility are moved to expected_contacts.json.
    """
    names = [
        "आरव", "प्रिया", "रोहन", "ईशान", "कबीर", "अनन्या", "विहान", "आदित्य",
        "दीया", "संजय", "नेहा", "अर्जुन", "तन्वी", "आर्यन", "खुशी", "मनीष",
        "रिया", "पूजा", "राहुल", "श्रेया",
    ]

    students = []
    for idx in range(1, 21):
        stu_id = f"STU_{idx:02d}"
        roll = f"{idx:02d}"
        child_name = nfc(names[idx - 1])
        class_sec = nfc("कक्षा 10-A")

        # Defaults
        student_phone = f"98200100{idx:02d}"
        parent_phone = f"98300100{idx:02d}"
        consent = "OPT_IN"
        guardian_ver = "VERIFIED"
        verified_sibling = False

        # Exceptions
        if idx == 1:
            student_phone = "+91 98111-22201"
            parent_phone = "+91 98111-22202"
        elif idx == 2:
            student_phone = "09811122203"
            parent_phone = "9811122203"
        elif idx in (3, 4):
            parent_phone = "9811122299"
            verified_sibling = False
        elif idx in (5, 6):
            parent_phone = "9811122288"
            verified_sibling = True
        elif idx == 7:
            parent_phone = "5511122207"
        elif idx == 8:
            consent = "UNKNOWN"
        elif idx == 9:
            consent = "REVOKED"
        elif idx == 10:
            guardian_ver = "UNVERIFIED"
        elif idx == 17:
            parent_phone = "9830010017"
            consent = "OPT_IN"
            guardian_ver = "VERIFIED"
        elif idx == 19:
            consent = "REVOKED"

        students.append({
            "student_id": stu_id,
            "roll_number": roll,
            "child_display_name": child_name,
            "class_section": class_sec,
            "raw_student_phone": student_phone,
            "raw_guardian_phone": parent_phone,
            "consent_status": consent,
            "guardian_verification": guardian_ver,
            "verified_sibling": verified_sibling,
        })

    return {
        "schema_version": 1,
        "test_id": "TEST_300",
        "org_id": "DEFAULT_INSTITUTION",
        "cohort_label": nfc("कक्षा 10-A"),
        "students": students,
    }


def generate_expected_contacts(admissions: dict) -> dict:
    """
    Expected contact & quarantine evaluation results for admissions_300.json.
    Separates expected business-rule evaluations (quarantine flags, reason codes, dispatch eligibility)
    from input admissions data per S1-R1 requirement.
    """
    contacts = []
    for s in admissions["students"]:
        sid = s["student_id"]
        idx = int(sid.split("_")[1])

        is_quarantined = False
        quarantine_flags = []
        dispatch_eligible = True
        exclusion_reason = None

        if idx == 2:
            is_quarantined = True
            quarantine_flags = ["INTERCEPTION_RISK_SAME_NUMBER"]
            dispatch_eligible = False
            exclusion_reason = "INTERCEPTION_RISK_SAME_NUMBER"
        elif idx in (3, 4):
            is_quarantined = True
            quarantine_flags = ["DUPLICATE_PARENT_UNVERIFIED"]
            dispatch_eligible = False
            exclusion_reason = "DUPLICATE_PARENT_UNVERIFIED"
        elif idx == 7:
            is_quarantined = True
            quarantine_flags = ["INVALID_PHONE_NUMBER"]
            dispatch_eligible = False
            exclusion_reason = "INVALID_PHONE_NUMBER"
        elif idx == 8:
            dispatch_eligible = False
            exclusion_reason = "CONSENT_UNKNOWN"
        elif idx in (9, 19):
            dispatch_eligible = False
            exclusion_reason = "CONSENT_REVOKED"
        elif idx == 10:
            dispatch_eligible = False
            exclusion_reason = "GUARDIAN_UNVERIFIED"

        entry = {
            "student_id": sid,
            "is_quarantined": is_quarantined,
            "quarantine_flags": quarantine_flags,
            "dispatch_eligible": dispatch_eligible,
            "exclusion_reason": exclusion_reason,
        }
        contacts.append(entry)

    return {
        "schema_version": 1,
        "test_id": "TEST_300",
        "org_id": "DEFAULT_INSTITUTION",
        "contacts": contacts,
    }


def generate_submissions_300(test_paper: dict) -> dict:
    """
    Submissions for STU_01 to STU_20.
    16 PRESENT (01–16), 4 ABSENT (17–20, empty responses).
    Materialise every response in JSON.
    Wrong answer = next option in A->B->C->D->A order after the key.
    """
    options = ["A", "B", "C", "D"]
    key_map = {q["question_id"]: q["correct_option"] for q in test_paper["questions"]}

    def wrong_opt(q: int) -> str:
        key = key_map[q]
        idx = options.index(key)
        return options[(idx + 1) % 4]

    submissions = []

    for idx in range(1, 21):
        stu_id = f"STU_{idx:02d}"
        sub_id = f"SUB_300_{idx:02d}"

        if idx >= 17:
            # ABSENT: empty responses dict
            submissions.append({
                "submission_id": sub_id,
                "student_id": stu_id,
                "status": "ABSENT",
                "responses": {},
            })
            continue

        resp: dict[str, str] = {}

        if idx == 1:
            # Q1–10 ✓; Q11–20 ✗; Q21–25 blank; Q26–30 ✓; Q31–45 ✗; Q46–50 blank; Q51–55 ✓; Q56–75 blank.
            for q in range(1, 11):
                resp[str(q)] = key_map[q]
            for q in range(11, 21):
                resp[str(q)] = wrong_opt(q)
            for q in range(21, 26):
                resp[str(q)] = "BLANK"
            for q in range(26, 31):
                resp[str(q)] = key_map[q]
            for q in range(31, 46):
                resp[str(q)] = wrong_opt(q)
            for q in range(46, 51):
                resp[str(q)] = "BLANK"
            for q in range(51, 56):
                resp[str(q)] = key_map[q]
            for q in range(56, 76):
                resp[str(q)] = "BLANK"

        elif idx == 2:
            # Q1–70 ✓; Q71–72 ✗; Q73–75 blank.
            for q in range(1, 71):
                resp[str(q)] = key_map[q]
            for q in (71, 72):
                resp[str(q)] = wrong_opt(q)
            for q in (73, 74, 75):
                resp[str(q)] = "BLANK"

        elif idx == 3:
            # Q1–23 ✓; Q24-25 blank; Q26–27 ✗; rest blank.
            for q in range(1, 24):
                resp[str(q)] = key_map[q]
            for q in (24, 25):
                resp[str(q)] = "BLANK"
            for q in (26, 27):
                resp[str(q)] = wrong_opt(q)
            for q in range(28, 76):
                resp[str(q)] = "BLANK"

        elif idx == 4:
            # Q1–45 ✓; rest blank.
            for q in range(1, 46):
                resp[str(q)] = key_map[q]
            for q in range(46, 76):
                resp[str(q)] = "BLANK"

        elif 5 <= idx <= 13:
            # Q1–20 ✓; rest blank.
            for q in range(1, 21):
                resp[str(q)] = key_map[q]
            for q in range(21, 76):
                resp[str(q)] = "BLANK"

        elif 14 <= idx <= 16:
            # all blank.
            for q in range(1, 76):
                resp[str(q)] = "BLANK"

        submissions.append({
            "submission_id": sub_id,
            "student_id": stu_id,
            "status": "PRESENT",
            "responses": resp,
        })

    return {
        "schema_version": 1,
        "test_id": "TEST_300",
        "org_id": "DEFAULT_INSTITUTION",
        "submissions": submissions,
    }


def generate_expected_reports(admissions: dict) -> dict:
    """
    Generate literal golden expected values matching S1.md table exactly.
    Includes full diagnostic rendered parent message strings per S1-BLOCK-02 (Option 1)
    and S1-BLOCK-03 (Option 1).
    """
    students_info = {s["student_id"]: s for s in admissions["students"]}

    # Student-specific literals from S1.md table
    reports = []

    # STU_01
    reports.append({
        "student_id": "STU_01",
        "roll_number": "01",
        "child_display_name": students_info["STU_01"]["child_display_name"],
        "class_section": students_info["STU_01"]["class_section"],
        "status": "PRESENT",
        "attempted": 45,
        "correct": 20,
        "wrong": 25,
        "blank": 30,
        "gross_marks": 80,
        "bleed_marks": 25,
        "net_marks": 55,
        "percentage": "18.33",
        "net_percentage": "18.3%",
        "competition_rank": 13,
        "status_band": "RED",
        "requires_ptm_slip": True,
        "easy_missed_question_ids": [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
        "positive_marks_not_earned": 40,
        "subject_diagnostics": {
            "PHYSICS": "ACCURACY_BLEED",
            "CHEMISTRY": "ACCURACY_BLEED",
            "MATHS": "CONCEPTUAL_SPEED_GAP",
        },
        "message_text": nfc(
            "प्रिय अभिभावक, आरव (कक्षा 10-A) के टर्म 1 डायग्नोस्टिक टेस्ट में कुल नंबर: "
            "300 में से 55 नंबर आए हैं (18.3%)। 16 उपस्थित बच्चों में आरव का रैंक 13 है। "
            "क्लास का औसत स्कोर 82.7 है। क्लास में सबसे ज़्यादा नंबर 278 हैं। "
            "सही जवाबों से मिले 80 नंबर, गलत जवाबों से 25 नंबर कट गए।"
        ),
    })

    # STU_02
    reports.append({
        "student_id": "STU_02",
        "roll_number": "02",
        "child_display_name": students_info["STU_02"]["child_display_name"],
        "class_section": students_info["STU_02"]["class_section"],
        "status": "PRESENT",
        "attempted": 72,
        "correct": 70,
        "wrong": 2,
        "blank": 3,
        "gross_marks": 280,
        "bleed_marks": 2,
        "net_marks": 278,
        "percentage": "92.67",
        "net_percentage": "92.7%",
        "competition_rank": 1,
        "status_band": "GREEN",
        "requires_ptm_slip": False,
        "easy_missed_question_ids": [],
        "positive_marks_not_earned": 0,
        "subject_diagnostics": {
            "PHYSICS": "MASTERY_ZONE",
            "CHEMISTRY": "MASTERY_ZONE",
            "MATHS": "MASTERY_ZONE",
        },
        "message_text": nfc(
            "प्रिय अभिभावक, प्रिया (कक्षा 10-A) के टर्म 1 डायग्नोस्टिक टेस्ट में कुल नंबर: "
            "300 में से 278 नंबर आए हैं (92.7%)। 16 उपस्थित बच्चों में प्रिया का रैंक 1 है। "
            "क्लास का औसत स्कोर 82.7 है। क्लास में सबसे ज़्यादा नंबर 278 हैं। "
            "सही जवाबों से मिले 280 नंबर, गलत जवाबों से 2 नंबर कट गए।"
        ),
    })

    # STU_03
    reports.append({
        "student_id": "STU_03",
        "roll_number": "03",
        "child_display_name": students_info["STU_03"]["child_display_name"],
        "class_section": students_info["STU_03"]["class_section"],
        "status": "PRESENT",
        "attempted": 25,
        "correct": 23,
        "wrong": 2,
        "blank": 50,
        "gross_marks": 92,
        "bleed_marks": 2,
        "net_marks": 90,
        "percentage": "30.00",
        "net_percentage": "30.0%",
        "competition_rank": 3,
        "status_band": "YELLOW",
        "requires_ptm_slip": False,
        "easy_missed_question_ids": [],
        "positive_marks_not_earned": 0,
        "subject_diagnostics": {
            "PHYSICS": "MASTERY_ZONE",
            "CHEMISTRY": "FOUNDATIONAL_CRISIS",
            "MATHS": "NO_ATTEMPT",
        },
        "message_text": nfc(
            "प्रिय अभिभावक, रोहन (कक्षा 10-A) के टर्म 1 डायग्नोस्टिक टेस्ट में कुल नंबर: "
            "300 में से 90 नंबर आए हैं (30.0%)। 16 उपस्थित बच्चों में रोहन का रैंक 3 है। "
            "क्लास का औसत स्कोर 82.7 है। क्लास में सबसे ज़्यादा नंबर 278 हैं। "
            "सही जवाबों से मिले 92 नंबर, गलत जवाबों से 2 नंबर कट गए।"
        ),
    })

    # STU_04
    reports.append({
        "student_id": "STU_04",
        "roll_number": "04",
        "child_display_name": students_info["STU_04"]["child_display_name"],
        "class_section": students_info["STU_04"]["class_section"],
        "status": "PRESENT",
        "attempted": 45,
        "correct": 45,
        "wrong": 0,
        "blank": 30,
        "gross_marks": 180,
        "bleed_marks": 0,
        "net_marks": 180,
        "percentage": "60.00",
        "net_percentage": "60.0%",
        "competition_rank": 2,
        "status_band": "YELLOW",
        "requires_ptm_slip": False,
        "easy_missed_question_ids": [],
        "positive_marks_not_earned": 0,
        "subject_diagnostics": {
            "PHYSICS": "MASTERY_ZONE",
            "CHEMISTRY": "MASTERY_ZONE",
            "MATHS": "NO_ATTEMPT",
        },
        "message_text": nfc(
            "प्रिय अभिभावक, ईशान (कक्षा 10-A) के टर्म 1 डायग्नोस्टिक टेस्ट में कुल नंबर: "
            "300 में से 180 नंबर आए हैं (60.0%)। 16 उपस्थित बच्चों में ईशान का रैंक 2 है। "
            "क्लास का औसत स्कोर 82.7 है। क्लास में सबसे ज़्यादा नंबर 278 हैं। "
            "सही जवाबों से मिले 180 नंबर, गलत जवाबों से 0 नंबर कट गए।"
        ),
    })

    # STU_05 to STU_13
    for idx in range(5, 14):
        stu_id = f"STU_{idx:02d}"
        c_name = students_info[stu_id]["child_display_name"]
        reports.append({
            "student_id": stu_id,
            "roll_number": f"{idx:02d}",
            "child_display_name": c_name,
            "class_section": students_info[stu_id]["class_section"],
            "status": "PRESENT",
            "attempted": 20,
            "correct": 20,
            "wrong": 0,
            "blank": 55,
            "gross_marks": 80,
            "bleed_marks": 0,
            "net_marks": 80,
            "percentage": "26.67",
            "net_percentage": "26.7%",
            "competition_rank": 4,
            "status_band": "RED",
            "requires_ptm_slip": True,
            "easy_missed_question_ids": [],
            "positive_marks_not_earned": 0,
            "subject_diagnostics": {
                "PHYSICS": "MASTERY_ZONE",
                "CHEMISTRY": "NO_ATTEMPT",
                "MATHS": "NO_ATTEMPT",
            },
            "message_text": nfc(
                f"प्रिय अभिभावक, {c_name} (कक्षा 10-A) के टर्म 1 डायग्नोस्टिक टेस्ट में कुल नंबर: "
                "300 में से 80 नंबर आए हैं (26.7%)। 16 उपस्थित बच्चों में "
                f"{c_name} का रैंक 4 है। क्लास का औसत स्कोर 82.7 है। "
                "क्लास में सबसे ज़्यादा नंबर 278 हैं। सही जवाबों से मिले 80 नंबर, "
                "गलत जवाबों से 0 नंबर कट गए।"
            ),
        })

    # STU_14 to STU_16
    for idx in range(14, 17):
        stu_id = f"STU_{idx:02d}"
        c_name = students_info[stu_id]["child_display_name"]
        reports.append({
            "student_id": stu_id,
            "roll_number": f"{idx:02d}",
            "child_display_name": c_name,
            "class_section": students_info[stu_id]["class_section"],
            "status": "PRESENT",
            "attempted": 0,
            "correct": 0,
            "wrong": 0,
            "blank": 75,
            "gross_marks": 0,
            "bleed_marks": 0,
            "net_marks": 0,
            "percentage": "0.00",
            "net_percentage": "0.0%",
            "competition_rank": 14,
            "status_band": "RED",
            "requires_ptm_slip": True,
            "easy_missed_question_ids": list(range(1, 21)),
            "positive_marks_not_earned": 80,
            "subject_diagnostics": {
                "PHYSICS": "NO_ATTEMPT",
                "CHEMISTRY": "NO_ATTEMPT",
                "MATHS": "NO_ATTEMPT",
            },
            "message_text": nfc(
                f"प्रिय अभिभावक, {c_name} (कक्षा 10-A) के टर्म 1 डायग्नोस्टिक टेस्ट में कुल नंबर: "
                "300 में से 0 नंबर आए हैं (0.0%)। 16 उपस्थित बच्चों में "
                f"{c_name} का रैंक 14 है। क्लास का औसत स्कोर 82.7 है। "
                "क्लास में सबसे ज़्यादा नंबर 278 हैं। सही जवाबों से मिले 0 नंबर, "
                "गलत जवाबों से 0 नंबर कट गए।"
            ),
        })

    # STU_17 to STU_20 (ABSENT)
    for idx in range(17, 21):
        stu_id = f"STU_{idx:02d}"
        c_name = students_info[stu_id]["child_display_name"]
        reports.append({
            "student_id": stu_id,
            "roll_number": f"{idx:02d}",
            "child_display_name": c_name,
            "class_section": students_info[stu_id]["class_section"],
            "status": "ABSENT",
            "attempted": None,
            "correct": None,
            "wrong": None,
            "blank": None,
            "gross_marks": None,
            "bleed_marks": None,
            "net_marks": None,
            "percentage": None,
            "net_percentage": None,
            "competition_rank": None,
            "status_band": "ABSENT",
            "requires_ptm_slip": True,
            "easy_missed_question_ids": [],
            "positive_marks_not_earned": None,
            "subject_diagnostics": None,
            "message_text": nfc(
                f"प्रिय अभिभावक, {c_name} (कक्षा 10-A) टर्म 1 डायग्नोस्टिक टेस्ट के टेस्ट में अनुपस्थित रहे। "
                "कुल 300 नंबर का टेस्ट आयोजित किया गया था जिसमें 16 बच्चे उपस्थित रहे।"
            ),
        })

    return {
        "schema_version": 1,
        "test_id": "TEST_300",
        "org_id": "DEFAULT_INSTITUTION",
        "batch_metrics": {
            "enrolled_count": 20,
            "present_count": 16,
            "absent_count": 4,
            "total_score_sum": 1323,
            "class_average_exact": "82.6875",
            "class_average": "82.7",
            "class_average_fraction": "1323/16",
            "topper_net_marks": 278,
            "easy_question_ids": list(range(1, 21)),
            "ptm_eligible_count": 17,
        },
        "student_reports": reports,
    }


def generate_marks_entry_50() -> dict:
    """
    Marks Entry Golden Fixture (marks_entry_50.json).
    6 students, Class 8-B, English (Max Marks 50):
      - ME_01: Aarav, PRESENT, 30.0
      - ME_02: Priya, PRESENT, 47.0
      - ME_03: Rohan, PRESENT, 30.0
      - ME_04: Ananya, PRESENT, 2.5
      - ME_05: Vikram, PRESENT, 0.0
      - ME_06: Meera, ABSENT, null
    """
    return {
        "schema_version": 1,
        "org_id": "DEFAULT_INSTITUTION",
        "assessment_name": nfc("यूनिट टेस्ट 1"),
        "subject": nfc("अंग्रेज़ी"),
        "max_marks": 50,
        "cohort_label": nfc("कक्षा 8-B"),
        "rows": [
            {
                "student_id": "ME_01",
                "roll_no": "01",
                "child_display_name": nfc("आरव"),
                "status": "PRESENT",
                "marks": "30.0",
            },
            {
                "student_id": "ME_02",
                "roll_no": "02",
                "child_display_name": nfc("प्रिया"),
                "status": "PRESENT",
                "marks": "47.0",
            },
            {
                "student_id": "ME_03",
                "roll_no": "03",
                "child_display_name": nfc("रोहन"),
                "status": "PRESENT",
                "marks": "30.0",
            },
            {
                "student_id": "ME_04",
                "roll_no": "04",
                "child_display_name": nfc("अनन्या"),
                "status": "PRESENT",
                "marks": "2.5",
            },
            {
                "student_id": "ME_05",
                "roll_no": "05",
                "child_display_name": nfc("विक्रम"),
                "status": "PRESENT",
                "marks": "0.0",
            },
            {
                "student_id": "ME_06",
                "roll_no": "06",
                "child_display_name": nfc("मीरा"),
                "status": "ABSENT",
                "marks": None,
            },
        ],
    }


def generate_expected_marks_reports() -> dict:
    """
    Expected reports for marks_entry_50.json per S1.md and S1-BLOCK decisions.
    """
    return {
        "schema_version": 1,
        "org_id": "DEFAULT_INSTITUTION",
        "assessment_name": nfc("यूनिट टेस्ट 1"),
        "subject": nfc("अंग्रेज़ी"),
        "max_marks": 50,
        "cohort_label": nfc("कक्षा 8-B"),
        "batch_metrics": {
            "enrolled_count": 6,
            "present_count": 5,
            "absent_count": 1,
            "total_score_sum": "109.5",
            "class_average": "21.9",
            "topper_marks": "47.0",
            "ptm_eligible_count": 3,
        },
        "student_reports": [
            {
                "student_id": "ME_01",
                "roll_no": "01",
                "child_display_name": nfc("आरव"),
                "class_section": nfc("कक्षा 8-B"),
                "status": "PRESENT",
                "marks": "30.0",
                "max_marks": 50,
                "percentage": "60.00",
                "net_percentage": "60.0%",
                "competition_rank": 2,
                "status_band": "YELLOW",
                "requires_ptm_slip": False,
                "message_text": nfc(
                    "प्रिय अभिभावक, आरव (कक्षा 8-B) के यूनिट टेस्ट 1 (अंग्रेज़ी) में "
                    "50 में से 30 नंबर आए हैं (60.0%)। 5 उपस्थित बच्चों में आरव का रैंक 2 है। "
                    "क्लास का औसत स्कोर 21.9 है। क्लास में सबसे ज़्यादा नंबर 47 हैं।"
                ),
            },
            {
                "student_id": "ME_02",
                "roll_no": "02",
                "child_display_name": nfc("प्रिया"),
                "class_section": nfc("कक्षा 8-B"),
                "status": "PRESENT",
                "marks": "47.0",
                "max_marks": 50,
                "percentage": "94.00",
                "net_percentage": "94.0%",
                "competition_rank": 1,
                "status_band": "GREEN",
                "requires_ptm_slip": False,
                "message_text": nfc(
                    "प्रिय अभिभावक, प्रिया (कक्षा 8-B) के यूनिट टेस्ट 1 (अंग्रेज़ी) में "
                    "50 में से 47 नंबर आए हैं (94.0%)। 5 उपस्थित बच्चों में प्रिया का रैंक 1 है। "
                    "क्लास का औसत स्कोर 21.9 है। क्लास में सबसे ज़्यादा नंबर 47 हैं।"
                ),
            },
            {
                "student_id": "ME_03",
                "roll_no": "03",
                "child_display_name": nfc("रोहन"),
                "class_section": nfc("कक्षा 8-B"),
                "status": "PRESENT",
                "marks": "30.0",
                "max_marks": 50,
                "percentage": "60.00",
                "net_percentage": "60.0%",
                "competition_rank": 2,
                "status_band": "YELLOW",
                "requires_ptm_slip": False,
                "message_text": nfc(
                    "प्रिय अभिभावक, रोहन (कक्षा 8-B) के यूनिट टेस्ट 1 (अंग्रेज़ी) में "
                    "50 में से 30 नंबर आए हैं (60.0%)। 5 उपस्थित बच्चों में रोहन का रैंक 2 है। "
                    "क्लास का औसत स्कोर 21.9 है। क्लास में सबसे ज़्यादा नंबर 47 हैं।"
                ),
            },
            {
                "student_id": "ME_04",
                "roll_no": "04",
                "child_display_name": nfc("अनन्या"),
                "class_section": nfc("कक्षा 8-B"),
                "status": "PRESENT",
                "marks": "2.5",
                "max_marks": 50,
                "percentage": "5.00",
                "net_percentage": "5.0%",
                "competition_rank": 4,
                "status_band": "RED",
                "requires_ptm_slip": True,
                "message_text": nfc(
                    "प्रिय अभिभावक, अनन्या (कक्षा 8-B) के यूनिट टेस्ट 1 (अंग्रेज़ी) में "
                    "50 में से 2.5 नंबर आए हैं (5.0%)। 5 उपस्थित बच्चों में अनन्या का रैंक 4 है। "
                    "क्लास का औसत स्कोर 21.9 है। क्लास में सबसे ज़्यादा नंबर 47 हैं।"
                ),
            },
            {
                "student_id": "ME_05",
                "roll_no": "05",
                "child_display_name": nfc("विक्रम"),
                "class_section": nfc("कक्षा 8-B"),
                "status": "PRESENT",
                "marks": "0.0",
                "max_marks": 50,
                "percentage": "0.00",
                "net_percentage": "0.0%",
                "competition_rank": 5,
                "status_band": "RED",
                "requires_ptm_slip": True,
                "message_text": nfc(
                    "प्रिय अभिभावक, विक्रम (कक्षा 8-B) के यूनिट टेस्ट 1 (अंग्रेज़ी) में "
                    "50 में से 0 नंबर आए हैं (0.0%)। 5 उपस्थित बच्चों में विक्रम का रैंक 5 है। "
                    "क्लास का औसत स्कोर 21.9 है। क्लास में सबसे ज़्यादा नंबर 47 हैं।"
                ),
            },
            {
                "student_id": "ME_06",
                "roll_no": "06",
                "child_display_name": nfc("मीरा"),
                "class_section": nfc("कक्षा 8-B"),
                "status": "ABSENT",
                "marks": None,
                "max_marks": 50,
                "percentage": None,
                "net_percentage": None,
                "competition_rank": None,
                "status_band": "ABSENT",
                "requires_ptm_slip": True,
                "message_text": nfc(
                    "प्रिय अभिभावक, मीरा (कक्षा 8-B) यूनिट टेस्ट 1 (अंग्रेज़ी) के टेस्ट में अनुपस्थित रहे। "
                    "कुल 50 नंबर का टेस्ट आयोजित किया गया था जिसमें 5 बच्चे उपस्थित रहे।"
                ),
            },
        ],
    }


def generate_isolation_two_orgs() -> dict:
    """
    Two-Org Isolation Fixture (isolation_two_orgs.json).
    Org Alpha and Org Beta with overlapping roll numbers ("01")
    and identical parent phone numbers across orgs with different student identities.
    """
    return {
        "schema_version": 1,
        "org_alpha": {
            "org_id": "ORG_ALPHA",
            "school_name": nfc("आदर्श विद्यालय"),
            "students": [
                {
                    "student_id": "STU_ALPHA_01",
                    "roll_number": "01",
                    "student_name": nfc("आरव शर्मा"),
                    "child_display_name": nfc("आरव"),
                    "class_section": nfc("कक्षा 10-A"),
                    "guardian_phone": "+919811122201",
                    "marks": 55,
                    "max_marks": 100,
                },
            ],
        },
        "org_beta": {
            "org_id": "ORG_BETA",
            "school_name": nfc("सरस्वती विद्या मंदिर"),
            "students": [
                {
                    "student_id": "STU_BETA_01",
                    "roll_number": "01",
                    "student_name": nfc("विवेक कुमार"),
                    "child_display_name": nfc("विवेक"),
                    "class_section": nfc("कक्षा 8-B"),
                    "guardian_phone": "+919811122201",
                    "marks": 90,
                    "max_marks": 100,
                },
            ],
        },
    }


def generate_edge_cases() -> dict:
    """
    Edge-case fixture (edge_cases.json):
      - all-wrong student (net -75 -> -25.00%, RED)
      - tie-for-first pair
      - zero-present batch
      - one-student batch
      - percentage boundary values (29.99, 30.0, 60.0, 60.01)
    """
    return {
        "schema_version": 1,
        "all_wrong_student": {
            "student_id": "EDGE_ALL_WRONG",
            "total_questions": 75,
            "max_marks": 300,
            "attempted": 75,
            "correct": 0,
            "wrong": 75,
            "blank": 0,
            "gross_marks": 0,
            "bleed_marks": 75,
            "net_marks": -75,
            "net_percentage": "-25.0%",
            "status_band": "RED",
            "requires_ptm_slip": True,
        },
        "tie_for_first_pair": {
            "present_count": 3,
            "students": [
                {"student_id": "EDGE_TIE_A", "net_marks": 250, "competition_rank": 1},
                {"student_id": "EDGE_TIE_B", "net_marks": 250, "competition_rank": 1},
                {"student_id": "EDGE_TIE_C", "net_marks": 200, "competition_rank": 3},
            ],
        },
        "zero_present_batch": {
            "enrolled_count": 5,
            "present_count": 0,
            "absent_count": 5,
            "total_score_sum": None,
            "class_average": None,
            "topper_net_marks": None,
            "easy_question_ids": [],
        },
        "one_student_batch": {
            "enrolled_count": 1,
            "present_count": 1,
            "absent_count": 0,
            "student": {
                "student_id": "EDGE_SOLO",
                "net_marks": 200,
                "max_marks": 300,
                "competition_rank": 1,
                "status_band": "GREEN",
            },
            "class_average": "200.0",
            "topper_net_marks": 200,
        },
        "rounding_tie_batch": {
            "enrolled_count": 4,
            "present_count": 4,
            "absent_count": 0,
            "scores": [12, 12, 12, 13],
            "total_score_sum": 49,
            "class_average_fraction": "49/4",
            "class_average_exact": "12.25",
            "class_average_display": "12.3",
        },
        "percentage_boundaries": [
            {"input_pct": "29.99", "expected_band": "RED"},
            {"input_pct": "30.0", "expected_band": "YELLOW"},
            {"input_pct": "60.0", "expected_band": "YELLOW"},
            {"input_pct": "60.01", "expected_band": "GREEN"},
            {"input_pct": "-25.0", "expected_band": "RED"},
            {"input_pct": "0.0", "expected_band": "RED"},
        ],
    }


def generate_readme() -> str:
    """Fixture documentation (README.md)."""
    return nfc("""# Golden Fixtures (`fixtures/golden/`)

This directory contains the frozen golden fixtures for `omr_dispatch_engine` Stage S1.
All files are deterministically produced by `generate_fixtures.py` and locked by `manifest.json`.

## Fixture Inventory

1. `test_paper_300.json`: 75-question diagnostic examination (PHYSICS 1–25, CHEMISTRY 26–50, MATHS 51–75; +4/−1/0; max 300; synthetic bubble geometry).
2. `admissions_300.json`: 20-student roster (STU_01–STU_20) containing input attributes only (personalized names, sections, phone numbers, consent status, guardian verification status, and verified sibling flag).
3. `expected_contacts.json`: Expected contact quarantine and dispatch eligibility evaluations (reason codes: `INTERCEPTION_RISK_SAME_NUMBER`, `DUPLICATE_PARENT_UNVERIFIED`, `INVALID_PHONE_NUMBER`, consent/guardian exclusion reasons).
4. `submissions_300.json`: Materialized decoded responses for all 20 students (16 PRESENT, 4 ABSENT).
5. `expected_reports.json`: Frozen expected values for the 20-student OMR batch, containing exact arithmetic scores, ranks, bands, easy missed questions, and rendered parent messages.
6. `marks_entry_50.json`: 6-student manual marks entry assessment (English, Class 8-B, Max Marks 50) including half-marks and absence.
7. `expected_marks_reports.json`: Frozen expected metrics for the 6-student marks entry cohort.
8. `isolation_two_orgs.json`: Multi-tenant isolation fixture with overlapping roll numbers and identical parent phones across distinct schools.
9. `edge_cases.json`: Boundary conditions including all-wrong student (-25.0%), ties for first place, zero-present batches, single-student batches, percentage boundaries, and rounding-tie batch (49/4 = 12.25 -> 12.3).
10. `manifest.json`: Cryptographic SHA-256 integrity manifest for all fixture files.

## Invariants & Rules

- **Zero Float:** All scores and arithmetic are evaluated using integers, exact fractions, and decimal half-up quantization.
- **Numeric Representation Rule:**
  - Counts (enrolled, present, absent, attempted, correct, wrong, blank), integer marks (gross, bleed, net), and competition ranks remain JSON integers.
  - Every decimal value (percentages, averages, sums, half-marks, boundary percentages) is a JSON string with fixed decimal places:
    - `expected_reports.json`: batch metrics holds both exact rational class average `"82.6875"` and one-decimal display string `"82.7"`; student report holds table `"percentage": "18.33"` while the Hindi caption displays `"18.3%"`.
    - `expected_marks_reports.json`: holds sum `"109.5"`, average `"21.9"`, and topper `"47.0"`.
    - `edge_cases.json`: boundary percentages (`"29.99"`, `"30.0"`, `"60.0"`, `"60.01"`, `"-25.0"`, `"0.0"`) and rounding-tie average (`"12.25"` exact, `"12.3"` display) are strings.
- **Line Endings:** All files are strictly written with POSIX newline (`\\n`). No CRLF (`\\r\\n`) line endings are permitted.
- **Input/Expected Separation:** `admissions_300.json` contains raw student inputs only. Expected quarantine flags, reason codes, and dispatch eligibility are segregated in `expected_contacts.json`.
- **Unicode NFC:** All text files are strictly encoded in Unicode Normalization Form C.
- **Latin Digits:** All numeric figures in messages use standard Latin numerals (0–9).
- **No Banned Vocabulary:** No user-facing text contains forbidden D-06 terms.
""")


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    test_paper = generate_test_paper_300()
    dump_json(FIXTURES_DIR / "test_paper_300.json", test_paper)

    admissions = generate_admissions_300()
    dump_json(FIXTURES_DIR / "admissions_300.json", admissions)

    expected_contacts = generate_expected_contacts(admissions)
    dump_json(FIXTURES_DIR / "expected_contacts.json", expected_contacts)

    submissions = generate_submissions_300(test_paper)
    dump_json(FIXTURES_DIR / "submissions_300.json", submissions)

    expected_reports = generate_expected_reports(admissions)
    dump_json(FIXTURES_DIR / "expected_reports.json", expected_reports)

    marks_entry = generate_marks_entry_50()
    dump_json(FIXTURES_DIR / "marks_entry_50.json", marks_entry)

    expected_marks = generate_expected_marks_reports()
    dump_json(FIXTURES_DIR / "expected_marks_reports.json", expected_marks)

    isolation = generate_isolation_two_orgs()
    dump_json(FIXTURES_DIR / "isolation_two_orgs.json", isolation)

    edge_cases = generate_edge_cases()
    dump_json(FIXTURES_DIR / "edge_cases.json", edge_cases)

    readme_content = generate_readme()
    (FIXTURES_DIR / "README.md").write_text(readme_content, encoding="utf-8", newline="\n")

    # Generate manifest.json hashing all data files + README
    files_to_hash = [
        "fixtures/golden/test_paper_300.json",
        "fixtures/golden/admissions_300.json",
        "fixtures/golden/expected_contacts.json",
        "fixtures/golden/submissions_300.json",
        "fixtures/golden/expected_reports.json",
        "fixtures/golden/marks_entry_50.json",
        "fixtures/golden/expected_marks_reports.json",
        "fixtures/golden/isolation_two_orgs.json",
        "fixtures/golden/edge_cases.json",
        "fixtures/golden/README.md",
    ]

    files_map = {}
    for rel_path in sorted(files_to_hash):
        full_path = REPO_ROOT / rel_path
        file_bytes = full_path.read_bytes()
        files_map[rel_path] = hashlib.sha256(file_bytes).hexdigest()

    manifest_data = {
        "schema_version": 1,
        "fixture_version": "1.0.0",
        "files": files_map,
    }
    dump_json(FIXTURES_DIR / "manifest.json", manifest_data)

    manifest_bytes = (FIXTURES_DIR / "manifest.json").read_bytes()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    sys.stdout.write("[GENERATOR] Golden fixtures successfully generated.\n")
    sys.stdout.write(f"[GENERATOR] manifest.json SHA-256: {manifest_sha}\n")


if __name__ == "__main__":
    main()
