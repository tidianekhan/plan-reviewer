.PHONY: setup run test

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r backend/requirements.txt
	cd frontend && npm install

run:
	cd frontend && npm run build
	cd backend && ../.venv/bin/uvicorn app.main:app --port 8000

test:
	.venv/bin/pytest backend/tests
