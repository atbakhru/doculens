.PHONY: setup dev test evaluate fixtures compose down migrate-up
setup:
	python -m pip install -r requirements.txt
	cd apps/web && npm ci
dev:
	python scripts/dev.py
test:
	python -m pytest -q
	python -m ruff check .
	cd apps/web && npm run build
evaluate:
	python -m scripts.evaluate
fixtures:
	python -m scripts.fixtures
compose:
	docker compose -f infra/docker/compose.yml up --build -d
down:
	docker compose -f infra/docker/compose.yml down
migrate-up:
	python -m db.migrate
