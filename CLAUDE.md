# Project commands

See `AGENTS.md`, `README.md`, and `docs/ARCHITECTURE.md`.

Local start: `python scripts/dev.py` after installing Python requirements and `npm ci` in `apps/web`.

Checks: `python -m pytest -q`; `python -m ruff check .`; `cd apps/web && npm run build`.

Evaluation: `python -m scripts.evaluate`. Docker stack: `docker compose -f infra/docker/compose.yml up -d --build`.

Keep public claims tied to measured evidence. Hosted deployment, account credentials, and paid infrastructure are separate from the local application.
