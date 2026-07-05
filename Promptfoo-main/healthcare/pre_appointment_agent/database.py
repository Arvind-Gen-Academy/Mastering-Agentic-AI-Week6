"""SQLite schema and the seeded mock patient data.

`init_db()` is idempotent (INSERT OR REPLACE) so it is safe to call from both
the notebook and server startup.
"""

import sqlite3

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id     INTEGER PRIMARY KEY,
    name           TEXT,
    age            INTEGER,
    sex            TEXT,
    blood_group    TEXT,
    conditions     TEXT,
    primary_doctor TEXT
);

CREATE TABLE IF NOT EXISTS visits (
    visit_id     INTEGER PRIMARY KEY,
    patient_id   INTEGER,
    visit_date   TEXT,
    reason       TEXT,
    symptoms     TEXT,
    diagnosis    TEXT,
    notes        TEXT,
    doctor_name  TEXT
);

CREATE TABLE IF NOT EXISTS medications (
    med_id       INTEGER PRIMARY KEY,
    patient_id   INTEGER,
    drug_name    TEXT,
    dosage       TEXT,
    frequency    TEXT,
    start_date   TEXT,
    is_active    INTEGER
);

CREATE TABLE IF NOT EXISTS vitals (
    vital_id       INTEGER PRIMARY KEY,
    patient_id     INTEGER,
    visit_id       INTEGER,
    recorded_date  TEXT,
    bp_systolic    INTEGER,
    bp_diastolic   INTEGER,
    heart_rate     INTEGER,
    blood_sugar    REAL,
    weight_kg      REAL
);

CREATE TABLE IF NOT EXISTS allergies (
    allergy_id  INTEGER PRIMARY KEY,
    patient_id  INTEGER,
    allergen    TEXT,
    reaction    TEXT,
    severity    TEXT
);

