"""Central configuration: environment, model, and file paths.

Loading the OPENAI_API_KEY here (once, at import) means every other module can
assume the key is present rather than re-checking it.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root is the parent of this package directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# The SQLite file lives at the project root so the notebook, the server, and
# ad-hoc scripts all resolve to the same database regardless of cwd.
DB_PATH = PROJECT_ROOT / "patients.db"

# Underlying LLM for agent reasoning and response generation.
MODEL_NAME = "gpt-4o-mini"

# Server bind address (kept in sync with the promptfoo `url` config).
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000

load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def require_api_key() -> None:
    """Fail fast with a clear message if the OpenAI key is not configured."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Add it to a .env file at the project root."
        )
