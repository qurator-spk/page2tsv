deps:
	pip install -r requirements.txt

deps-test:
	pip install -r requirements-test.txt

test:
	pytest tests

install:
	pip install .

install-dev:
	pip install -e .

.PHONY: test

