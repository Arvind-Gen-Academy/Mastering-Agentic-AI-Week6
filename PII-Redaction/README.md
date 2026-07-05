# Hospital Patient Intake & Clinical Agent

A conversational hospital system built with LangChain/LangGraph, OpenAI (GPT-4o mini), and Microsoft Presidio. Patients register and triage through a chat interface; hospital staff manage clinical records through a second agent; and everything is viewable on a live dashboard. **Real patient data never leaves your machine** — PII is anonymised locally before any text reaches the cloud LLM.

---

## What it does

Two AI agents share one PII-safe backend:

**Patient portal** (`app.py`) — a receptionist agent that:
- Greets the patient and detects whether they are **new or returning**.
- For new patients, collects eight fields one at a time: name, age, sex, phone, email, complaint, department, doctor.
- **Triages** the complaint — flags high-urgency symptoms (chest pain, stroke, etc.) and suggests the right department/doctor from a fixed list.
- Registers the patient, then optionally records **pre-visit info** (allergies, medications, history).
- For returning patients, looks up their record and opens a **new visit** without re-asking demographics.

**Staff clinical agent** (`pages/staff_agent.py`) — a clinical assistant that lets staff:
- Look up a patient's full **EHR** (encounters + clinical data).
- Add clinical updates (diagnoses, medications, allergies, notes, lab results).
- Write and file a **discharge summary** with follow-up dates.
- Compose and "send" personalised **follow-up messages**.

**Hospital dashboard** (`pages/hospital_dashboard.py`) — a read-only view of every patient, their encounters, and clinical data, with status filtering.

---

## How PII redaction works

All PII processing happens locally — the cloud LLM never receives real patient data.

```
Patient types:    "My name is John Smith, I have chest pain"
                            ↓
Presidio (local): "My name is TOKEN_PERSON_0, I have chest pain"
                            ↓
OpenAI API sees:  TOKEN_PERSON_0, chest pain          ← no real PII
                            ↓
Tool call:        register_patient(name="TOKEN_PERSON_0", ...)
                            ↓
Tool runs locally: pii.deredact(TOKEN_PERSON_0) → "John Smith"
                            ↓
DB stores:        { name: "John Smith", ... }         ← real value, on your machine
```

`PIIHandler` builds a **session-scoped entity map** (`TOKEN_PERSON_0` → `"John Smith"`) that lives only in memory and is never transmitted anywhere. Tokens are stable within a session — the same value always maps to the same token. When the agent returns text or calls a tool, `deredact()` resolves tokens back to real values entirely on your machine, and the reply shown to the patient is de-anonymised locally too.

Presidio detects the usual entities (PERSON, PHONE_NUMBER, EMAIL_ADDRESS, etc.) plus custom recognizers added in `pii_handler.py` for **age**, **sex**, bare **name** replies, and **Indian mobile numbers** — cases the stock statistical model misses in short chat turns.

---

## Architecture

```
  LOCAL — real PII never leaves this box                              CLOUD
 ┌───────────────────────────────────────────────────────────┐
 │                                                             │
 │  ┌─────────────────────┐      ┌─────────────────────┐      │
 │  │  Patient Portal      │      │  Staff Clinical Agent│      │
 │  │  app.py (Streamlit)  │      │  pages/staff_agent.py│      │
 │  └──────────┬──────────┘      └──────────┬──────────┘      │
 │             │  raw user text             │  raw staff text  │
 │             └─────────────┬──────────────┘                  │
 │                           ▼                                 │
 │  ┌──────────────────────────────────────────────────────┐ │
 │  │  PIIHandler · pii_handler.py   (Microsoft Presidio)    │ │
 │  │    redact():  "John Smith"  ──►  "TOKEN_PERSON_0"      │ │
 │  │    entity map (RAM):  TOKEN_PERSON_0 → "John Smith"    │ │
 │  └───────────────────────┬──────────────────────────────┘ │
 │                          │  tokens only                    │
 │                          ▼                                 │      ┌──────────────┐
 │  ┌──────────────────────────────────────────┐  tokens only│      │  OpenAI      │
 │  │  Agent · agent.py                          │────────────┼─────►│  GPT-4o mini │
 │  │    LangChain create_agent (ReAct loop)     │◄───────────┼──────│              │
 │  │    role prompt (prompt.py) + MemorySaver   │  tool calls │      └──────────────┘
 │  └───────────────────────┬──────────────────┘   (tokens)  │
 │                          │  tool call carrying tokens      │
 │                          ▼                                 │
 │  ┌──────────────────────────────────────────────────────┐ │
 │  │  Tools · tools.py                                      │ │
 │  │    deredact() resolves tokens → real values HERE       │ │
 │  │    patient: register_patient · open_new_visit ·        │ │
 │  │             collect_pre_visit_info · get_patient_ehr   │ │
 │  │    staff:   get_patient_ehr · update_encounter_clinical│ │
 │  │             · close_encounter_discharge · send_followup│ │
 │  └───────────────────────┬──────────────────────────────┘ │
 │                          │  real values                    │
 │                          ▼                                 │
 │  ┌──────────────────────────────────────────────────────┐ │
 │  │  db.py  ──►  patients.json                             │ │
 │  │    EHR: patients + encounters + clinical data          │ │
 │  └───────────────────────┬──────────────────────────────┘ │
 │                          │  read                           │
 │                          ▼                                 │
 │  ┌──────────────────────────────────────────────────────┐ │
 │  │  Hospital Dashboard · pages/hospital_dashboard.py      │ │
 │  └──────────────────────────────────────────────────────┘ │
 │                                                             │
 └───────────────────────────────────────────────────────────┘
   Only anonymised tokens cross into the cloud. Tokens are resolved to
   real values inside the box and are never sent to OpenAI.
```

