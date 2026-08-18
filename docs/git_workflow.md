# Git Workflow — Automated Literature Review

## Branch Strategy

```
main
  │   Production-ready, stable code only.
  │   Direct commits are not permitted.
  │
  └── dev
       │   Integration branch. All feature branches merge here first.
       │   Merges into main after a sprint review.
       │
       ├── feature/data
       │       PDF ingestion, corpus management, data pipeline.
       │
       ├── feature/agents
       │       LangGraph orchestration, specialized AI agents,
       │       summarization, gap identification, citation verification.
       │
       └── feature/backend
               FastAPI routes, database schema, config, API models.
```

## Rules

| Rule | Detail |
|------|--------|
| Never commit directly to `main` | Use pull requests only |
| Never commit directly to `dev` | Merge from feature branches |
| Branch naming | `feature/<area>`, `fix/<description>`, `chore/<description>` |
| Commit style | Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `chore:` |
| PR requirement | At least one reviewer approval before merging to `dev` |
| PR requirement | CI tests must pass before merging to `main` |

## Daily Developer Workflow

```bash
# 1. Start new work — always branch from dev
git checkout dev
git pull origin dev
git checkout -b feature/your-feature-name

# 2. Work, commit incrementally
git add <specific files>
git commit -m "feat: add database health check endpoint"

# 3. Push and open a pull request targeting dev
git push -u origin feature/your-feature-name
# Open PR: feature/your-feature-name → dev

# 4. After approval and merge, clean up
git checkout dev
git pull origin dev
git branch -d feature/your-feature-name
```

## Commit Message Format

```
<type>(<scope>): <short summary>

Types: feat | fix | docs | test | chore | refactor | style
Scope: backend | frontend | db | agents | ingestion | scripts | docs

Examples:
  feat(backend): add /health/db endpoint
  fix(db): handle missing DATABASE_URL gracefully
  docs(readme): add frontend setup instructions
  test(backend): add integration test for health endpoint
  chore(deps): pin psycopg2-binary to 2.9.9
```

## Phase → Branch Mapping

| Phase | Primary Branch |
|-------|---------------|
| Phase 0 — Foundation | `dev` |
| Phase 1 — PDF Ingestion | `feature/data` |
| Phase 2 — Agents | `feature/agents` |
| Phase 3 — Backend API | `feature/backend` |
| Phase 4 — Frontend | `feature/backend` or dedicated `feature/frontend` |
