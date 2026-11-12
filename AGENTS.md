# Working on DocuLens

- Keep the API, worker, and model version contracts consistent.
- Run `python -m pytest -q`, `python -m ruff check .`, and `npm run build` in `apps/web` for relevant changes.
- Use `python -m scripts.evaluate` after changing feature or duplicate thresholds and report actual results, including regressions.
- Do not label layout clusters as semantic classes or interpret geometric agreement as a calibrated probability.
- Preserve originals, tenant isolation, worker fencing, and immutable sealed upload keys.
- Never commit `.env`, `.data`, customer documents, access tokens, or cloud credentials.
- Keep cloud provisioning explicit; this project defaults to a local demo.
