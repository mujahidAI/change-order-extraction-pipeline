ifeq ($(OS),Windows_NT)
    BIN := .venv/Scripts
    PYTHON ?= python
else
    BIN := .venv/bin
    PYTHON ?= python3
endif

.PHONY: setup test eval eval-cached api clean

setup:  ## create .venv, install packages, create .env
	$(PYTHON) -m venv .venv
	$(BIN)/python -m pip install -r requirements.txt
	$(BIN)/python -c "import os, shutil; os.path.exists('.env') or shutil.copy('.env.example', '.env')"

test:  ## offline tests (LLM is mocked)
	$(BIN)/python -m pytest -q

eval:  ## full evaluation (calls the LLM)
	$(BIN)/python eval.py

eval-cached:  ## re-score saved outputs, no LLM calls
	$(BIN)/python eval.py --cached

api:  ## run the API at http://localhost:8000/docs
	$(BIN)/uvicorn co_extract.api:app

clean:
	$(BIN)/python -c "import shutil; [shutil.rmtree(p, True) for p in ('.venv', '.pytest_cache', 'src/co_extract.egg-info')]"
