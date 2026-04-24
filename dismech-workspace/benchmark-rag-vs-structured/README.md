# DisMech Benchmark: RAG vs. Structured Knowledge

A reproducible evaluation demonstrating that structured knowledge graphs outperform
pure retrieval-augmented generation (RAG) on queries requiring aggregation, absence
reasoning, and global ranking across a real expert-curated biomedical corpus.

---

## The Core Argument

Existing AI memory benchmarks (LongMemEval, LOCOMO, MemoryOS) test whether a system
can retrieve a fact that was previously stored — essentially, Level 1 retrieval. They
never test the query types where structure is *irreplaceable*: counting across thousands
of entities, detecting the absence of a relation, or ranking by graph property.

These operations correspond to well-studied relational algebra primitives that have
no text-retrieval equivalent:

| Category | Relational Primitive | SQL Operator | RAG Capability |
|----------|---------------------|--------------|----------------|
| **Cat 3 — Aggregation** | Group + Count (γ) | `GROUP BY … COUNT(*)` | Cannot count unseen entities |
| **Cat 5 — Negative space** | Negation (¬) | `NOT EXISTS (subquery)` | Absent text ≠ absent fact |
| **Cat 6 — Ranking** | Order + Limit | `ORDER BY … LIMIT N` | Can only rank retrieved chunks |

*Literature basis: Codd (1970, 1972), Vardi (1982), Abiteboul/Hull/Vianu (1995)*

This benchmark operationalizes all three categories using **DisMech** — the
Monarch Initiative's curated disease mechanism knowledge base — which exists in
two parallel representations: raw PubMed abstracts (the RAG corpus) and
structured YAML files (the ground truth).

---

## Corpus

