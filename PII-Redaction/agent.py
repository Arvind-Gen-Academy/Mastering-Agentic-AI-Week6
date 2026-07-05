import datetime

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from prompt import REGISTRATION_TRIAGE_PROMPT, STAFF_PROMPT


def _build_llm(api_key: str) -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key=api_key,
        temperature=0.3,
    )


def build_agent(api_key: str, tools: list, role: str = "patient"):
    """Build an agent scoped to one portal's tools and system prompt.

    role: "patient" (registration/triage) or "staff" (clinical workflows).
    """
    today = datetime.date.today().isoformat()
    base_prompt = REGISTRATION_TRIAGE_PROMPT if role == "patient" else STAFF_PROMPT
    prompt = base_prompt.replace("{TODAY}", today)
    memory = MemorySaver()
    return create_agent(
        model=_build_llm(api_key),
        tools=tools,
        checkpointer=memory,
        system_prompt=prompt,
    )
