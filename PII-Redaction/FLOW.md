# Patient Registration Flow

## What is the Entity Map?

A **map** (also called a dictionary) is just a lookup table — like a real dictionary where you look up a word to get its definition. Here it maps a token to the original value:

```
TOKEN_PERSON_0        →  "John Smith"
TOKEN_PHONE_NUMBER_0  →  "9876543210"
TOKEN_EMAIL_ADDRESS_0 →  "john@gmail.com"
TOKEN_AGE_0           →  "35 years old"
TOKEN_SEX_0           →  "Male"
```

Tokens are formatted `TOKEN_<TYPE>_<N>`. They are **stable within a session** — the same original value always gets the same token. When the system needs the real value back, it just looks up the token in this table.

---

## Step-by-Step: Registering a New Patient

### Step 1 — User opens the app
- Streamlit starts and `init_session()` runs once (`app.py`).
- Objects are created and stored in session state:
  - `PIIHandler` — holds the entity map and redaction logic
  - `patient_tools` — built by `make_tools(pii)`, with the PIIHandler baked in
  - `agent` — built by `build_agent(api_key, patient_tools, role="patient")`; the LLM (OpenAI GPT-4o mini) wired up with those tools and the patient system prompt
- On first render the app sends a hidden `"Hello, I'd like to register."` message so the agent replies with a greeting.

---

### Step 2 — Agent greets, then figures out new vs returning
- The agent's **first message is only a greeting** — no tool is called yet, because no patient token exists in the conversation.
- After the patient replies, the agent decides:
  - **Returning patient** ("I've been here before") → it asks for the name, calls `get_patient_ehr()`, confirms identity, and opens a new visit with `open_new_visit()` (see the returning-patient branch at the end).
  - **New patient** → it proceeds through registration below.

---

### Step 3 — User types their name
**User types:** `"John Smith"`

1. `app.py` receives the raw text.
2. `pii.redact("John Smith")` is called:
   - Presidio detects "John Smith" as a PERSON entity.
   - A token `TOKEN_PERSON_0` is created.
   - The entity map is updated: `{ "TOKEN_PERSON_0": "John Smith" }`
   - Returns the string `"TOKEN_PERSON_0"`.
3. `"TOKEN_PERSON_0"` is sent to OpenAI. **OpenAI never sees "John Smith".**
4. The agent replies: *"Thank you! What is your age?"*

---

### Step 4 — User provides remaining details (age, sex, phone, email)

Each message goes through the same cycle:
- Raw text → `pii.redact()` → token sent to OpenAI
- The entity map grows with each new piece of PII detected:

```
{
  "TOKEN_PERSON_0":        "John Smith",
  "TOKEN_AGE_0":           "35 years old",
  "TOKEN_SEX_0":           "Male",
  "TOKEN_PHONE_NUMBER_0":  "9876543210",
  "TOKEN_EMAIL_ADDRESS_0": "john@gmail.com"
}
```

The agent asks for **one field at a time** and waits for each answer.

---

### Step 5 — User describes their complaint
**User types:** `"I have chest pain"`

- No PII detected → text passes through unchanged.
- OpenAI sees: `"I have chest pain"`
- The agent **triages** the complaint: "chest pain" is a HIGH-urgency keyword, so it advises calling emergency services and asks whether to still register a follow-up. It then suggests **Cardiology** and asks for a preferred doctor.

---

### Step 6 — User confirms department and doctor
**User types:** `"Dr. Mehta"`

1. Presidio may detect "Dr. Mehta" as a PERSON:
   - Token `TOKEN_PERSON_1` is created.
   - Entity map updated: `{ ..., "TOKEN_PERSON_1": "Dr. Mehta" }`
2. OpenAI sees `"TOKEN_PERSON_1"`.

---

### Step 7 — Agent calls `register_patient()`

OpenAI now has all 8 fields and calls the tool with tokens:

```
register_patient(
    name       = "TOKEN_PERSON_0",
    age        = "TOKEN_AGE_0",
    sex        = "TOKEN_SEX_0",
    phone      = "TOKEN_PHONE_NUMBER_0",
    email      = "TOKEN_EMAIL_ADDRESS_0",
    complaint  = "chest pain",
    department = "Cardiology",
    doctor     = "TOKEN_PERSON_1"
)
```

