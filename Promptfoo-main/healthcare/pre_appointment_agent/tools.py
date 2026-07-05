"""The SQLite retrieval tool exposed to the agent.

Read-only: it only issues SELECT queries against the patient database.
"""

import json
import sqlite3

from langchain_core.tools import Tool

from .config import DB_PATH


def get_patient_data(patient_id: str) -> str:
    """Fetch a patient's profile, last 2 visits, active meds, vitals,
    allergies, and follow-ups as a JSON string."""
    pid = int(patient_id.strip())
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (pid,))
    patient = cursor.fetchone()
    if not patient:
        conn.close()
        return "Patient not found."

    cursor.execute(
        """
        SELECT visit_date, reason, symptoms, diagnosis, notes, doctor_name
        FROM visits WHERE patient_id = ?
        ORDER BY visit_date DESC LIMIT 2
        """,
        (pid,),
    )
    visits = cursor.fetchall()

    cursor.execute(
        "SELECT drug_name, dosage, frequency, start_date FROM medications WHERE patient_id = ? AND is_active = 1",
        (pid,),
    )
    meds = cursor.fetchall()

    cursor.execute(
        "SELECT visit_id, recorded_date, bp_systolic, bp_diastolic, heart_rate, blood_sugar, weight_kg"
        " FROM vitals WHERE patient_id = ? ORDER BY recorded_date DESC",
        (pid,),
    )
    vitals = cursor.fetchall()

    cursor.execute("SELECT allergen, reaction, severity FROM allergies WHERE patient_id = ?", (pid,))
    allergies = cursor.fetchall()

    cursor.execute("SELECT recommended, due_date, is_done FROM followups WHERE patient_id = ?", (pid,))
    followups = cursor.fetchall()

    conn.close()

    result = {
        "patient": dict(zip(["id", "name", "age", "sex", "blood_group", "conditions", "primary_doctor"], patient)),
        "visits": [dict(zip(["date", "reason", "symptoms", "diagnosis", "notes", "doctor"], v)) for v in visits],
        "medications": [dict(zip(["drug", "dosage", "frequency", "since"], m)) for m in meds],
        "vitals": [dict(zip(["visit_id", "date", "bp_sys", "bp_dia", "hr", "blood_sugar", "weight_kg"], v)) for v in vitals],
        "allergies": [dict(zip(["allergen", "reaction", "severity"], a)) for a in allergies],
        "followups": [dict(zip(["recommended", "due_date", "is_done"], f)) for f in followups],
    }
    return json.dumps(result, indent=2)


sqlite_tool = Tool(
    name="get_patient_data",
    func=get_patient_data,
    description=(
        "Fetches all patient data from the database given a patient ID. Returns profile, "
        "last 2 visits, medications, vitals, allergies, and follow-ups."
    ),
)
