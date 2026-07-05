"""Four FAISS knowledge bases of static clinical reference content, wrapped as
tools the agent can consult.

Building the KBs requires OpenAI embeddings (and thus the API key), so it is
done lazily via `build_kb_tools()` rather than at import time.
"""

from langchain_community.vectorstores import FAISS
from langchain_core.tools import Tool
from langchain_openai import OpenAIEmbeddings

# ── KB 1: Vitals thresholds ──────────────────────────
VITALS_DOCS = [
    "Normal blood pressure: systolic 90-120, diastolic 60-80. Borderline: systolic 121-139, diastolic 81-89. High (hypertension): systolic 140+, diastolic 90+.",
    "Normal fasting blood sugar: 70-99 mg/dL. Prediabetes: 100-125 mg/dL. Diabetes: 126 mg/dL and above.",
    "Normal resting heart rate: 60-100 bpm. Below 60 may indicate bradycardia. Above 100 may indicate tachycardia.",
    "For patients over 60, systolic BP up to 130 is acceptable. Blood sugar targets may be relaxed to under 180 mg/dL post-meal.",
    "A rising trend in BP or blood sugar across two consecutive visits is a clinical flag even if individual readings are borderline.",
]

# ── KB 2: Chronic disease guidelines ────────────────
CHRONIC_DOCS = [
    "Type 2 Diabetes management: monitor HbA1c every 3 months, fasting blood sugar at each visit, check for neuropathy and retinopathy annually.",
    "Hypertension management: check BP at every visit, review sodium intake and stress levels, ensure medication compliance, monitor kidney function annually.",
    "For patients with both diabetes and hypertension, target BP below 130/80 and HbA1c below 7%. Combined risk of cardiovascular events is significantly elevated.",
    "Worsening diabetes signs: rising fasting glucose, increased thirst, fatigue, blurred vision, slow wound healing.",
    "Worsening hypertension signs: persistent headaches, dizziness, shortness of breath, chest tightness. Immediate referral if BP exceeds 180/120.",
]

# ── KB 3: Medication guidelines ─────────────────────
MEDICATION_DOCS = [
    "Metformin long-term use: monitor kidney function (eGFR) annually. Risk of lactic acidosis if eGFR drops below 30. Check B12 levels after 3+ years of use.",
    "Amlodipine long-term use: monitor for peripheral oedema and gingival hyperplasia. Avoid in patients with severe aortic stenosis.",
    "Aspirin long-term use: increased risk of GI bleeding. Consider proton pump inhibitor co-prescription for patients over 60 on long-term aspirin.",
    "Patients on 3 or more medications: review for drug-drug interactions at each visit. Polypharmacy increases risk of adverse events in patients over 50.",
    "Red flag: if a patient has been on the same dose for over 6 months without review, reassess whether the dose is still appropriate given current vitals.",
]

# ── KB 4: Allergy interaction guidelines ────────────
ALLERGY_DOCS = [
    "Penicillin allergy: avoid all penicillin-class antibiotics. Cross-reactivity with cephalosporins is possible in 1-10% of cases. Use macrolides or clindamycin as alternatives.",
    "NSAIDs allergy: avoid aspirin, ibuprofen, naproxen. Paracetamol is generally safe. Check current medication list for any NSAID overlap.",
    "Sulfa allergy: avoid sulfonamide antibiotics and some diuretics like furosemide. Cross-reactivity with thiazide diuretics is debated.",
    "If a patient has a known drug allergy and is currently prescribed a medication from the same class, flag immediately for physician review.",
    "Latex allergy: relevant for surgical and procedural contexts. Ensure latex-free gloves and equipment are used.",
]

_KB_SPECS = [
    (
        "check_vitals_kb",
        "Use this to analyse vital sign trends. Input a query about BP, blood sugar, or heart rate readings. "
        "Returns clinical thresholds and what counts as normal, borderline, or critical by age and sex.",
        VITALS_DOCS,
    ),
    (
        "check_chronic_disease_kb",
        "Use this when the patient has a diagnosed chronic condition such as diabetes or hypertension. "
        "Input the condition name. Returns management guidelines, what to monitor, and signs of worsening.",
        CHRONIC_DOCS,
    ),
    (
        "check_medication_kb",
        "Use this when the patient is on 3 or more medications or has been on a medication for over 6 months. "
        "Input the drug name or concern. Returns long-term use warnings and dosage red flags.",
        MEDICATION_DOCS,
    ),
    (
        "check_allergy_interaction_kb",
        "Use this when the patient has known allergies and is also on medications. Input the allergen name. "
        "Returns known allergen-drug interaction pairs and flags any conflicts with current medications.",
        ALLERGY_DOCS,
    ),
]


def _make_kb_tool(name: str, description: str, kb: FAISS) -> Tool:
    def query_kb(query: str) -> str:
        docs = kb.similarity_search(query, k=2)
        return "\n".join(d.page_content for d in docs)

    return Tool(name=name, func=query_kb, description=description)


def build_kb_tools() -> list[Tool]:
    """Embed each KB with OpenAI embeddings and return the 4 KB tools."""
    embeddings = OpenAIEmbeddings()
    return [
        _make_kb_tool(name, description, FAISS.from_texts(docs, embeddings))
        for name, description, docs in _KB_SPECS
    ]