Both portals construct their own `PIIHandler` and an agent via `build_agent(...)`, differing only in the tool set and system prompt (`role="patient"` vs `role="staff"`). Splitting tools per portal keeps each agent's tool surface small, which reduces malformed tool calls from the model.

---

## How the agents work

Each agent is a LangChain **`create_agent`** ReAct loop backed by OpenAI's GPT-4o mini (`temperature=0.3`), with a `MemorySaver` checkpointer keyed by a per-session `thread_id`. Departments and doctors are embedded in the system prompt, so the model can triage and suggest options with no tool call — tools are reserved for actions that touch the database.

**Patient agent tools**

| Tool | When called |
|---|---|
| `register_patient(name, age, sex, phone, email, complaint, department, doctor)` | All eight fields confirmed for a **new** patient |
| `open_new_visit(patient_id, complaint, department, doctor)` | A **returning** patient starts a new visit |
| `collect_pre_visit_info(patient_id, allergies, current_medications, medical_history)` | Post-registration pre-visit intake |
| `get_patient_ehr(name_token_or_id)` | Looking up a returning patient's record |

**Staff agent tools**

| Tool | When called |
|---|---|
| `get_patient_ehr(name_token_or_id)` | Retrieve a patient's full EHR (PII re-tokenised in the response) |
| `update_encounter_clinical(patient_id, field, value)` | Add a diagnosis, medication, note, lab result, etc. |
| `close_encounter_discharge(patient_id, discharge_summary, followup_instructions, followup_dates)` | Discharge and file the summary |
| `send_patient_followup(patient_token_or_id, message)` | Send a personalised follow-up message |

Tokens are resolved to real values *inside* the tools, so the model orchestrates the whole workflow having only ever seen `TOKEN_*` placeholders.

---

## Project structure

```
app.py                        Patient portal chat UI (Streamlit)
pages/
  staff_agent.py              Staff clinical agent chat UI
  hospital_dashboard.py       Read-only dashboard over patients.json
agent.py                      build_agent() — create_agent + role-based prompt
prompt.py                     System prompts (patient triage + staff clinical)
tools.py                      Patient & staff tool sets, departments, triage rules
pii_handler.py                Presidio redact/deredact + entity map + recognizers
db.py                         patients.json read/write (EHR: patients + encounters)
patients.json                 Patient/EHR records (created on first registration)
pii_demo.ipynb                Interactive Presidio concepts walkthrough
architecture.jpg              Architecture diagram (image)
pyproject.toml / uv.lock      Dependencies (managed by uv)
.env                          OPENAI_API_KEY
```

---

## Setup

**1. Install dependencies** (with [uv](https://docs.astral.sh/uv/))
```bash
uv sync
```
The spaCy model (`en_core_web_lg`) that Presidio relies on is pinned as a project dependency, so `uv sync` installs it automatically — no separate download step.

**2. Add your API key**
```
# .env
OPENAI_API_KEY=sk-...   # from platform.openai.com
```

**3. Run**
```bash
uv run streamlit run app.py
```

Three pages appear in the Streamlit sidebar:
- **Patient Registration** — the intake / triage chatbot (`app.py`)
- **Staff Clinical Agent** — EHR lookup, clinical updates, discharge (`pages/staff_agent.py`)
- **Hospital Dashboard** — the read-only patient/EHR view (`pages/hospital_dashboard.py`)

Every chat turn shows a **🔒 What the LLM sees** expander so you can verify that PII was anonymised before it left your machine.

---

## Technology

| Component | Library |
|---|---|
| Agent framework | LangChain / LangGraph (`create_agent`) |
| LLM | OpenAI — GPT-4o mini (`langchain-openai`) |
| PII anonymisation | Microsoft Presidio (`presidio-analyzer`, `presidio-anonymizer`) |
| NLP model (Presidio) | spaCy `en_core_web_lg` |
| UI | Streamlit |
| Store | Local JSON file (`patients.json`) |
</content>
</invoke>
