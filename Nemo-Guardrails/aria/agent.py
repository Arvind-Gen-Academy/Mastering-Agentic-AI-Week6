"""The unguarded ARIA agent (baseline).

Wraps OpenAI function calling so the LLM can actually invoke ARIA's tools and
get real data back. This is the *before* picture: no guardrails, so the same
attack suite that the guardrail configs later block runs freely here.
"""

import json

from openai import OpenAI

from aria.prompts import ARIA_SYSTEM_PROMPT
from aria.tools import TOOL_MAP, TOOLS

_MODEL = "gpt-3.5-turbo"


def aria_unguarded(user_message: str, model: str = _MODEL, verbose: bool = True) -> str:
    """Call ARIA with NO guardrails.

    Uses OpenAI function calling: the LLM decides whether to invoke a tool,
    the tool runs against the mock data, and the result is fed back for a final
    natural-language response.
    """
    client = OpenAI()

    messages = [
        {"role": "system", "content": ARIA_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    # Step 1: LLM decides what to do (may call a tool).
    response = client.chat.completions.create(
        model=model,
        temperature=0.3,
        messages=messages,
        tools=TOOLS,
    )
    choice = response.choices[0]

    # Step 2: If no tool call, return the text directly.
    if not choice.message.tool_calls:
        return choice.message.content

    # Step 3: Execute the tool call.
    tc = choice.message.tool_calls[0]
    func_name = tc.function.name
    func_args = json.loads(tc.function.arguments)

    if verbose:
        print(f"  [TOOL CALL] {func_name}({func_args})")

    tool_result = TOOL_MAP[func_name](**func_args)

    # Step 4: Feed the tool result back to the LLM for the final response.
    messages.append(choice.message)
    messages.append({
        "role": "tool",
        "tool_call_id": tc.id,
        "content": tool_result,
    })

    final = client.chat.completions.create(
        model=model,
        temperature=0.3,
        messages=messages,
    )
    return final.choices[0].message.content
