# Deploying to Vercel

The deployed application is the same one that runs locally: the Claude Design
frontend, the FastAPI adapter in `api/`, and the Python shopping-agent engine.
Nothing about agent behavior, prompts, presentation, or the Demo/Live modes
changes when it is deployed.

## Architecture

Vercel's FastAPI framework preset runs the whole application as a **single
Vercel Function** on Fluid compute. There is no separate frontend build and no
second service, so the frontend and the API stay same-origin and no CORS layer
is needed.

```
https://<deployment>/                 -> redirect to the shopping agent
https://<deployment>/app/...          -> frontend/ (static: HTML, JS, product images)
https://<deployment>/api/...          -> the FastAPI app -> engine
```

`api/server.py` mounts `frontend/` at `/app` and redirects `/` to the app, which
is why the deployment root opens directly into Rufus.

## Configuration

Four files, all deployment-only:

| File | Why |
| --- | --- |
| `pyproject.toml` | `[tool.vercel] entrypoint = "api.server:app"`. Without it the preset scans root modules (`app.py`, `streamlit_app.py`) for a top-level `app` and would not find the API. |
| `vercel.json` | `maxDuration` for the function, and `includeFiles` for `prompts/**`. |
| `.vercelignore` | Keeps evals, artifacts, tests, docs and the legacy surfaces out of the bundle (~32 MB → ~2 MB). |
| `requirements.txt` | Runtime dependencies only. |

Dependencies are split so the deployed bundle carries only what the Live agent
runs:

- `requirements.txt` — `openai`, `python-dotenv`, `fastapi`, `uvicorn`
- `requirements-dev.txt` — the above plus `streamlit`, needed for the legacy
  debug surface and for `tests/test_streamlit_app.py`

**Contributors should install `requirements-dev.txt`**, or `tests/test_streamlit_app.py`
will fail to import.

## Environment variables

Set in **Project → Settings → Environment Variables**:

| Variable | Required | Environments |
| --- | --- | --- |
| `OPENAI_API_KEY` | **Yes**, for Live mode | Production, and Preview if you want Live there |
| `LIVE_DEBUG` | No | Set to `1` only in Preview/Development for a small per-turn diagnostic field |

Nothing else is required. `OPENAI_API_KEY` is read server-side only
(`engine/preference_extraction.py`, `engine/conversational_response.py`,
`engine/shopping_selection.py`) and is never sent to the browser.

Without the key the API returns the engine's own "unable to start a new shopping
conversation" copy with `error: "model_unavailable"`. Demo mode still works —
it is entirely client-side and needs no key or backend.

## Local development

Unchanged:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m uvicorn api.server:app --reload --port 8000
open http://localhost:8000/
```

Vercel's local emulator also works, and is worth using once to check the routing
and function config before deploying (requires Vercel CLI ≥ 48.1.8):

```bash
npx vercel@latest dev
```

## Deploying

```bash
npx vercel@latest login      # once, interactive
npx vercel@latest link       # once, links this directory to a project
npx vercel@latest            # Preview deployment
```

Verify the Preview URL, then promote:

```bash
npx vercel@latest --prod
```

## Sessions are in memory

`api/sessions.py` keeps each conversation in the function's process memory.
There is no database and no durable profile, by design.

On Fluid compute a warm instance is reused, so a conversation usually stays on
the same process and multi-turn behavior works. It is **not guaranteed**:
instances scale down when idle and are archived after inactivity, so a session
can disappear between turns.

That failure is handled rather than fatal. The API returns `404` for an unknown
session and the frontend creates a new one and retries the turn once, so the UI
never breaks. The shopper silently loses prior context — a follow-up like
"compare the first two" after a lost session has nothing to resolve against, and
the agent asks for clarification instead. Acceptable for a portfolio demo;
a shared session store would be the fix if that changes.

## Streaming

Live turns use SSE (`POST /api/session/{id}/turn/stream`) so validated cards can
render before the prose is written.

Streaming has been enabled by default on Vercel's Python runtime since January
2025, and `text/event-stream` is not in the CDN's compression allowlist, so the
stream is not gzip-buffered. Locally the first event arrives ~8 s before the
last on a recommendation turn, and the same behavior is expected deployed —
**verify it on a Preview deployment rather than assuming it.**

Two caveats worth knowing:

- Streamed time counts against `maxDuration`. Observed turns run 8–12.5 s
  against a 300 s limit, so there is a wide margin.
- Vercel keeps HTTP/2 connections alive with `PING` frames, but HTTP/1.1 clients
  or intermediaries may drop an idle connection. This stream can be idle for
  several seconds before its first event and sends no heartbeat. If a deployed
  turn ever hangs mid-stream, that is the first thing to check; the fix is a
  periodic SSE comment frame while the turn is running.

If the stream fails before anything has rendered, the frontend falls back to the
buffered `POST /api/session/{id}/turn` endpoint, which runs the identical engine
path.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `500` on every API call | Entrypoint not resolved — confirm `pyproject.toml` is deployed and `[tool.vercel] entrypoint` is present |
| `FileNotFoundError: Prompt file not found` | `prompts/` missing from the bundle — check `includeFiles` in `vercel.json` |
| Live says the conversation is unavailable | `OPENAI_API_KEY` is not set for that environment |
| Frontend loads but images 404 | `frontend/` was excluded from the bundle; it must not be in `.vercelignore` |
| Every turn starts a fresh conversation | Sessions are being lost between invocations — expected under scale-down; see above |
| `504 FUNCTION_INVOCATION_TIMEOUT` | Turn exceeded `maxDuration`; raise it in `vercel.json` |
