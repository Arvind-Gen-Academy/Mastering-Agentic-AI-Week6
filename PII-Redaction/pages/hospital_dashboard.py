import json
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import load_all_patients

st.set_page_config(
    page_title="Hospital Dashboard",
    page_icon="🏨",
    layout="wide",
)

st.title("🏨 Hospital Dashboard")
st.caption("Live view of all patient records. Real patient details are stored here — PII is only anonymised in transit to the AI.")

# ── Controls ──────────────────────────────────────────────────────────────────

col_refresh, col_filter, col_count, _ = st.columns([1, 2, 2, 3])

with col_refresh:
    if st.button("🔄 Refresh"):
        st.rerun()

STATUS_OPTIONS = ["All", "registered", "scheduled", "admitted", "discharged"]
with col_filter:
    status_filter = st.selectbox("Filter by status", STATUS_OPTIONS, label_visibility="collapsed")

patients = load_all_patients()

# Filter
if status_filter != "All":
    def _has_status(p):
        return any(e.get("status") == status_filter for e in p.get("encounters", []))
    patients = [p for p in patients if _has_status(p)]

with col_count:
    total_encounters = sum(len(p.get("encounters", [])) for p in patients)
    st.metric("Patients", len(patients))

if not patients:
    st.info("No patient records yet. Patients register via the Patient Portal.")
    st.stop()

st.divider()

STATUS_COLORS = {
    "registered": ("#cce5ff", "#004085"),
    "scheduled":  ("#fff3cd", "#856404"),
    "admitted":   ("#d4edda", "#155724"),
    "discharged": ("#f8d7da", "#721c24"),
}


def _status_badge(status: str) -> str:
    bg, fg = STATUS_COLORS.get(status, ("#e2e3e5", "#383d41"))
    return (
        f"<span style='background:{bg};color:{fg};"
        f"padding:2px 10px;border-radius:4px;font-weight:600;font-size:0.85em'>"
        f"{status.upper()}</span>"
    )


# Show newest patients first
for patient in reversed(patients):
    p_info   = patient.get("patient", {})
    p_name   = p_info.get("name", "Unknown")
    p_id     = patient["_id"]
    created  = patient.get("created_at", "")[:19].replace("T", " ")
    encounters = patient.get("encounters", [])
    latest_status = encounters[-1].get("status", "—") if encounters else "—"

    badge = _status_badge(latest_status)
    with st.expander(
        f"**{p_name}** &nbsp;·&nbsp; {created} &nbsp;·&nbsp; {len(encounters)} encounter(s)",
        expanded=False,
    ):
        col_demo, col_enc = st.columns([1, 2])

        with col_demo:
            st.subheader("Demographics")
            st.table({
                "Field": ["Name", "Age", "Sex", "Phone", "Email"],
                "Value": [
                    p_info.get("name",  "—"),
                    p_info.get("age",   "—"),
                    p_info.get("sex",   "—"),
                    p_info.get("phone", "—"),
                    p_info.get("email", "—"),
                ],
            })
            st.markdown(f"**Patient ID:** `{p_id}`")
            st.markdown(f"**Current status:** {badge}", unsafe_allow_html=True)

        with col_enc:
            st.subheader("Encounters")
            if not encounters:
                st.info("No encounters recorded.")
            else:
                for i, enc in enumerate(reversed(encounters), 1):
                    visit   = enc.get("visit", {})
                    clinical = enc.get("clinical", {})
                    enc_status = enc.get("status", "—")
                    enc_badge  = _status_badge(enc_status)

                    adm = (enc.get("admission_date") or "")[:19].replace("T", " ")
                    dis = (enc.get("discharge_date") or "—")

                    with st.container(border=True):
                        st.markdown(
                            f"**Encounter {i}** &nbsp; {enc_badge} &nbsp; "
                            f"`{enc['encounter_id'][:8]}…`",
                            unsafe_allow_html=True,
                        )
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown(f"**Admitted:** {adm}")
                            st.markdown(f"**Discharged:** {dis if dis != '—' else '—'}")
                            st.markdown(f"**Complaint:** {visit.get('complaint', '—')}")
                        with c2:
                            st.markdown(f"**Department:** {visit.get('department', '—')}")
                            st.markdown(f"**Doctor:** {visit.get('doctor', '—')}")

                        # Clinical summary
                        has_clinical = any([
                            clinical.get("diagnoses"),
                            clinical.get("allergies"),
                            clinical.get("current_medications"),
                            clinical.get("notes"),
                            clinical.get("discharge_summary"),
                        ])
                        if has_clinical:
                            with st.expander("Clinical data"):
                                for field in ["diagnoses", "allergies", "current_medications",
                                              "procedures", "notes", "lab_results", "medical_history"]:
                                    val = clinical.get(field)
                                    if val:
                                        st.markdown(f"**{field.replace('_', ' ').title()}:** {val}")
                                if clinical.get("discharge_summary"):
                                    st.markdown("**Discharge Summary:**")
                                    st.text(clinical["discharge_summary"])
                                if clinical.get("followup_instructions"):
                                    st.markdown(f"**Follow-up Instructions:** {clinical['followup_instructions']}")
                                if clinical.get("followup_dates"):
                                    sent = set(clinical.get("followup_sent", []))
                                    dates_display = [
                                        f"{d} ✓" if d in sent else d
                                        for d in clinical["followup_dates"]
                                    ]
                                    st.markdown(f"**Follow-up Dates:** {', '.join(dates_display)}")

        # Raw document toggle
        with st.expander("Raw JSON document"):
            st.code(json.dumps(patient, indent=2), language="json")
