# Pre-Appointment Briefing Agent

A defended clinical RAG assistant that prepares pre-appointment briefings for
doctors, plus a [Promptfoo](https://promptfoo.dev) red-team harness that attacks it.

**Stack:** LangChain · GPT-4o-mini · FAISS · SQLite · FastAPI

## Layout

```
pre_appointment_agent/       # the application package
├── config.py                # env / model / paths
├── database.py              # schema + seeded mock patients (init_db)
├── tools.py                 # get_patient_data() SQLite tool
├── knowledge_base.py        # 4 FAISS KBs + KB tools
├── agent.py                 # hardened system prompt + build_agent()
├── defenses.py              # guardrail, crescendo, self-reminder, SecureAgentRunner
└── server.py                # FastAPI /generate endpoint
demo.ipynb                   # thin demo: database, run-agent, guardrails
redteam/                     # promptfoo attack configs
├── redteam_standard.yaml    #   built-in plugins/strategies
└── custom/                  #   custom plugin + strategy
    ├── redteam_custom.yaml
    ├── plugins/emotional-patient-record-pretext.yaml
    └── strategies/hospital-emergency-emotional.js
```

## The four defences

1. **Input guardrail** — regex blocklist for jailbreak / off-topic input
2. **Prompt hardening** — security rules baked into the system prompt
3. **Crescendo monitor** — per-thread accumulating score that blocks slow escalation
4. **Self-reminder** — re-anchors the agent's role every 3rd turn

All applied in `SecureAgentRunner.run()`; memory and crescendo state are isolated
per `thread_id` (one patient session each).

## Setup

```bash
uv sync                   # Python deps (the agent + server)
npm install               # promptfoo, the red-team harness (project-local)
cp .env.example .env      # then add your OPENAI_API_KEY
```

## Run

**Demo notebook** (database, agent, guardrails):

```bash
uv run jupyter lab demo.ipynb
```

**Server** (what the red-team configs hit — `POST /generate` on `127.0.0.1:8000`):

```bash
uv run pre-appointment-server
```

## Red-team

With the server running in another terminal:

```bash
npx promptfoo redteam run -c redteam/redteam_standard.yaml
npx promptfoo redteam run -c redteam/custom/redteam_custom.yaml
```

> `promptfoo` is installed **project-local** (a devDependency), so it's not on
> your `PATH` — the `npx` prefix runs the copy in `node_modules/.bin`. Bare
> `promptfoo …` will fail with `command not found`.

### Configure red-teams from the UI

To set up and run a scan from the browser instead of YAML:

```bash
npx promptfoo redteam setup   # opens http://localhost:15500
```

The wizard walks you through picking a target, plugins, and strategies, then
generates and runs the attacks. The server must be running (see above), and the
target should point at `http://127.0.0.1:8000/generate`.

> The UI builds its own config from your selections — it does **not** load
> `redteam_standard.yaml` or the custom plugin/strategy under `redteam/custom/`.
> The custom JS strategy is CLI/YAML-only. Use the UI for exploratory scans; use
> `redteam run -c …` for the committed configs.

## View results (web UI)

`redteam run` already includes the eval step and writes results to a SQLite DB
in `~/.promptfoo/` (not into this project). To browse the latest run in your
browser:

```bash
npx promptfoo redteam report   # red-team vulnerability dashboard
npx promptfoo view             # general eval results explorer
```

Both start a local server (default `http://localhost:15500`) and open it in your
browser. Press `Ctrl+C` in the terminal to stop it.

To save a portable copy into the project instead of the shared DB, add
`--output` to the run:

```bash
npx promptfoo redteam run -c redteam/redteam_standard.yaml --output report.html
```
