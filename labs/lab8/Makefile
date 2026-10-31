PYTHON ?= ../../.local/lab8/venv/bin/python
.PHONY: test up down analytics
up:
	docker compose -f compose.yml up -d --wait
down:
	docker compose -f compose.yml down -v
test:
	PYTHONPATH=. $(PYTHON) -m unittest discover -s tests
analytics:
	$(PYTHON) local_analytics.py ../../.local/lab8/events.jsonl --out ../../docs/lab8-evidence/local-batch
