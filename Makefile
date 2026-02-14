.PHONY: lint format install-dev

install-dev:
	pip install ruff

lint:
	ruff check backend

format:
	ruff format backend

format-check:
	ruff format --check backend
