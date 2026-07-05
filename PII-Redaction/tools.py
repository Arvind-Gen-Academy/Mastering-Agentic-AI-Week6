import re

from langchain_core.tools import tool

import db
from pii_handler import PIIHandler

DEPARTMENTS = {
    "General Medicine": ["Dr. Sharma", "Dr. Patel"],
    "Cardiology":       ["Dr. Mehta",  "Dr. Gupta"],
    "Orthopedics":      ["Dr. Singh",  "Dr. Verma"],
    "Neurology":        ["Dr. Reddy",  "Dr. Iyer"],
    "Pediatrics":       ["Dr. Nair",   "Dr. Das"],
    "Dermatology":      ["Dr. Shah",   "Dr. Joshi"],
    "Ophthalmology":    ["Dr. Kumar",  "Dr. Rao"],
    "ENT":              ["Dr. Bose",   "Dr. Malhotra"],
    "Gynecology":       ["Dr. Pillai", "Dr. Menon"],
    "Psychiatry":       ["Dr. Kapoor", "Dr. Chopra"],
}

# ── Triage keyword rules ───────────────────────────────────────────────────────

_DEPT_KEYWORDS: dict[str, list[str]] = {
    "Cardiology":       ["chest pain", "heart", "palpitation", "cardiac", "shortness of breath",
                         "breathless", "angina", "arrhythmia"],
    "Neurology":        ["headache", "migraine", "seizure", "stroke", "dizzy", "dizziness",
                         "numbness", "tingling", "memory loss", "confusion", "tremor"],
    "Orthopedics":      ["bone", "joint", "fracture", "back pain", "knee", "shoulder", "hip",
                         "spine", "arthritis", "ligament", "sprain"],
    "Gynecology":       ["pregnancy", "menstrual", "period", "ovary", "uterus", "pelvic",
                         "vaginal", "cervical", "breast"],
    "Pediatrics":       ["child", "infant", "baby", "pediatric", "growth", "vaccination", "newborn"],
    "Dermatology":      ["skin", "rash", "acne", "eczema", "psoriasis", "itch", "hives",
                         "fungal", "wound"],
    "Ophthalmology":    ["eye", "vision", "sight", "blind", "cataract", "glaucoma", "retina"],
    "ENT":              ["ear", "nose", "throat", "hearing", "sinus", "tonsil", "voice",
                         "nasal", "snoring"],
    "Psychiatry":       ["anxiety", "depression", "mental", "stress", "insomnia", "sleep",
                         "mood", "panic", "suicidal", "hallucination"],
    "General Medicine": ["fever", "cold", "flu", "fatigue", "weakness", "appetite", "weight",
                         "diabetes", "blood pressure", "hypertension", "cough", "vomiting",
                         "diarrhea", "infection", "pain"],
}

_HIGH_URGENCY = ["chest pain", "shortness of breath", "stroke", "seizure", "unconscious",
                 "severe", "acute", "heavy bleeding", "fracture", "suicidal", "hallucination",
                 "arrhythmia", "angina"]
_MEDIUM_URGENCY = ["fever", "vomiting", "infection", "dizzy", "moderate", "persistent"]


def _classify_triage(complaint: str) -> dict:
    text = complaint.lower()

    # Department
    dept = "General Medicine"
    for department, keywords in _DEPT_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            dept = department
            break

    # Urgency
    if any(kw in text for kw in _HIGH_URGENCY):
        urgency = "HIGH"
    elif any(kw in text for kw in _MEDIUM_URGENCY):
        urgency = "MEDIUM"
    else:
        urgency = "LOW"

    return {"urgency": urgency, "department": dept}


def _is_token(value: str) -> bool:
    return bool(re.match(r"^TOKEN_[A-Z_]+_\d+$", value.strip()))


