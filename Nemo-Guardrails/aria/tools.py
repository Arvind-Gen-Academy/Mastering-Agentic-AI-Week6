"""ARIA's tools: policy lookup and account query.

Defines the Python implementations, the OpenAI function-calling schema, and a
name→function map used by the unguarded agent.
"""

from aria.knowledge_base import CUSTOMERS, KNOWLEDGE_BASE, TRANSACTIONS


def lookup_policy(topic: str) -> str:
    """Look up a NeoBank policy by topic name."""
    result = KNOWLEDGE_BASE.get(topic.strip().lower())
    if result:
        return result
    return f"No policy found for '{topic}'. Available topics: {', '.join(KNOWLEDGE_BASE.keys())}"


def query_account(user_id: str) -> str:
    """Look up account details and transactions for a user ID."""
    customer = CUSTOMERS.get(user_id.strip())
    if not customer:
        return f"Account not found for user_id: {user_id}"

    lines = [
        f"Account Details for {customer['name']}",
        f"  User ID: {user_id}",
        f"  Tier: {customer['tier']}",
        f"  Balance: ${customer['balance']:,.2f}",
        f"  Status: {customer['status']}",
        f"  Email: {customer['email']}",
        f"  Phone: {customer['phone']}",
        f"  DOB: {customer['dob']}",
        f"  Address: {customer['address']}",
    ]
    if customer["fraud_flags"]:
        lines.append(f"  Fraud Flags: {', '.join(customer['fraud_flags'])}")

    txns = TRANSACTIONS.get(user_id.strip(), [])
    if txns:
        lines.append("\nRecent Transactions:")
        for t in txns:
            recipient = t.get("recipient", "")
            detail = f" → {recipient}" if recipient else ""
            lines.append(
                f"  [{t['date']}] {t['type']} | ${t['amount']:,.2f} | "
                f"{t['description']}{detail} | {t['status']}"
            )

    return "\n".join(lines)


# ── OpenAI function-calling schema ──
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_policy",
            "description": "Look up a specific NeoBank policy by topic name. "
                           "Topics: transfer_limits, dispute_process, card_management, "
                           "fraud_detection, account_verification, internal_reference_only.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "The policy topic to look up"}
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_account",
            "description": "Retrieve account details and transactions for a user ID. "
                           "Example: USR-0042",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "The customer's user ID"}
                },
                "required": ["user_id"],
            },
        },
    },
]

# ── Dispatch map: tool name → callable ──
TOOL_MAP = {
    "lookup_policy": lookup_policy,
    "query_account": query_account,
}
