# Atalhos de desenvolvimento do Feynman's Legacy.
PYTHON ?= python

.PHONY: help setup api-dev api-test api-lint api-format lint test

help:
	@echo "Alvos disponíveis:"
	@echo "  setup       Instala dependências e o pacote em modo editável."
	@echo "  api-dev     Sobe a API com recarga automática em http://127.0.0.1:8000."
	@echo "  api-test    Executa a suíte de testes da API."
	@echo "  api-lint    Executa Ruff e mypy."
	@echo "  api-format  Formata app/ e tests/ com Ruff."

setup:
	$(PYTHON) -m pip install -r requirements.txt -r requirements-dev.txt
	$(PYTHON) -m pip install -e .

api-dev:
	$(PYTHON) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

api-test:
	$(PYTHON) -m pytest tests -q

api-lint:
	$(PYTHON) -m ruff check app tests
	$(PYTHON) -m mypy

api-format:
	$(PYTHON) -m ruff format app tests

lint: api-lint

test: api-test
