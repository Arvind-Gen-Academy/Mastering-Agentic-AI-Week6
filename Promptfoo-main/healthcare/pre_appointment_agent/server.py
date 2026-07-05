"""FastAPI server exposing the agent for Promptfoo (and manual use).

Keeps the exact contract the red-team configs expect:
    POST /generate  -> {"output": "..."}   (promptfoo reads json.output)

Run standalone with:
    uv run pre-appointment-server
    # or
    python -m pre_appointment_agent.server
"""

from fastapi import FastAPI
from pydantic import BaseModel

from . import build_secure_runner
from .config import SERVER_HOST, SERVER_PORT

app = FastAPI(title="Pre-Appointment Briefing Agent")

# Build the defended agent once at import so every request reuses it (and its
# per-thread memory / crescendo state).
runner = build_secure_runner()


class GenerateRequest(BaseModel):
    prompt: str | None = None
    user_input: str | None = None
    thread_id: str = "promptfoo-session"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate")
def generate(req: GenerateRequest):
    user_input = req.user_input or req.prompt
    if not user_input:
        return {"output": "[BLOCKED] Missing prompt."}
    return {"output": runner.run(user_input, thread_id=req.thread_id)}


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="info")


if __name__ == "__main__":
    main()
