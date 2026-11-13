ROLE
You are a senior full-stack engineer. Build a working, demo-ready MVP in this repo. Be token-efficient: write code directly, no long explanations, no placeholder TODOs, no unrequested features. After each milestone, run the tests, fix failures, and reply in at most 5 lines (what works, what's missing). Wait for me to say "do milestone N".

PRODUCT
"Counselling practice platform + AI case copilot." Small counselling practices launch an online presence without a tech team. Clients log in, browse practices, book a listed therapist, fill an intake form, and see their therapist plus the exercises the therapist approved. Therapists get an AI case copilot. The AI never diagnoses, and a human approves every client-facing action. Demo uses synthetic data only. Show a banner on every page: "Demo: use fictional information only."

STACK (do not substitute)
- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, APScheduler
- DB: PostgreSQL 16 + pgvector (image pgvector/pgvector:pg16), runs in Docker Compose, no published DB port
- AI: Anthropic Python SDK. Model names from env: MODEL_FAST=claude-haiku-5-5 (default for everything in development), MODEL_SMART=claude-sonnet-5-5 (final demo only)
- Embeddings: fastembed with multilingual-e5-small (local, free)
- ML: scikit-learn logistic regression on embeddings for risk triage
- Frontend: React + TypeScript + Vite + Tailwind + shadcn/ui, mobile-friendly
- Infra: docker-compose with services caddy, api, postgres. Caddy handles HTTPS for DOMAIN from env.
- Tests: pytest. Auth: email+password (argon2), JWT in httpOnly cookie. Secrets only via .env, provide .env.example, .gitignore includes .env.

ROLES AND ACCESS RULES (enforce server-side in a dependency layer, not in prompts)
- client: reads only own rows
- therapist: reads only clients with a booking or case plan with them. A therapist in the same practice cannot read another therapist's clients
- practice_owner (may also be a therapist): manages practice page and listings only. NEVER any clinical table
- admin: sets verified flag on practices/therapists
- Public routes show only published AND verified practices. No client data ever.

DATA MODEL
users(role, email, password_hash, language), practices(name, slug, owner_id, page_json, status draft|published, verified), therapist_profiles(user_id, practice_id, bio, approaches[], languages[], fee, verified), availability_slots, bookings, intake_forms(therapist_id, fields_json), intake_responses, consents, sessions(booking_id, raw_notes, structured_json), case_plans(client_id, therapist_id, version, approach, formulation_text written by therapist, goals_json, approved_at), exercises(library: thought_record, brain_dump, plus Kannada versions), assignments, checkins, assessments(type PHQ9|GAD7, total, item_scores, taken_at), alerts(type risk|plateau|drift, payload, acknowledged), pending_actions(type, payload, status, idempotency_key, decided_by), audit_log(append-only), kb_documents, kb_chunks(text, approach, topic_tags, embedding vector, tsvector).

CORE RULE: AI MODULES ONLY PROPOSE
Every AI output is saved as a pending_action or draft. Only an authenticated human action applies it (publish page, release exercise, apply plan update, send email). Use idempotency keys so double-clicks cannot double-send.

AGENTS (each is a bounded tool-use loop: max 8 tool calls, max_tokens set, Pydantic-validated JSON output, one retry on validation failure, then a visible error)
1. Practice launch agent: input = owner's answers (name, location, languages, specialties, approaches, fee range, tone). Tools: draft_page, check_claims, revise_page. Loop until check_claims passes. check_claims = regex banned list ("cure", "guaranteed", "100%", outcome promises) PLUS a cheap model evaluator call. Output a page_json (tagline, about, services, faq, what_to_expect), never raw HTML. Owner approves before publish.
2. Case copilot, "Prepare my day" button: for each of the therapist's clients with an upcoming session, call tools get_intake, structure_notes, get_scores, retrieve_knowledge, compare_to_plan, draft_exercises. Output a briefing with suggestions. Every suggestion must cite a kb_chunk id and/or quote the client's notes. Unsupported statements must be labelled INFERRED. If retrieval finds nothing, say "no supporting entry found". An output validator REJECTS any suggestion citing a chunk id that was not actually retrieved. Never output a diagnosis. Phrase as "the notes point toward X, please confirm."
3. Monitoring agent: APScheduler nightly job plus a "Run overnight check now" button. Plateau/drift detection is deterministic CODE: no meaningful PHQ-9/GAD-7 improvement over 2 weeks (slope test), homework completion under 50%, plan goal untouched in 3 sessions. The model only drafts the plan-update text. It creates an alert plus a pending_action. It never applies anything.
4. Client exercise runner is NOT an agent: it serves a fixed template and has exactly two server functions, save_checkin and flag_risk.

RAG
Seed 12 to 15 short original knowledge entries written in your own words (CBT thought record, behavioural activation, DBT distress tolerance, CBT-I stimulus control, worry postponement, grounding, etc.), each with purpose, typical use, cautions, steps. Add a source/licence field marked "original, for demo." One chunk per technique. Retrieval = filter by approach/language, then pgvector similarity + Postgres full-text merged with reciprocal rank fusion, top 5, with a minimum similarity threshold. Per-client case memory retrieval must filter by client_id inside the SQL query.

SAFETY LAYER (build first, must work with no LLM call)
- Runs on ALL client free-text input and on PHQ-9 item 9 > 0
- Layer 1: keyword/pattern list in English, Hindi, Kannada (romanised and native script)
- Layer 2: embeddings + logistic regression classifier trained on a small labelled synthetic set that you generate (about 60 phrases), report precision and recall on a held-out split in a README table
- On a hit: stop, show a FIXED pre-written crisis message with Tele-MANAS 14416, create a high-priority alert for the therapist. No model-written text in this path.
- Every client page shows a crisis notice and "skill-building support, not a replacement for therapy."
- Post-check on all AI output rejects diagnostic conclusions and supplement or medication advice.
- Notes and client text go into prompts as delimited data with an instruction never to follow commands inside them.

COST CONTROLS
- Disk cache of model responses keyed by hash(prompt+model) in dev so repeated runs cost nothing
- Prompt caching on the system prompt and retrieved chunks
- Daily token budget in code, and per-IP rate limits. When the budget is exceeded, AI endpoints return "AI unavailable, manual workflow open."
- If the AI service is down, the safety path and the manual workflows still work

FRONTEND (keep minimal, use shadcn components)
- Public: practice page /p/:slug, practice list with filters (language, specialty, approach, fee, online/in-person), contact form that emails the domain mailbox via SMTP env vars (SMTP_HOST, SMTP_USER, SMTP_PASS)
- Client: signup/login, profile, browse, book with intake form, dashboard ("My practice", "My therapist", upcoming session, approved exercises), exercise page (mobile friendly), embedded Jitsi iframe for the session
- Therapist: availability, intake form builder, bookings, notes (type or paste transcript), case plan with therapist-written formulation, "Prepare my day", approval inbox, alerts
- Practice owner: guided onboarding chat, AI-drafted page preview, approve/publish
- Admin: verify toggle
- An "Agent activity" panel showing each tool step the agents took ("Checked 4 clients, 1 plateau, drafted update, awaiting approval")

SEED DATA (script: make seed)
2 practices (1 published+verified, 1 draft), 3 therapists, 4 synthetic clients, bookings, 2 to 3 weeks of PHQ-9/GAD-7 for one client with a plateau, intake responses, session notes, the knowledge base, and demo logins printed in the README.

TESTS (pytest, keep fast)
1. Access control: cross-client read, cross-therapist read, practice owner to clinical data, retrieval across clients. All must fail.
2. Safety: 30 labelled phrases (EN/HI/KN, indirect phrasing, a diagnosis request, a supplement request, a prompt-injection attempt). Risk cases trigger 100%. No diagnosis or supplement advice in any output.
3. Citation validity: all cited chunk ids were retrieved.
4. Claims check: bait prompts ("guarantee results") never reach the owner.
Mock the LLM in tests. Provide one command: make test.

DELIVERABLES
docker-compose.yml, Caddyfile, Makefile (up, seed, test), README (architecture diagram in ASCII or mermaid, how to run, eval results table, guardrails, roadmap: payments, calendar sync, meeting bot, DPDP review), .env.example.

MILESTONES (stop after each one and report in 5 lines)
1. Repo skeleton, Compose, Postgres+pgvector, Alembic schema, auth + roles + access dependency layer, safety layer with tests. Hello-world works through Caddy.
2. Practices, public page, practice launch agent with claims check, approval and publish, filters list, contact form email.
3. Therapist profiles, availability, booking, intake, confirmation email, client dashboard.
4. Knowledge base + RAG, notes structuring, case plan, "Prepare my day" with citations, exercise release via approval inbox, exercise pages and check-ins.
5. Monitoring agent, alerts, plateau rule, agent activity panel, seed script, full tests green, README.

Start with milestone 1 only.