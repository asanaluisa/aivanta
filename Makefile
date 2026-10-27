.PHONY: up down test test-backend test-frontend seed fixtures

up:            ## build and start the full stack
	docker compose up --build

down:
	docker compose down

seed:          ## reload the synthetic demo data
	docker compose exec backend python -m app.seed --reset

test: test-backend test-frontend

test-backend:
	cd backend && pytest -q

test-frontend:
	cd frontend && npm test

fixtures:      ## regenerate API payload fixtures used by frontend tests
	cd backend && python scripts/export_fixtures.py
