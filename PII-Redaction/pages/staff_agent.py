import asyncio
import os
import sys
import uuid

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from agent import build_agent
from pii_handler import PIIHandler
from tools import make_tools

# ---------------------------------------------------------------------------
# Session bootstrap
# ---------------------------------------------------------------------------

def init_session() -> None:
    if "staff_ready" in st.session_state:
        return

    load_dotenv(override=True)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("OPENAI_API_KEY not set. Add it to your .env file.")
        st.stop()

    pii = PIIHandler()
    _patient_tools, staff_tools = make_tools(pii)
    agent = build_agent(api_key, staff_tools, role="staff")

    st.session_state.update(
        staff_ready=True,
        staff_pii=pii,
        staff_agent=agent,
        staff_thread_id=str(uuid.uuid4()),
        # (role, display_text, raw_text)
        staff_messages=[],
    )


# ---------------------------------------------------------------------------
# Core: send one message through the staff agent
# ---------------------------------------------------------------------------

def send_message(raw_text: str) -> tuple[str, str, str]:
    """Return (display_response, raw_llm_response, redacted_input)."""
    pii: PIIHandler = st.session_state.staff_pii
    agent           = st.session_state.staff_agent

    redacted = pii.redact(raw_text)
    config   = {"configurable": {"thread_id": st.session_state.staff_thread_id}}

    max_tool_retries = 2
    result = None
    for attempt in range(max_tool_retries + 1):
        try:
            result = agent.invoke(
                {"messages": [HumanMessage(content=redacted)]},
                config=config,
            )
            break
        except Exception as exc:
            msg = str(exc)
            if "rate_limit_exceeded" in msg or "429" in msg:
                import re as _re
                wait = _re.search(r"try again in ([\d]+m[\d.]+s|[\d.]+s)", msg)
                wait_str = wait.group(1) if wait else "a few minutes"
                friendly = (
                    f"Rate limit reached on the AI model. "
                    f"Please wait **{wait_str}** and try again. "
                    f"(Check your OpenAI plan's rate limits and usage.)"
                )
                return friendly, msg, redacted
            if "tool_use_failed" in msg or "Failed to call a function" in msg:
                if attempt < max_tool_retries:
                    continue
                friendly = (
                    "The AI had trouble processing that request. "
                    "Please try rephrasing, or click **New session** in the sidebar and try again."
                )
                return friendly, msg, redacted
            raise

    content = result["messages"][-1].content
    if isinstance(content, list):
        raw_llm = " ".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    else:
        raw_llm = content

    display_response = pii.deredact(raw_llm)
    return display_response, raw_llm, redacted


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Staff Clinical Agent",
    page_icon="🩺",
    layout="centered",
)

init_session()

st.title("🩺 Staff Clinical Agent")
st.caption(
    "Look up patient EHRs, update clinical data, and generate discharge summaries. "
    "Patient identifiers are anonymised before reaching the AI."
)

# Render conversation history
for role, display_text, raw_text in st.session_state.staff_messages:
    with st.chat_message(role):
        st.markdown(display_text)
        if role == "user":
            # Always visible (not just when redaction changed the text) so
            # staff can verify whether patient identifiers were anonymised.
            with st.expander("🔒 What the LLM sees"):
                st.code(raw_text, language=None)
        elif raw_text != display_text:
            with st.expander("🔍 Raw LLM output"):
                st.code(raw_text, language=None)

# Chat input
user_input = st.chat_input("e.g. Look up John Smith / Add diagnosis: hypertension / Discharge this patient")
if user_input:
    st.session_state.staff_messages.append(("user", user_input, user_input))

    with st.spinner(""):
        display_resp, raw_resp, redacted_input = send_message(user_input)

    st.session_state.staff_messages[-1] = ("user", user_input, redacted_input)
    st.session_state.staff_messages.append(("assistant", display_resp, raw_resp))
    st.rerun()

# Sidebar controls
with st.sidebar:
    st.header("Session")
    if st.button("🔄 New session", use_container_width=True):
        for key in [k for k in st.session_state.keys() if k.startswith("staff_")]:
            del st.session_state[key]
        st.rerun()

    st.divider()
    st.markdown(
        "**Quick commands**\n"
        "- `Look up [patient name]`\n"
        "- `Add diagnosis: [text]`\n"
        "- `Add note: [text]`\n"
        "- `Add allergy: [text]`\n"
        "- `Add medication: [text]`\n"
        "- `Discharge this patient`"
    )