CREATE TABLE IF NOT EXISTS followups (
    followup_id  INTEGER PRIMARY KEY,
    patient_id   INTEGER,
    visit_id     INTEGER,
    recommended  TEXT,
    due_date     TEXT,
    is_done      INTEGER
);
"""

# ── PATIENTS — basic profile for each patient ───────
PATIENTS = [
    (1, 'Ravi Sharma',    58, 'M', 'B+', 'Type 2 Diabetes, Hypertension',        'Dr. Priya Nair'),
    (2, 'Anita Menon',    45, 'F', 'A+', 'Hypothyroidism',                        'Dr. Priya Nair'),
    (3, "Samuel D'Cruz",  67, 'M', 'O+', 'Hypertension, Coronary Artery Disease', 'Dr. Arjun Mehta'),
    (4, 'Fatima Sheikh',  34, 'F', 'B-', 'Asthma',                                'Dr. Arjun Mehta'),
    (5, 'Ramesh Iyer',    72, 'M', 'AB+', 'Type 2 Diabetes, CKD Stage 2',         'Dr. Priya Nair'),
]

# ── VISITS — 2 visits per patient, linked by patient_id ─
VISITS = [
    # Ravi Sharma (patient_id = 1)
    (1,  1, '2024-06-10', 'Routine checkup',            'Mild fatigue',                    'Type 2 Diabetes - controlled',              'HbA1c improving',                      'Dr. Priya Nair'),
    (2,  1, '2024-11-05', 'Diabetes and BP review',     'Fatigue, occasional dizziness',   'Type 2 Diabetes - borderline, BP elevated', 'Patient stressed at work',             'Dr. Priya Nair'),
    # Anita Menon (patient_id = 2)
    (3,  2, '2024-05-20', 'Routine checkup',            'Tiredness, weight gain',          'Hypothyroidism - controlled',               'TSH slightly high, dose reviewed',     'Dr. Priya Nair'),
    (4,  2, '2024-10-15', 'Thyroid review',             'Persistent fatigue, hair loss',   'Hypothyroidism - undertreated',             'TSH still elevated after dose change', 'Dr. Priya Nair'),
    # Samuel D'Cruz (patient_id = 3)
    (5,  3, '2024-04-08', 'Chest discomfort',           'Mild chest tightness on exertion', 'Stable angina',                            'Stress ECG ordered',                   'Dr. Arjun Mehta'),
    (6,  3, '2024-09-22', 'Cardiac review',             'Occasional breathlessness',       'CAD - stable, BP borderline high',          'Stress ECG not done yet',              'Dr. Arjun Mehta'),
    # Fatima Sheikh (patient_id = 4)
    (7,  4, '2024-07-11', 'Asthma review',              'Wheezing, shortness of breath',   'Mild persistent asthma',                    'Inhaler technique reviewed',           'Dr. Arjun Mehta'),
    (8,  4, '2024-12-01', 'Acute visit',                'Worsening wheeze, cough',         'Asthma exacerbation',                       'Triggered by dust at new workplace',   'Dr. Arjun Mehta'),
    # Ramesh Iyer (patient_id = 5)
    (9,  5, '2024-03-14', 'Routine checkup',            'Swollen ankles, fatigue',         'Type 2 Diabetes with CKD Stage 2',          'eGFR declining slowly',                'Dr. Priya Nair'),
    (10, 5, '2024-10-30', 'Diabetes and kidney review', 'Increased swelling, low energy',  'CKD progressing, diabetes uncontrolled',    'Metformin dose reduced',               'Dr. Priya Nair'),
]

# ── MEDICATIONS — active meds per patient, linked by patient_id ─
MEDICATIONS = [
    # Ravi (patient_id = 1) — 3 medications
    (1,  1, 'Metformin',        '500mg',    'Twice daily',   '2022-03-01', 1),
    (2,  1, 'Amlodipine',       '5mg',      'Once daily',    '2023-01-15', 1),
    (3,  1, 'Aspirin',          '75mg',     'Once daily',    '2023-01-15', 1),
    # Anita (patient_id = 2) — 1 medication
    (4,  2, 'Levothyroxine',    '50mcg',    'Once daily',    '2021-08-10', 1),
    # Samuel (patient_id = 3) — 4 medications
    (5,  3, 'Amlodipine',       '10mg',     'Once daily',    '2020-06-01', 1),
    (6,  3, 'Atorvastatin',     '40mg',     'Once at night', '2020-06-01', 1),
    (7,  3, 'Aspirin',          '75mg',     'Once daily',    '2020-06-01', 1),
    (8,  3, 'Nitroglycerin',    '0.5mg',    'As needed',     '2024-04-08', 1),
    # Fatima (patient_id = 4) — 2 medications
    (9,  4, 'Salbutamol',       '100mcg',   'As needed',     '2022-02-15', 1),
    (10, 4, 'Budesonide',       '200mcg',   'Twice daily',   '2022-02-15', 1),
    # Ramesh (patient_id = 5) — 3 medications
    (11, 5, 'Metformin',        '500mg',    'Once daily',    '2019-05-20', 1),
    (12, 5, 'Insulin Glargine', '10 units', 'Once at night', '2023-09-01', 1),
    (13, 5, 'Amlodipine',       '5mg',      'Once daily',    '2021-03-10', 1),
]

# ── VITALS — one row per visit, linked by patient_id and visit_id ─
VITALS = [
    # Ravi (patient_id = 1)
    (1,  1, 1,  '2024-06-10', 128, 82, 74, 138.0, 78.0),
    (2,  1, 2,  '2024-11-05', 145, 94, 80, 162.0, 79.5),
    # Anita (patient_id = 2)
    (3,  2, 3,  '2024-05-20', 118, 76, 72,  92.0, 68.0),
    (4,  2, 4,  '2024-10-15', 122, 78, 75,  95.0, 70.5),
    # Samuel (patient_id = 3)
    (5,  3, 5,  '2024-04-08', 138, 88, 82,  98.0, 84.0),
    (6,  3, 6,  '2024-09-22', 148, 92, 85, 101.0, 85.5),
    # Fatima (patient_id = 4)
    (7,  4, 7,  '2024-07-11', 112, 72, 88,  88.0, 62.0),
    (8,  4, 8,  '2024-12-01', 116, 74, 102, 90.0, 62.5),
    # Ramesh (patient_id = 5)
    (9,  5, 9,  '2024-03-14', 132, 84, 76, 178.0, 71.0),
    (10, 5, 10, '2024-10-30', 138, 88, 79, 195.0, 69.5),
]

# ── ALLERGIES — known allergens per patient, linked by patient_id ─
# Note: patients 2 (Anita) and 4 (Fatima) have no recorded allergies.
ALLERGIES = [
    (1, 1, 'Penicillin',  'Rash and swelling', 'Moderate'),  # Ravi
    (2, 3, 'Sulfa drugs', 'Hives',             'Mild'),       # Samuel
    (3, 4, 'NSAIDs',      'Bronchospasm',      'Severe'),      # Fatima
    (4, 5, 'Penicillin',  'Anaphylaxis',       'Severe'),      # Ramesh
]

# ── FOLLOWUPS — pending tasks raised during visits ─
# is_done: 0 = pending, 1 = completed
FOLLOWUPS = [
    (1, 1, 2,  'HbA1c blood test',            '2024-12-05', 0),  # Ravi — raised at visit 2
    (2, 3, 5,  'Stress ECG',                  '2024-06-01', 0),  # Samuel — raised at visit 5
    (3, 3, 6,  'Kidney function test',        '2024-11-01', 0),  # Samuel — raised at visit 6
    (4, 5, 9,  'eGFR and urine protein test', '2024-06-01', 1),  # Ramesh — completed
    (5, 5, 10, 'Nephrology referral',         '2024-12-01', 0),  # Ramesh — raised at visit 10
]


def init_db() -> None:
    """Create the schema and seed the 5 mock patients. Idempotent."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executescript(SCHEMA)

    cursor.executemany("INSERT OR REPLACE INTO patients VALUES (?, ?, ?, ?, ?, ?, ?)", PATIENTS)
    cursor.executemany(
        "INSERT OR REPLACE INTO visits (visit_id, patient_id, visit_date, reason, symptoms, diagnosis, notes, doctor_name)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        VISITS,
    )
    cursor.executemany(
        "INSERT OR REPLACE INTO medications (med_id, patient_id, drug_name, dosage, frequency, start_date, is_active)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        MEDICATIONS,
    )
    cursor.executemany(
        "INSERT OR REPLACE INTO vitals (vital_id, patient_id, visit_id, recorded_date, bp_systolic, bp_diastolic, heart_rate, blood_sugar, weight_kg)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        VITALS,
    )
    cursor.executemany("INSERT OR REPLACE INTO allergies VALUES (?, ?, ?, ?, ?)", ALLERGIES)
    cursor.executemany("INSERT OR REPLACE INTO followups VALUES (?, ?, ?, ?, ?, ?)", FOLLOWUPS)

    conn.commit()
    conn.close()
