"""ARIA — a vulnerable banking agent, hardened with NeMo Guardrails.

Convenience re-exports so the notebook can do e.g.:

    from aria import ARIA_INSTRUCTIONS, create_config, test_rail, ATTACK_SUITE
"""

from aria.agent import aria_unguarded
from aria.attacks import (
    ATTACK_SUITE,
    content_safety_attacks,
    general_attacks,
    pii_attacks,
    pii_mask_tests,
)
from aria.config import load_environment, require_openai
from aria.guardrails import BLOCKED_PHRASES, create_config, is_blocked, test_rail
from aria.prompts import ARIA_INSTRUCTIONS, ARIA_SYSTEM_PROMPT
from aria.tools import TOOL_MAP, TOOLS, lookup_policy, query_account

__all__ = [
    "aria_unguarded",
    "ATTACK_SUITE",
    "general_attacks",
    "content_safety_attacks",
    "pii_attacks",
    "pii_mask_tests",
    "load_environment",
    "require_openai",
    "create_config",
    "test_rail",
    "is_blocked",
    "BLOCKED_PHRASES",
    "ARIA_INSTRUCTIONS",
    "ARIA_SYSTEM_PROMPT",
    "TOOLS",
    "TOOL_MAP",
    "lookup_policy",
    "query_account",
]