def make_tools(pii: PIIHandler) -> tuple[list, list]:
    """Return (patient_tools, staff_tools) with PIIHandler bound via closure.

    Tools are split per portal so each agent only binds the tools relevant
    to its workflow — a smaller tool surface reduces malformed tool-call
    generations from the underlying LLM.
    """

    # ── Patient-side tools ─────────────────────────────────────────────────────

    @tool
    def register_patient(
        name: str, age: str, sex: str, phone: str, email: str,
        complaint: str, department: str, doctor: str,
    ) -> str:
        """Register a new patient after all eight fields are confirmed.

        Args:
            name: Patient full name or anonymized token.
            age: Patient age.
            sex: Patient sex / gender.
            phone: Patient phone number or anonymized token.
            email: Patient email address or anonymized token.
            complaint: Main medical complaint.
            department: Medical department.
            doctor: Preferred doctor name.
        """
        missing = [f for f, v in [
            ("complaint", complaint), ("department", department), ("doctor", doctor)
        ] if not v or not v.strip()]
        if missing:
            return f"Error: still need — {', '.join(missing)}. Collect these first."

        real_info = {
            "name":       pii.deredact(name),
            "age":        pii.deredact(age),
            "sex":        pii.deredact(sex),
            "phone":      pii.deredact(phone),
            "email":      pii.deredact(email),
            "complaint":  complaint,
            "department": department,
            "doctor":     pii.deredact(doctor),
        }
        patient_id = db.save_registration(real_info)
        return f"Registration complete. Patient ID: {patient_id}"

    @tool
    def open_new_visit(
        patient_id: str,
        complaint: str,
        department: str,
        doctor: str,
    ) -> str:
        """Open a new visit encounter for an existing returning patient.

        Use this instead of register_patient when the patient already exists.
        Call get_patient_ehr first to obtain the patient_id.

        Args:
            patient_id: The patient UUID from get_patient_ehr.
            complaint: The patient's medical complaint for this new visit.
            department: Medical department for this visit.
            doctor: Preferred doctor name.
        """
        patient = db.get_patient_by_id(patient_id)
        if not patient:
            return f"Error: no patient found with ID {patient_id}. Register as a new patient instead."

        prev_visits = len(patient.get("encounters", []))
        enc_id = db.open_encounter(patient_id, {
            "complaint":  complaint,
            "department": department,
            "doctor":     pii.deredact(doctor),
        })
        return (
            f"New visit opened. Patient ID: {patient_id}. "
            f"Encounter ID: {enc_id}. "
            f"Visit #{prev_visits + 1} for this patient."
        )

    @tool
    def collect_pre_visit_info(
        patient_id: str,
        allergies: str,
        current_medications: str,
        medical_history: str,
    ) -> str:
        """Record pre-visit medical information for a registered patient.

        Args:
            patient_id: The patient ID returned by register_patient.
            allergies: Known allergies (comma-separated, or 'none').
            current_medications: Current medications (comma-separated, or 'none').
            medical_history: Relevant past medical history.
        """
        enc = db.get_open_encounter(patient_id)
        if not enc:
            return f"Error: no open encounter found for patient {patient_id}."

        eid = enc["encounter_id"]
        if allergies and allergies.lower() != "none":
            db.update_clinical(patient_id, eid, "allergies",
                               [pii.deredact(a.strip()) for a in allergies.split(",")])
        if current_medications and current_medications.lower() != "none":
            db.update_clinical(patient_id, eid, "current_medications",
                               [pii.deredact(m.strip()) for m in current_medications.split(",")])
        if medical_history and medical_history.lower() != "none":
            db.update_clinical(patient_id, eid, "medical_history", pii.deredact(medical_history))

        return "Pre-visit information recorded. The care team will review it before your appointment."

    # ── Staff-side tools ───────────────────────────────────────────────────────

    @tool
    def get_patient_ehr(name_token_or_id: str) -> str:
        """Look up a patient's full EHR including all encounters and clinical data.

        Accepts either an anonymized name token (e.g. <PERSON_0>) or a patient ID (UUID).

        Args:
            name_token_or_id: Anonymized name token or patient UUID.
        """
        if _is_token(name_token_or_id):
            real_name = pii.deredact(name_token_or_id)
            patient = db.get_patient_by_name(real_name)
        else:
            patient = db.get_patient_by_id(name_token_or_id)

        if not patient:
            return "Patient not found. Check the name or ID and try again."

        # Re-tokenize sensitive patient fields
        p = patient["patient"]
        safe_patient = {
            "patient_id": patient["_id"],
            "name":       pii.redact(p.get("name") or ""),
            "age":        p.get("age"),
            "sex":        p.get("sex"),
            "phone":      pii.redact(p.get("phone") or ""),
            "email":      pii.redact(p.get("email") or ""),
        }

        # Tokenize doctor names in encounters; keep clinical data as-is
        safe_encounters = []
        for enc in patient.get("encounters", []):
            visit = enc.get("visit", {})
            safe_enc = {
                "encounter_id":   enc["encounter_id"],
                "admission_date": enc.get("admission_date"),
                "discharge_date": enc.get("discharge_date"),
                "status":         enc.get("status"),
                "visit": {
                    "complaint":  visit.get("complaint"),
                    "department": visit.get("department"),
                    "doctor":     pii.redact(visit.get("doctor") or ""),
                },
                "clinical": enc.get("clinical", {}),
            }
            safe_encounters.append(safe_enc)

        import json as _json
        result = _json.dumps({**safe_patient, "encounters": safe_encounters}, indent=2)
        return result

    @tool
    def update_encounter_clinical(
        patient_id: str,
        field: str,
        value: str,
    ) -> str:
        """Add clinical information to the patient's current open encounter.

        Valid fields: allergies, current_medications, diagnoses, procedures, notes, lab_results.

        Args:
            patient_id: The patient UUID (from get_patient_ehr).
            field: Clinical field to update.
            value: Value to add (appended to list fields).
        """
        valid_fields = {"allergies", "current_medications", "diagnoses",
                        "procedures", "notes", "lab_results"}
        if field not in valid_fields:
            return f"Invalid field '{field}'. Choose from: {', '.join(sorted(valid_fields))}."

        enc = db.get_open_encounter(patient_id)
        if not enc:
            return f"No open encounter found for patient {patient_id}. Has the patient been discharged already?"

        db.update_clinical(patient_id, enc["encounter_id"], field, pii.deredact(value))
        return f"Added to {field}: {pii.deredact(value)}"

    @tool
    def close_encounter_discharge(
        patient_id: str,
        discharge_summary: str,
        followup_instructions: str,
        followup_dates: str,
    ) -> str:
        """Close the patient's current encounter with a discharge summary.

        Write a complete discharge summary before calling this tool. The summary
        may contain anonymized tokens — they will be resolved to real values before saving.

        Args:
            patient_id: The patient UUID (from get_patient_ehr).
            discharge_summary: Full narrative discharge summary (may contain PII tokens).
            followup_instructions: Instructions for the patient post-discharge.
            followup_dates: Comma-separated follow-up dates in YYYY-MM-DD format (e.g. '2026-07-03,2026-07-07').
        """
        enc = db.get_open_encounter(patient_id)
        if not enc:
            return f"No open encounter for patient {patient_id}."

        real_summary = pii.deredact(discharge_summary)
        real_followup = pii.deredact(followup_instructions)
        dates = [d.strip() for d in followup_dates.split(",") if d.strip()]

        db.close_encounter(
            patient_id,
            enc["encounter_id"],
            real_summary,
            real_followup,
            dates,
        )
        return (
            f"Encounter closed. Patient discharged. "
            f"Follow-up dates scheduled: {', '.join(dates)}."
        )

    @tool
    def send_patient_followup(patient_token_or_id: str, message: str) -> str:
        """Send a personalised follow-up message to a discharged patient.

        Compose the full message yourself using the patient's clinical data
        before calling this tool. PII tokens in the message are resolved to
        real values before sending.

        Args:
            patient_token_or_id: Anonymized name token (e.g. <PERSON_0>) or patient UUID.
            message: The complete follow-up message to send to the patient.
        """
        if _is_token(patient_token_or_id):
            real_name = pii.deredact(patient_token_or_id)
            patient = db.get_patient_by_name(real_name)
        else:
            patient = db.get_patient_by_id(patient_token_or_id)

        if not patient:
            return "Patient not found. Check the name or ID."

        real_name  = patient["patient"].get("name", "Patient")
        phone      = patient["patient"].get("phone", "")
        email      = patient["patient"].get("email", "")
        real_msg   = pii.deredact(message)

        # Find most recent discharged encounter and mark a pending follow-up as sent
        discharged_enc = next(
            (e for e in reversed(patient.get("encounters", []))
             if e.get("status") == "discharged"),
            None,
        )
        if discharged_enc:
            clinical = discharged_enc.get("clinical", {})
            pending  = [
                d for d in clinical.get("followup_dates", [])
                if d not in clinical.get("followup_sent", [])
            ]
            if pending:
                db.mark_followup_sent(
                    patient["_id"], discharged_enc["encounter_id"], pending[0]
                )

        # In production: replace the return below with your email/SMS call.
        # e.g. send_email(to=email, body=real_msg) or twilio_sms(to=phone, body=real_msg)
        return (
            f"Follow-up sent to {real_name}.\n"
            f"  Email: {email}  |  Phone: {phone}\n\n"
            f"Message:\n{real_msg}"
        )

    # triage_complaint is intentionally excluded: the LLM reasons about
    # department from DEPARTMENTS_INFO in the prompt, removing the risk of
    # a premature tool call during the greeting phase.
    patient_tools = [
        register_patient,
        open_new_visit,
        collect_pre_visit_info,
        get_patient_ehr,
    ]
    staff_tools = [
        get_patient_ehr,
        update_encounter_clinical,
        close_encounter_discharge,
        send_patient_followup,
    ]
    return patient_tools, staff_tools
