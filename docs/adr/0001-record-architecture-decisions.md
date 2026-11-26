# 0001. Record architecture decisions

Status: accepted

## Context
Saarthi is growing from a hackathon build into a multi-tenant product. Decisions such as the job queue, row-level security and encryption have trade-offs that are lost if they live only in commit messages.

## Decision
Each significant decision gets a short file in `docs/adr/NNNN-title.md` with context, options considered, decision and consequences. ADRs are immutable once accepted; a later ADR supersedes an earlier one rather than editing it. The PR or commit that implements a decision links its ADR.

## Options considered
- Wiki or issue threads: not versioned with the code.
- Only commit messages: hard to find, no alternatives recorded.

## Consequences
A small writing cost per decision, in exchange for reviewers being able to see why, not just what.

## Quality gates introduced alongside
CI (`.github/workflows/ci.yml`) runs ruff, mypy, pytest (Postgres with pgvector), eslint, `tsc` and the frontend build. mypy is gradual: modules listed under `[[tool.mypy.overrides]]` in `pyproject.toml` predate it and are exempt; new modules are checked, and modules are removed from the list as they are cleaned up, never added.
