.PHONY: dev-backend dev-frontend test install-backend install-frontend

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && uv run pytest -v

install-backend:
	cd backend && uv pip install -r requirements.txt

install-frontend:
	cd frontend && npm install

install: install-backend install-frontend
