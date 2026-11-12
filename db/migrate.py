"""Versioned initial schema migration; run once before starting hosted services."""

from sqlalchemy import text
from services.api.db import engine, init_db

if __name__ == "__main__":
    init_db()
    with engine.begin() as db:
        db.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)"))
        db.execute(text("INSERT INTO schema_migrations(version) VALUES (1) ON CONFLICT DO NOTHING"))
    print("Schema migration 001 applied (idempotent).")
