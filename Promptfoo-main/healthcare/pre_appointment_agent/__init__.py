"""Pre-Appointment Briefing Agent — a defended clinical RAG assistant.

Public entrypoints:
    init_db()               — create & seed the SQLite database
    build_secure_runner()   — return a ready-to-use SecureAgentRunner
"""

from .agent import SYSTEM, build_agent
from .config import require_api_key
from .database import init_db
from .defenses import SecureAgentRunner
from .tools import get_patient_data

__all__ = [
    "init_db",
    "build_agent",
    "build_secure_runner",
    "SecureAgentRunner",
    "SYSTEM",
    "get_patient_data",
]


def build_secure_runner(seed: bool = True) -> SecureAgentRunner:
    """One-call setup: verify the API key, (optionally) seed the DB, build the
    agent, and wrap it in the defence layer."""
    require_api_key()
    if seed:
        init_db()
    agent, checkpointer = build_agent()
    return SecureAgentRunner(agent, checkpointer)
