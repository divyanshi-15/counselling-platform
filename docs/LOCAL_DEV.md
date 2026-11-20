# Local development

## Seeded accounts

**Local development only. Never use these on a public host.** All people are fictional. `make seed` creates them with the default passwords below; on any shared or public deployment, do not seed, or rotate them with `python -m backend.scripts.rotate_seed_passwords`.


| Role | Login | Password | Notes |
|---|---|---|---|
| Admin | admin@example.com | admin123 | verification queue |
| Practice owner | owner@example.com | owner123 | Calm Minds Counselling (published, verified) |
| Practice owner | owner2@example.com | owner123 | Harbour Counselling |
| Practice owner | owner3@example.com | owner123 | Lakeview Wellness Clinic |
| Practice owner | owner4@example.com | owner123 | Greenleaf Counselling Studio (setup in progress, pending invite) |
| Therapist | therapist@example.com | therapist123 | Calm Minds; clients Alpha, Beta |
| Therapist | therapist2@example.com, therapist4@example.com | therapist123 | Calm Minds |
| Therapist | therapist3@example.com, therapist5@example.com, therapist6@example.com | therapist123 | Harbour |
| Therapist | therapist7@example.com to therapist9@example.com | therapist123 | Lakeview |
| Therapist | therapist10@example.com | therapist123 | Lakeview; verification submitted, awaiting admin review |
| Client | client@example.com | client123 | Alpha: PHQ-9/GAD-7 plateau, 1 of 4 exercises done |
| Client | client2@example.com to client12@example.com | client123 | varied cases (client5 has an active journey; client12 has no therapist) |

## Review accounts for a hosted instance

`create_judge_accounts` creates or refreshes one client, one verified therapist with fictional case data, and one practice owner with a draft practice. Passwords come from the environment (12+ characters) and are never stored in the repository:

```
JUDGE_PASSWORD_CLIENT=... JUDGE_PASSWORD_THERAPIST=... JUDGE_PASSWORD_OWNER=... \
  python -m backend.scripts.create_judge_accounts
```

## Useful targets

| Command | Purpose |
|---|---|
| `make kb` | Load knowledge-base entries and embeddings |
| `make calibrate` | Recompute the RAG similarity threshold (rerun after KB edits) |
| `make risk-report` | Print risk-triage hard negatives and any misses from `tests/risk_independent.csv` |
| `make create-admin EMAIL=... PASSWORD=...` | Create an admin account |
