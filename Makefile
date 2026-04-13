SKILL_DIR := plugins/dismech/skills/dismech
DISORDERS_DIR ?= /Users/gullyburns/Documents/GitHub/dismech/kb/disorders
PORT ?= 7777

.PHONY: init ingest serve demo stats

init:
	uv run --project $(SKILL_DIR) --python 3.12 python $(SKILL_DIR)/alhazen_core.py init

ingest:
	uv run --project $(SKILL_DIR) --python 3.12 python $(SKILL_DIR)/dismech.py ingest --source $(DISORDERS_DIR)

serve:
	uv run --project $(SKILL_DIR) --python 3.12 python $(SKILL_DIR)/dismech.py serve --port $(PORT)

stats:
	uv run --project $(SKILL_DIR) --python 3.12 python $(SKILL_DIR)/dismech.py stats

demo: init ingest stats
	@echo "DisMech demo ready. Run 'make serve' to start the dashboard."
