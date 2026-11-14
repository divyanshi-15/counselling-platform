# Frontend spec (compressed)
Stack: /frontend Vite+React+TS+Tailwind+shadcn/ui+react-router. API types via openapi-typescript from FastAPI OpenAPI (`make api-types`). One fetch wrapper, credentials "include". Same-origin: Caddy serves built static + SPA fallback, `handle_path /api/*` proxies to api (prefix stripped). Dev: Vite proxy /api. Docker web build stage so `docker compose up --build` yields the site.
Rules: banner "Demo: use fictional information only." on every page. Mobile-first; client pages OK at 375px. shadcn defaults, one accent colour, no custom design system. Loading/empty/error states everywhere; AI outage -> "AI unavailable, manual workflow open". Never guess routes: read OpenAPI. Missing endpoint -> list it, add smallest one with access tests, say so.
Screens
- Public: practice list + filters (language, specialty, approach, fee, online/in-person); /p/:slug (about, services, FAQ, what to expect, verified therapists, contact form); login/signup; demo-login helper when DEMO_MODE=1.
- Client: dashboard (my practice, my therapist, upcoming session, approved exercises; fixed notice + crisis line on every client page); book flow (therapist, slot, intake form, confirm); exercise page w/ save check-in (crisis response -> show fixed message prominently, nothing else); Join session = Jitsi iframe.
- Therapist: bookings + intake view; add notes; record PHQ-9/GAD-7; case plan editor (therapist-written formulation); "Prepare my day" briefing, every suggestion shows citation + INFERRED badge; approval inbox showing exactly what reaches client; alerts (risk pinned, red); Agent activity panel (agent_runs); "Run overnight check now".
- Owner: onboarding form, "Draft with agent", preview page_json, approve to publish; Agent activity panel.
- Admin: verify toggle list.
Stages: (1) setup+public+auth [DONE]; (2) client; (3) therapist; (4) owner/admin + one Playwright test of demo path with LLM faked server-side by env flag.