---

### Step 8 — `tools.py` de-anonymizes using the entity map

`pii.deredact()` looks up each token in the **same entity map** built during the conversation:

```
"TOKEN_PERSON_0"        →  "John Smith"
"TOKEN_AGE_0"           →  "35 years old"
"TOKEN_SEX_0"           →  "Male"
"TOKEN_PHONE_NUMBER_0"  →  "9876543210"
"TOKEN_EMAIL_ADDRESS_0" →  "john@gmail.com"
"TOKEN_PERSON_1"        →  "Dr. Mehta"
```

Result (real values restored):
```python
real_info = {
    "name":       "John Smith",
    "age":        "35 years old",
    "sex":        "Male",
    "phone":      "9876543210",
    "email":      "john@gmail.com",
    "complaint":  "chest pain",
    "department": "Cardiology",
    "doctor":     "Dr. Mehta"
}
```

This all happens **locally on your server**.

---

### Step 9 — `db.py` saves to `patients.json`

`save_registration(real_info)` creates a patient record **and opens their first encounter**. Each patient document holds demographics plus a list of `encounters`, each with its own visit info and clinical data:

```json
{
  "_id": "a3f9c-...",
  "created_at": "2026-07-04T15:00:00Z",
  "patient": {
    "name":  "John Smith",
    "age":   "35 years old",
    "sex":   "Male",
    "phone": "9876543210",
    "email": "john@gmail.com"
  },
  "encounters": [
    {
      "encounter_id":   "b7e21-...",
      "admission_date": "2026-07-04T15:00:00Z",
      "discharge_date": null,
      "status":         "registered",
      "visit": {
        "complaint":  "chest pain",
        "department": "Cardiology",
        "doctor":     "Dr. Mehta"
      },
      "clinical": {
        "allergies": [], "current_medications": [], "medical_history": [],
        "diagnoses": [], "procedures": [], "notes": [], "lab_results": [],
        "discharge_summary": null, "followup_instructions": null,
        "followup_dates": [], "followup_sent": []
      }
    }
  ]
}
```

The tool returns `"Registration complete. Patient ID: <id>"`. The **Hospital Dashboard** reads this file and shows the full real details.

---

### Step 10 — Pre-visit intake (PHASE 2)

Once registration succeeds, the chat input stays active and the agent moves to pre-visit intake:

1. It confirms registration and offers to note **allergies, current medications, and medical history**.
2. Whatever the patient shares is redacted like any other message, then passed to `collect_pre_visit_info(patient_id, ...)`.
3. That tool de-anonymizes the values and writes them into the current encounter's `clinical` block via `db.update_clinical(...)`.
4. The agent thanks the patient and closes the conversation. (If they decline, it ends gracefully.)

---

## Returning Patient Branch

If the patient says they've been here before:

1. The agent asks for their name → `pii.redact()` produces e.g. `TOKEN_PERSON_0`.
2. It calls `get_patient_ehr("TOKEN_PERSON_0")`. The tool resolves the token, looks up the record, and returns the EHR with PII **re-tokenized** so OpenAI still never sees real values.
3. It confirms identity ("I found your record — [age], [sex].") and asks only for the **new complaint** (demographics are already on file).
4. It triages, suggests department/doctor, and calls `open_new_visit(patient_id, complaint, department, doctor)` — appending a second encounter to the same patient document.
5. It then continues to pre-visit intake (PHASE 2) using that `patient_id`.

Note: `patient_id` values are UUIDs, **not PII**, so the agent uses them directly in tool calls.

---

## Summary

| Who sees what | Data |
|---|---|
| OpenAI (LLM) | Only tokens: `TOKEN_PERSON_0`, `TOKEN_PHONE_NUMBER_0` … |
| Your server | Everything — real values live in the entity map (in RAM) |
| `patients.json` | Full real details (de-anonymized before saving) |
| Hospital dashboard | Full real details |
</content>
