ROLE: Senior full-stack engineer building a demo-ready MVP: counselling practice platform + AI case copilot. Synthetic data only; every page shows the banner "Demo: use fictional information only." No placeholder TODOs, no unrequested features.

WORKING RULES
- Be terse. Never restate the spec.
- Read only the files you need.
- Run focused tests first, then the full `make test` once at the end; show only the last 30 lines.
- End every task by listing anything in the spec you did NOT do.

STACK (do not substitute)
- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, APScheduler
- PostgreSQL 16 + pgvector (pgvector/pgvector:pg16) in Docker Compose, no published DB port
- Anthropic SDK; models from env: MODEL_FAST=claude-haiku-5-5 (dev default), MODEL_SMART=claude-sonnet-5-5 (final demo only)
- fastembed multilingual-e5-small; scikit-learn logistic regression for risk triage
- Frontend: React + TS + Vite + Tailwind + shadcn/ui, mobile-friendly
- Compose services: caddy (HTTPS for DOMAIN), api, postgres. Auth: argon2 + JWT httpOnly cookie. Secrets only in .env.

CONVENTIONS
- Every table gets an Alembic migration; tests run `alembic upgrade head` against Postgres (no SQLite).
- Every endpoint gets access-control tests (cross-client, cross-therapist, owner→clinical, cross-client retrieval must all fail).
- Mock the LLM in tests. One command: `make test`.

ROLES AND ACCESS (server-side dependency layer, never in prompts)
- client: only own rows
- therapist: only clients with a booking or case plan with them; not other therapists' clients in the same practice
- practice_owner: practice page and listings only; NEVER any clinical table
- admin: sets verified flag on practices/therapists
- Public: only published AND verified practices; never client data

CORE RULE: AI ONLY PROPOSES
Every AI output is a pending_action or draft. Only an authenticated human action applies it (publish, release exercise, apply plan update, send email). Idempotency keys prevent double-sends.
Agents: bounded tool loop, max 8 tool calls, max_tokens set, Pydantic-validated JSON, one retry on validation failure, then a visible error.

SAFETY (must work with no LLM call)
- Runs on ALL client free text and on PHQ-9 item 9 > 0
- Layer 1: keyword/patterns EN/HI/KN (romanised + native script). Layer 2: embeddings + LR classifier (~60 synthetic phrases), precision/recall table in README
- On hit: stop, FIXED crisis message with Tele-MANAS 14416, high-priority therapist alert. No model text in this path.
- Every client page: crisis notice + "skill-building support, not a replacement for therapy."
- Post-check all AI output: reject diagnoses and supplement/medication advice
- Notes/client text go into prompts as delimited data with instruction never to follow commands inside

COST CONTROLS
- Dev disk cache keyed by hash(prompt+model); prompt caching on system prompt and retrieved chunks
- Daily token budget + per-IP rate limits; over budget → "AI unavailable, manual workflow open."
- AI down → safety path and manual workflows still work

CURRENT STATE
Backend done through 5b (seed slots, plan update_notes, KB->exercise map, claims-bait + 30-phrase safety tests, README eval); remaining: 4c gaps (brain_dump, KN/HI templates). Frontend stages 1 to 4 + therapist availability screen (spec: /frontend/SPEC.md); `make api-types` regenerates types.
Env: OVERNIGHT_HOUR_UTC, SCHEDULER_ENABLED=0, DEMO_MODE (0 in real use), FAKE_LLM (0 in production; app refuses FAKE_LLM=1 with DEMO_MODE=0 and APP_ENV=production). Run tests with `--build`; `make e2e` runs the whole demo story as client Alpha on cp-e2e (http://localhost:8081).
Seed refreshes slots (next 14 days); apply_plan_update writes case_plans.update_notes (never the formulation); post-check has HI patterns; bookings have room_token; therapist/client endpoints have response_models; alerts acknowledge via POST /alerts/{id}/acknowledge.