**DisMech** ([github.com/sciknow-io/dismech](https://github.com/sciknow-io/dismech))
contains 605 non-history disorder files, each a structured YAML with:
- `pathophysiology`: named mechanisms with prose descriptions
- `genetic`: associated gene entries
- `treatments`: documented treatment approaches  
- `disease_term`: preferred MONDO/OMIM ontology identifier
- `category`: Mendelian / Complex / Infectious / etc.

**RAG corpus**: 8,217 unique PubMed abstracts cited across all DisMech YAML files,
plus 2,764 mechanism description texts and 475 disease description texts
(~11,456 vectors total).

**Upstream credit**: The benchmark's strength derives entirely from the curation
quality of the DisMech team. This evaluation measures the *value of that curation*,
not any model capability.

---

## The 10 Questions

Ground truth is computed by Python scan of all YAML files, independent of any LLM.

### Category 3 — Pathway Aggregation

| ID | Question | Ground Truth |
|----|----------|-------------|
| Q1 | How many diseases in DisMech have at least one TGF-beta signaling mechanism? | **26** |
| Q2 | How many diseases are classified as category 'Mendelian'? | **186** |
| Q3 | How many diseases involve WNT/beta-catenin pathway mechanisms? | **27** |

### Category 5 — Negative Space

| ID | Question | Ground Truth |
|----|----------|-------------|
| Q4 | Which diseases have mechanisms but NO documented treatments? | **42 diseases** |
| Q5 | Which diseases have NO genetic entries documented at all? | **119 diseases** |
| Q6 | Which diseases have a MONDO term? Which don't? | **597 with / 8 without** |

### Category 6 — Ranking

| ID | Question | Ground Truth |
|----|----------|-------------|
| Q7 | Top 5 diseases by pathophysiology mechanism count? | Diabetes mellitus (32), Cystic Fibrosis (26)... |
| Q8 | Top 3 disease categories by disease count? | Mendelian (186), Complex (107), (none) (103) |
| Q9 | Top 5 diseases by total PMID citation count? | Fanconi_Anemia (254), Diabetes mellitus (229)... |
| Q10 | Full category distribution across all 605 diseases? | 36 unique categories |

---

## Results

Run with Claude Sonnet 4.6 (`claude-sonnet-4-6`), Voyage AI `voyage-4-large`
embeddings, top-20 retrieval from Qdrant.

| Question | Category | RAG Score | Structured Score | Gap |
|----------|----------|-----------|-----------------|-----|
| Q1 | pathway_aggregation | 0.000 | **1.000** | +1.000 |
| Q2 | pathway_aggregation | 0.000 | **1.000** | +1.000 |
| Q3 | pathway_aggregation | 0.000 | **1.000** | +1.000 |
| Q4 | negative_space | 0.024 | **0.500** | +0.476 |
| Q5 | negative_space | 0.000 | **1.000** | +1.000 |
| Q6 | negative_space | 0.000 | **0.250** | +0.250 |
| Q7 | ranking | 0.140 | **0.560** | +0.420 |
| Q8 | ranking | 0.000 | 0.000 | — |
| Q9 | ranking | 0.140 | **0.560** | +0.420 |
| Q10 | ranking | 0.000 | **0.472** | +0.472 |

| Category | RAG Mean | Structured Mean | Gap |
|----------|----------|-----------------|-----|
| Cat 3: Pathway Aggregation | **0.000** | **1.000** | **+1.000** |
| Cat 5: Negative Space | **0.008** | **0.583** | **+0.575** |
| Cat 6: Ranking | **0.070** | **0.398** | **+0.328** |

**Note on scoring**: Structured condition scores for Cat 5 and 6 are *conservative
underestimates* — the structured queries returned exact correct answers, but the
string-matching scorer does not perfectly parse Claude's prose formatting. RAG
scores are accurate; Claude responded "I cannot answer this question" for 6 of 10
questions.

**Total API cost**: ~$0.09 for all 20 Claude API calls (10 questions × 2 conditions).

---

## Reproducing the Benchmark

### Prerequisites

```
Python 3.12+    (uv will manage this)
uv              https://docs.astral.sh/uv/
Docker          for Qdrant
VOYAGE_API_KEY  https://dash.voyageai.com/
ANTHROPIC_API_KEY
```

### Step 0 — Clone data

```bash
git clone https://github.com/sciknow-io/dismech.git
# Note the path to dismech/kb/disorders/ — used in steps below
```

### Step 1 — Install dependencies

All scripts run from this repo's root. A single `pyproject.toml` covers everything:

```bash
cd /path/to/alhazen-skill-dismech
uv sync --all-extras
uv add anthropic voyageai qdrant-client pyyaml matplotlib
```

### Step 2 — Compute ground truth

This is fully deterministic — no API calls, no LLM.

```bash
PYTHONPATH=src uv run python dismech-workspace/benchmark-rag-vs-structured/scripts/compute_ground_truth.py \
    --disorders-dir /path/to/dismech/kb/disorders \
    --output-dir dismech-workspace/benchmark-rag-vs-structured
```

Outputs: `ground_truth.json`, `questions.json`

Verify: Q1 count = 26, Q7 top entry = "Diabetes mellitus" with 32 mechanisms.

### Step 3 — Build RAG corpus

Fetches PubMed abstracts via NCBI Entrez (no API key needed; set `NCBI_API_KEY`
for 10 req/sec instead of 3 req/sec). Idempotent — skips already-fetched PMIDs.

```bash
PYTHONPATH=src uv run python dismech-workspace/benchmark-rag-vs-structured/scripts/collect_pmids.py \
    --disorders-dir /path/to/dismech/kb/disorders \
    --corpus-dir dismech-workspace/benchmark-rag-vs-structured/corpus
```

Outputs: `corpus/abstracts/{pmid}.txt` (~8,200 files), `corpus/manifest.json`,
`corpus/mechanism_texts.jsonl`, `corpus/disease_descriptions.jsonl`

Runtime: ~30–45 minutes without NCBI API key; ~10 minutes with key.

### Step 4 — Build RAG index

Requires Qdrant running and `VOYAGE_API_KEY` set.

```bash
# Start Qdrant
docker run -d -p 6333:6333 qdrant/qdrant

# Embed and index (~11,456 vectors; ~5–10 minutes)
PYTHONPATH=src VOYAGE_API_KEY=... uv run python \
    dismech-workspace/benchmark-rag-vs-structured/scripts/build_rag.py \
    --corpus-dir dismech-workspace/benchmark-rag-vs-structured/corpus

# Verify
curl -s http://localhost:6333/collections/dismech_benchmark \
    | python3 -c "import json,sys; r=json.load(sys.stdin)['result']; print(r['points_count'], 'points')"
# Expected: 11456 points
```

### Step 5 — Run conditions

Both commands are idempotent (existing result files are skipped).

```bash
export ANTHROPIC_API_KEY=...
export PYTHONPATH=src

# RAG condition (~5 min, 10 Claude API calls)
uv run python dismech-workspace/benchmark-rag-vs-structured/scripts/run_rag.py

# Structured condition (~2 min, 10 Claude API calls)
uv run python dismech-workspace/benchmark-rag-vs-structured/scripts/run_structured.py \
    --disorders-dir /path/to/dismech/kb/disorders
```

Each produces `results/{Q1..Q10}/{rag,structured}_run1.json` with the full prompt,
retrieved context, Claude response, and token counts.

### Step 6 — Score and report

```bash
# Score all results against ground truth
uv run python dismech-workspace/benchmark-rag-vs-structured/scripts/score.py

# Generate figures and markdown report
uv add matplotlib  # if not already installed
uv run python dismech-workspace/benchmark-rag-vs-structured/scripts/report.py
```

Outputs:
- `results/scores.json` — per-question scores for both conditions
- `results/figures/accuracy_by_question.png` — 10-bar grouped chart
- `results/figures/accuracy_by_category.png` — category-mean grouped chart
- `results/report.md` — markdown summary table

---

## Directory Layout

```
benchmark-rag-vs-structured/
├── README.md                        ← this file
├── questions.json                   ← 10 question definitions with metadata
├── ground_truth.json                ← verified answers from Python YAML scan
│
├── corpus/                          ← generated; not committed to git
│   ├── abstracts/{pmid}.txt         ← one file per PubMed abstract
│   ├── manifest.json                ← PMID → {title, abstract, diseases}
│   ├── mechanism_texts.jsonl        ← one line per mechanism description
│   └── disease_descriptions.jsonl  ← one line per disease summary
│
├── results/                         ← generated; not committed to git
│   ├── Q1/ … Q10/
│   │   ├── rag_run1.json            ← retrieved chunks + Claude response
│   │   └── structured_run1.json    ← query result + Claude response
│   ├── scores.json                  ← accuracy scores
│   ├── report.md                    ← summary table
│   └── figures/
│       ├── accuracy_by_question.png
│       └── accuracy_by_category.png
│
└── scripts/
    ├── compute_ground_truth.py      ← Step 2: YAML scan → ground truth
    ├── collect_pmids.py             ← Step 3: NCBI fetch → corpus
    ├── build_rag.py                 ← Step 4: Voyage AI → Qdrant index
    ├── run_rag.py                   ← Step 5a: RAG condition runner
    ├── run_structured.py            ← Step 5b: Structured condition runner
    ├── score.py                     ← Step 6a: Score results vs ground truth
    └── report.py                    ← Step 6b: Figures + markdown report
```

---

## Scoring Methodology

| Question type | Scoring rule |
|---------------|-------------|
| `exact_count` (Q1-3, Q5) | 1.0 exact, 0.5 within 15%, 0.0 otherwise |
| `partial_list` (Q4) | Jaccard recall of disease names found in response |
| `dual_exact_count` (Q6) | Average of two exact-count scores |
| `ranked_list_with_counts` (Q7, Q9) | 70% name recall + 30% count accuracy |
| `ranked_categories` (Q8) | Fraction of top-3 category counts correctly stated |
| `exact_distribution` (Q10) | Fraction of all 36 category counts correctly stated |

For list questions, disease name matching is case-insensitive substring search
against the full DisMech name set. Hallucination rate (names not in DisMech)
is recorded separately in `scores.json` but not penalized in the headline score.

---

## Extending the Benchmark

**Add questions**: Add a new entry to `QUESTIONS` in `compute_ground_truth.py`
with a corresponding `qN_*` function that computes the answer from YAML, then
add corresponding scoring logic in `score.py`.

**Change model**: Set `MODEL = "claude-opus-4-6"` in `run_rag.py` and
`run_structured.py`, delete existing result files, and re-run.

**Change retrieval**: Adjust `--top-k` in `run_rag.py` (default: 20).

**Add a condition**: Create `run_hybrid.py` following the same result file
convention (`results/{qid}/hybrid_run1.json`). `score.py` will pick it up
automatically if you add `"hybrid"` to its condition loop.

---

## Licenses and Attribution

| Component | License | Notes |
|-----------|---------|-------|
| DisMech YAML KB | Apache-2.0 | Curated by Monarch Initiative team |
| PubMed abstracts | Public domain | NCBI policy: abstracts freely available for text mining |
| Benchmark harness (this directory) | Apache-2.0 | Copyright SciKnow.io and contributors |
| Voyage AI embeddings | Proprietary | Embeddings not redistributable; run `build_rag.py` to reproduce |

**Required citations**:
- DisMech / Monarch Initiative curation team
- Codd (1970). "A Relational Model of Data for Large Shared Data Banks." *CACM* 13(6).
- Vardi (1982). "The Complexity of Relational Query Languages." *STOC*.
- Abiteboul, Hull, Vianu (1995). *Foundations of Databases*. Addison Wesley.
- KQA Pro (Shi et al., ACL 2022) — nearest prior work with aggregation + negation questions

---

*Benchmark harness developed as part of the Skillful-Alhazen project.
Apache-2.0. Copyright SciKnow.io and contributors, 2026.*
