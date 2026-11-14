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
Done: 1, 2/2b, 2c, 3, 4a (kb/ 12 entries, `make kb`, hybrid RRF retrieval, citation validator, per-client case memory), 4b (sessions, case_plans, assessments, alerts, copilot_briefings; copilot agent; therapist inbox/alerts/agent-runs). 83 tests passing.
Embedding model is baked into the image at /opt/fastembed; tests use FakeEmbedder. Run tests with `--build` (image installs backend non-editable).
Remaining:
- 4c Exercises (thought_record, brain_dump + Kannada), release via approval inbox, exercise runner (fixed template; only save_checkin and flag_risk), check-ins, client-side risk flow.
- Frontend demo path: public list/page, client dashboard + exercise page + Jitsi iframe, therapist notes/case plan/Prepare my day/approval inbox/alerts, owner onboarding chat + preview/publish, admin verify toggle, Agent activity panel.
- 5 Monitoring: APScheduler nightly + "Run overnight check now"; deterministic plateau/drift (PHQ-9/GAD-7 slope over 2 weeks, homework <50%, goal untouched 3 sessions); model only drafts plan-update text → alert + pending_action. Seed (2 practices, 3 therapists, 4 clients, plateau scores, notes, KB, demo logins), safety tests (30 phrases), claims bait; README (diagram, run, eval table incl. KB threshold calibration, guardrails, roadmap: payments, calendar sync, meeting bot, DPDP review).
