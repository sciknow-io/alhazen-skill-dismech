# DisMech Benchmark Makefile
# RAG vs. Structured Knowledge — Q1–Q13
#
# Prerequisites:
#   - TypeDB running at localhost:1729 with 'dismech' database populated
#   - Qdrant running at localhost:6333
#   - VOYAGE_API_KEY set (for RAG embedding)
#   - ANTHROPIC_API_KEY set (for RAG answer generation)
#   - DISMECH_DISORDERS_DIR set to path of dismech/kb/disorders/
#   - uv installed (python package manager)
#
# Quick start:
#   export DISMECH_DISORDERS_DIR=/path/to/dismech/kb/disorders
#   make all          # run everything end to end
#   make all-new      # run only Q11–Q13 (enriched tiers)

PYTHON      := uv run --python 3.12 python
SCRIPTS     := scripts
RESULTS     := results
CORPUS      := corpus
DISORDERS   ?= $(DISMECH_DISORDERS_DIR)
TYPEDB_DB   := dismech

.PHONY: all all-new ground-truth corpus-extract corpus-build \
        run-structured run-rag score report clean-new help

# ---------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------

all: ground-truth corpus-extract corpus-build run-structured run-rag score report
	@echo "[done] Full benchmark complete — see $(RESULTS)/scores.json"

all-new: corpus-extract corpus-build \
         $(RESULTS)/Q11/structured_run1.json \
         $(RESULTS)/Q12/structured_run1.json \
         $(RESULTS)/Q13/structured_run1.json \
         $(RESULTS)/Q11/rag_run1.json \
         $(RESULTS)/Q12/rag_run1.json \
         $(RESULTS)/Q13/rag_run1.json \
         score report
	@echo "[done] Enriched-tier (Q11–Q13) benchmark complete"

# ---------------------------------------------------------------
# Ground truth (from YAML)
# ---------------------------------------------------------------

ground-truth: ground_truth.json questions.json

ground_truth.json questions.json: $(SCRIPTS)/compute_ground_truth.py
	$(PYTHON) $(SCRIPTS)/compute_ground_truth.py \
	    --disorders-dir $(DISORDERS) \
	    --output-dir .

# ---------------------------------------------------------------
# Corpus extraction (TypeDB → JSONL)
# ---------------------------------------------------------------

corpus-extract: $(CORPUS)/phenotype_texts.jsonl $(CORPUS)/treatment_texts.jsonl $(CORPUS)/genetic_texts.jsonl

$(CORPUS)/phenotype_texts.jsonl $(CORPUS)/treatment_texts.jsonl $(CORPUS)/genetic_texts.jsonl: \
        $(SCRIPTS)/extract_enriched_texts.py
	$(PYTHON) $(SCRIPTS)/extract_enriched_texts.py \
	    --typedb-database $(TYPEDB_DB) \
	    --corpus-dir $(CORPUS)

# ---------------------------------------------------------------
# RAG index build
# ---------------------------------------------------------------

corpus-build: corpus-extract
	$(PYTHON) $(SCRIPTS)/build_rag.py --layer phenotypes
	$(PYTHON) $(SCRIPTS)/build_rag.py --layer treatments
	$(PYTHON) $(SCRIPTS)/build_rag.py --layer genetic

corpus-build-all:
	$(PYTHON) $(SCRIPTS)/build_rag.py --layer all

# ---------------------------------------------------------------
# Structured condition
# ---------------------------------------------------------------

run-structured:
	$(PYTHON) $(SCRIPTS)/run_structured.py \
	    --results-dir $(RESULTS)

$(RESULTS)/Q11/structured_run1.json $(RESULTS)/Q12/structured_run1.json $(RESULTS)/Q13/structured_run1.json:
	$(PYTHON) $(SCRIPTS)/run_structured.py \
	    --results-dir $(RESULTS) \
	    --question-ids Q11,Q12,Q13

# ---------------------------------------------------------------
# RAG condition
# ---------------------------------------------------------------

run-rag:
	$(PYTHON) $(SCRIPTS)/run_rag.py \
	    --results-dir $(RESULTS)

$(RESULTS)/Q11/rag_run1.json $(RESULTS)/Q12/rag_run1.json $(RESULTS)/Q13/rag_run1.json:
	$(PYTHON) $(SCRIPTS)/run_rag.py \
	    --results-dir $(RESULTS) \
	    --question-ids Q11,Q12,Q13

# ---------------------------------------------------------------
# Scoring and reporting
# ---------------------------------------------------------------

score: $(RESULTS)/scores.json

$(RESULTS)/scores.json:
	$(PYTHON) $(SCRIPTS)/score.py \
	    --disorders-dir $(DISORDERS) \
	    --results-dir $(RESULTS)

report: score
	$(PYTHON) $(SCRIPTS)/report.py \
	    --results-dir $(RESULTS)

# ---------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------

clean-new:
	rm -f $(RESULTS)/Q11/structured_run1.json \
	      $(RESULTS)/Q12/structured_run1.json \
	      $(RESULTS)/Q13/structured_run1.json \
	      $(RESULTS)/Q11/rag_run1.json \
	      $(RESULTS)/Q12/rag_run1.json \
	      $(RESULTS)/Q13/rag_run1.json \
	      $(RESULTS)/scores.json

clean-corpus-enriched:
	rm -f $(CORPUS)/phenotype_texts.jsonl \
	      $(CORPUS)/treatment_texts.jsonl \
	      $(CORPUS)/genetic_texts.jsonl

# ---------------------------------------------------------------
# Help
# ---------------------------------------------------------------

help:
	@echo "DisMech Benchmark Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  all              Full pipeline Q1–Q13 (ground-truth + corpus + RAG index + runs + score + report)"
	@echo "  all-new          Enriched-tier pipeline Q11–Q13 only"
	@echo "  ground-truth     Recompute ground_truth.json from YAML"
	@echo "  corpus-extract   Extract phenotype/treatment/genetic texts from TypeDB → JSONL"
	@echo "  corpus-build     Index enriched JSONL layers into Qdrant"
	@echo "  corpus-build-all Index all layers (including abstracts, mechanisms, descriptions)"
	@echo "  run-structured   Run all structured-condition queries (Q1–Q13)"
	@echo "  run-rag          Run all RAG-condition queries (Q1–Q13)"
	@echo "  score            Score all results → results/scores.json"
	@echo "  report           Generate figures and markdown report"
	@echo "  clean-new        Remove Q11–Q13 result files (to re-run)"
	@echo ""
	@echo "Environment variables required:"
	@echo "  ANTHROPIC_API_KEY  — for RAG answer generation"
	@echo "  VOYAGE_API_KEY     — for RAG embedding"
