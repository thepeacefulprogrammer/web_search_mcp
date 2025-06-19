.PHONY: help install install-dev test test-unit test-integration lint format type-check security-check clean run docs build

# Default target
help:
	@echo "Available targets:"
	@echo "  install          - Install production dependencies"
	@echo "  install-dev      - Install development dependencies"
	@echo "  test            - Run all tests"
	@echo "  test-unit       - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-cov        - Run tests with coverage"
	@echo "  lint            - Run linting checks"
	@echo "  format          - Format code with black and isort"
	@echo "  type-check      - Run mypy type checking"
	@echo "  security-check  - Run bandit security checks"
	@echo "  quality-check   - Run all quality checks"
	@echo "  clean           - Clean build artifacts"
	@echo "  run             - Run the MCP server"
	@echo "  build           - Build the package"
	@echo "  setup-hooks     - Install pre-commit hooks"

# Installation
install:
	pip install .

install-dev:
	pip install -e ".[dev]"

# Testing
test:
	pytest

test-unit:
	pytest -m unit

test-integration:
	pytest -m integration

test-cov:
	pytest --cov=src --cov-report=html --cov-report=term-missing

# Code quality
lint:
	flake8 src tests

format:
	black src tests
	isort src tests

type-check:
	mypy src

security-check:
	bandit -r src

quality-check: lint type-check security-check
	@echo "All quality checks passed!"

# Development setup
setup-hooks:
	pre-commit install

# Server operations
run:
	python -m web_search_mcp.server

run-config:
	python -m web_search_mcp.server --config config/config.yaml

# Utility
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

build:
	python -m build

# Documentation (if using sphinx or similar)
docs:
	@echo "Add documentation build commands here"

# Development environment setup
dev-setup: install-dev setup-hooks
	@echo "Development environment setup complete!"
	@echo "Run 'make run' to start the server"

# CI/CD simulation
ci-check: quality-check test-cov
	@echo "CI checks completed successfully!" 