.PHONY: help install test lint format type-check clean build run-gui run-cli demo docker

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	uv sync

test:  ## Run tests
	pytest tests/ -v

test-cov:  ## Run tests with coverage
	pytest tests/ -v --cov=core --cov=parsers --cov=generators --cov-report=term-missing

lint:  ## Lint with ruff
	ruff check .
	ruff format --check .

format:  ## Format code
	ruff check --fix .
	ruff format .

type-check:  ## Run mypy
	mypy --ignore-missing-imports core/ models/ config.py parsers/ generators/ mailer/

clean:  ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache htmlcov .coverage

build:  ## Build package
	uv build

run-gui:  ## Run GUI
	python gui_app.py

run-cli:  ## Run CLI
	python main.py

demo:  ## Run demo
	python main.py demo

docker:  ## Run with Docker
	docker compose up --build

docker-dev:  ## Run tests in Docker
	docker compose --profile dev run --rm app-dev
