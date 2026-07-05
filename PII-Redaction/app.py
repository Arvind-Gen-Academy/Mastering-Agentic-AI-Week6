import asyncio
import os
import sys
import uuid

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
    if "ready" in st.session_state:
        return

    load_dotenv(override=True)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("OPENAI_API_KEY not set. Add it to your .env file.")
        st.stop()

    pii = PIIHandler()
    patient_tools, _staff_tools = make_tools(pii)
    agent = build_agent(api_key, patient_tools, role="patient")

    st.session_state.update(
        ready=True,
        pii=pii,
        agent=agent,
        thread_id=str(uuid.uuid4()),
        # Each message: (role, display_text, raw_text)
        # user  → display = original input,      raw = redacted (what LLM saw)
        # asst  → display = deredacted response, raw = raw LLM output (with tokens)
        display_messages=[],
        initialized=False,
    )


# ---------------------------------------------------------------------------
# Core: send one message through the agent
# ---------------------------------------------------------------------------

def send_message(raw_text: str) -> tuple[str, str, str]:
    """Return (display_response, raw_llm_response, redacted_input)."""
    pii: PIIHandler  = st.session_state.pii
    agent            = st.session_state.agent

    redacted = pii.redact(raw_text)
    config   = {"configurable": {"thread_id": st.session_state.thread_id}}

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
                    "Please try rephrasing, or click **Start new session** in the sidebar and try again."
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

    # Deredact LLM output before showing to patient
    display_response = pii.deredact(raw_llm)
    return display_response, raw_llm, redacted


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Hospital Patient Portal",
        page_icon="🏥",
        layout="centered",
    )

    init_session()

    st.title("🏥 Patient Registration & Booking")
    st.caption("Your personal information is anonymised before being sent to the AI.")

    # Render conversation history
    for role, display_text, raw_text in st.session_state.display_messages:
        with st.chat_message(role):
            st.markdown(display_text)
            if role == "user":
                # Always visible (not just when redaction changed the text) so
                # the patient can verify whether their input was anonymised.
                with st.expander("🔒 What the LLM sees"):
                    st.code(raw_text, language=None)
            elif raw_text != display_text:
                with st.expander("🔍 Raw LLM output"):
                    st.code(raw_text, language=None)

    # Opening greeting on first load
    if not st.session_state.initialized:
        with st.spinner("Connecting…"):
            display_resp, raw_resp, _ = send_message("Hello, I'd like to register.")
        st.session_state.display_messages.append(("assistant", display_resp, raw_resp))
        st.session_state.initialized = True
        st.rerun()

    # Chat input — always active (multi-phase conversation)
    user_input = st.chat_input("Type your message here…")
    if user_input:
        # Append user message immediately (raw will be backfilled after redaction)
        st.session_state.display_messages.append(("user", user_input, user_input))

        with st.spinner(""):
            display_resp, raw_resp, redacted_input = send_message(user_input)

        # Backfill the redacted version into the user message
        st.session_state.display_messages[-1] = ("user", user_input, redacted_input)
        st.session_state.display_messages.append(("assistant", display_resp, raw_resp))
        st.rerun()

    # Sidebar
    with st.sidebar:
        st.header("Session")
        if st.button("🔄 Start new session", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


if __name__ == "__main__":
    main()
