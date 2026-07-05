import json
import os
import uuid
from datetime import datetime, timezone

_DIR = os.path.dirname(__file__)
PATIENTS_FILE = os.path.join(_DIR, "patients.json")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load() -> list[dict]:
    if not os.path.exists(PATIENTS_FILE):
        return []
    try:
        with open(PATIENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _write(patients: list[dict]) -> None:
    with open(PATIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(patients, f, indent=2, ensure_ascii=False)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _blank_clinical() -> dict:
    return {
        "allergies":             [],
        "current_medications":   [],
        "medical_history":       [],
        "diagnoses":             [],
        "procedures":            [],
        "notes":                 [],
        "lab_results":           [],
        "discharge_summary":     None,
        "followup_instructions": None,
        "followup_dates":        [],
        "followup_sent":         [],
    }


# ── Patient CRUD ──────────────────────────────────────────────────────────────

def create_patient(demographics: dict) -> str:
    """Create a new patient record. Returns patient_id."""
    patients = _load()
    patient_id = str(uuid.uuid4())
    doc = {
        "_id":        patient_id,
        "created_at": _now(),
        "patient": {
            "name":  demographics.get("name"),
            "age":   demographics.get("age"),
            "sex":   demographics.get("sex"),
            "phone": demographics.get("phone"),
            "email": demographics.get("email"),
        },
        "encounters": [],
    }
    patients.append(doc)
    _write(patients)
    return patient_id


def get_patient_by_id(patient_id: str) -> dict | None:
    return next((p for p in _load() if p["_id"] == patient_id), None)


def get_patient_by_name(name: str) -> dict | None:
    name_lower = name.lower().strip()
    return next(
        (p for p in _load()
         if (p.get("patient", {}).get("name") or "").lower() == name_lower),
        None,
    )


def load_all_patients() -> list[dict]:
    return _load()


# ── Encounter CRUD ────────────────────────────────────────────────────────────

def open_encounter(patient_id: str, visit_info: dict) -> str:
    """Append a new Encounter to the patient. Returns encounter_id."""
    patients = _load()
    encounter_id = str(uuid.uuid4())
    encounter = {
        "encounter_id":   encounter_id,
        "admission_date": _now(),
        "discharge_date": None,
        "status":         "registered",
        "visit": {
            "complaint":  visit_info.get("complaint"),
            "department": visit_info.get("department"),
            "doctor":     visit_info.get("doctor"),
        },
        "clinical": _blank_clinical(),
    }
    for p in patients:
        if p["_id"] == patient_id:
            p["encounters"].append(encounter)
            break
    _write(patients)
    return encounter_id


def get_open_encounter(patient_id: str) -> dict | None:
    """Return the most recent non-discharged encounter, or None."""
    patient = get_patient_by_id(patient_id)
    if not patient:
        return None
    for enc in reversed(patient.get("encounters", [])):
        if enc.get("status") != "discharged":
            return enc
    return None


def update_encounter(patient_id: str, encounter_id: str, updates: dict) -> None:
    """Patch top-level fields on a specific encounter."""
    patients = _load()
    for p in patients:
        if p["_id"] == patient_id:
            for enc in p["encounters"]:
                if enc["encounter_id"] == encounter_id:
                    enc.update(updates)
                    break
            break
    _write(patients)


def update_clinical(patient_id: str, encounter_id: str, field: str, value) -> None:
    """Append value to a list clinical field, or set it if scalar."""
    patients = _load()
    for p in patients:
        if p["_id"] == patient_id:
            for enc in p["encounters"]:
                if enc["encounter_id"] == encounter_id:
                    clinical = enc.setdefault("clinical", _blank_clinical())
                    existing = clinical.get(field)
                    if isinstance(existing, list):
                        if isinstance(value, list):
                            existing.extend(value)
                        else:
                            existing.append(value)
                    else:
                        clinical[field] = value
                    break
            break
    _write(patients)


def close_encounter(
    patient_id: str,
    encounter_id: str,
    discharge_summary: str,
    followup_instructions: str,
    followup_dates: list[str],
) -> None:
    """Stamp discharge fields and mark the encounter as discharged."""
    patients = _load()
    for p in patients:
        if p["_id"] == patient_id:
            for enc in p["encounters"]:
                if enc["encounter_id"] == encounter_id:
                    enc["discharge_date"] = _now()
                    enc["status"] = "discharged"
                    clinical = enc.setdefault("clinical", _blank_clinical())
                    clinical["discharge_summary"]     = discharge_summary
                    clinical["followup_instructions"] = followup_instructions
                    clinical["followup_dates"]        = followup_dates
                    clinical["followup_sent"]         = []
                    break
            break
    _write(patients)


def mark_followup_sent(patient_id: str, encounter_id: str, date_str: str) -> None:
    """Record that a follow-up reminder was sent for a given date."""
    patients = _load()
    for p in patients:
        if p["_id"] == patient_id:
            for enc in p["encounters"]:
                if enc["encounter_id"] == encounter_id:
                    enc.setdefault("clinical", {}).setdefault("followup_sent", []).append(date_str)
                    break
            break
    _write(patients)


# ── Legacy compatibility ───────────────────────────────────────────────────────

def save_registration(info: dict) -> str:
    """Compatibility shim: create patient + open first encounter. Returns patient_id."""
    patient_id   = create_patient(info)
    open_encounter(patient_id, info)
    return patient_id


def load_registrations() -> list[dict]:
    """Alias kept for dashboard backward compatibility."""
    return load_all_patients()
