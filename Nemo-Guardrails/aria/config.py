"""Environment / API-key loading for the ARIA demo.

Loads variables from a local `.env` file (if present) and exposes a small
helper to verify that the required keys are set. Import `load_environment()`
once at the top of the notebook.
"""

import os

from dotenv import load_dotenv


def load_environment(verbose: bool = True) -> dict:
    """Load `.env` and report which API keys are available.

    Returns a dict mapping key name -> bool (present or not).
    """
    load_dotenv()

    keys = ["OPENAI_API_KEY", "NVIDIA_API_KEY"]
    status = {k: bool(os.environ.get(k)) for k in keys}

    if verbose:
        for name, present in status.items():
            mark = "✓" if present else "✗"
            note = "set" if present else "MISSING — add it to your .env file"
            print(f"{mark} {name}: {note}")

    return status


def require_openai() -> None:
    """Validate the OpenAI key by hitting the models endpoint."""
    from openai import OpenAI

    try:
        OpenAI().models.list()
        print("✓ OpenAI API key is valid")
    except Exception as e:  # noqa: BLE001 - surface any auth/network error to the user
        print(f"✗ OpenAI not reachable: {e}")
        print("  Check your OPENAI_API_KEY in .env")
