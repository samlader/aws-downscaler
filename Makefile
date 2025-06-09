.PHONY: help install test coverage lint clean lint-fix

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

install:
	pip install -r requirements.txt
	pip install -e .

test:
	pytest

coverage:
	pytest --cov=aws_downscaler --cov-report=term-missing --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

lint:
	mypy aws_downscaler tests
	flake8 aws_downscaler tests
	black --check aws_downscaler tests
	isort --check-only aws_downscaler tests

format:
	black aws_downscaler tests
	isort aws_downscaler tests

lint-fix:
	black aws_downscaler tests
	isort aws_downscaler tests

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 
