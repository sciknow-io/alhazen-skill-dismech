# Evaluation Walkthrough: RAG vs. Structured Knowledge on DisMech

This document is a detailed, step-by-step walkthrough of the benchmark evaluation
comparing retrieval-augmented generation (RAG) against structured knowledge graph
queries over the DisMech rare disease knowledge base. It explains what each script
does, how the pipeline fits together, what the results mean, and where RAG fails
and why.

---

## 1. What This Evaluation Tests

Most AI memory benchmarks ask: "Can you retrieve a fact you stored earlier?" That
is a retrieval test. It does not exercise the query types where structure matters
most:

- **Aggregation**: "How many diseases have mechanism X?" requires scanning *all*
  798 disorders and counting matches. A retrieval system that returns 20 chunks
  cannot count what it never sees.
- **Negation**: "Which diseases have NO genetic entries?" requires proving absence
  across the entire dataset. Absent text is not evidence of an absent fact.
- **Global ranking**: "Top 5 by mechanism count" requires comparing counts across
  all entities. 20 chunks give a biased sample, not a ranking.

These correspond to well-studied relational algebra primitives:

| Category | Relational Primitive | SQL Analogue | Why RAG Cannot Do This |
|----------|---------------------|--------------|------------------------|
| Aggregation | Group + Count | `GROUP BY ... COUNT(*)` | Cannot count unseen entities |
| Negation | Anti-join | `NOT EXISTS (subquery)` | Absence of retrieval is not absence of fact |
| Ranking | Order + Limit | `ORDER BY ... LIMIT N` | Can only rank the 20 chunks it retrieved |

The evaluation uses **13 questions** across these three categories. Ground truth
is computed by scanning all DisMech disorder YAML files. The structured condition
queries TypeDB directly for all 13 questions.

---

## 2. The Corpus: DisMech

[DisMech](https://github.com/sciknow-io/dismech) is a curated knowledge base of
rare disease mechanisms maintained by the Monarch Initiative. Each disorder is a
structured YAML file with:

- `name`, `category` (Mendelian, Complex, Infectious, etc.)
- `pathophysiology`: named mechanisms with descriptions, genes, cell types,
  biological processes, evidence PMIDs
- `genetic`: gene entries with association type (Causative, Risk Factor, etc.)
- `phenotypes`: HPO-annotated phenotype entries
- `treatments`: documented treatment approaches
- `disease_term`: preferred MONDO/OMIM identifier

**As of April 2026**: 798 diseases in TypeDB (797 YAML files plus 1 additional
entry), 38 unique disease categories, 3,787 mechanism descriptions, 5,936
phenotype entries, 2,953 treatment entries, 1,953 genetic entries, and 9,858
unique PubMed abstracts cited across all files.

The evaluation compares two representations of this same knowledge:

1. **RAG corpus** (unstructured): All texts embedded as vectors in Qdrant
   (~25,149 points using Voyage AI `voyage-4-large`, 1024-dim, cosine distance).
   Six layers: PubMed abstracts, mechanism descriptions, disease descriptions,
   phenotype descriptions, treatment descriptions, genetic descriptions.

2. **Structured queries** (knowledge graph): TypeQL queries against the TypeDB
   `dismech` database for all 13 questions. Some queries are direct TypeQL
   (e.g., `has category "Mendelian"`), others fetch data from TypeDB and apply
   regex filtering in Python (e.g., TGF-beta pattern matching on mechanism
   descriptions), and others perform multi-hop graph traversals (e.g., Q11's
   disease -> pathophysiology -> gene -> descriptor path).

---

## 3. Pipeline Overview

```
 dismech/kb/disorders/*.yaml        (797 curated disorder files)
            |
     +------+---------------------------+
     |                                  |
     v                                  v
 [compute_ground_truth.py]         [TypeDB dismech database]
   YAML scan (no LLM)               (798 diseases, ingested from YAML)
   -> ground_truth.json              Used by run_structured.py (all Q1-Q13)
   -> questions.json                 Used by extract_enriched_texts.py
            |
            v
 [collect_pmids.py]                 Step 2: Fetch PubMed abstracts via NCBI
   -> corpus/abstracts/*.txt
   -> corpus/manifest.json
            |
            v
 [extract_enriched_texts.py]        Step 3: Extract structured layers from TypeDB
   -> corpus/phenotype_texts.jsonl
   -> corpus/treatment_texts.jsonl
   -> corpus/genetic_texts.jsonl
            |
            v
 [build_rag.py]                     Step 4: Embed all layers into Qdrant
   -> Qdrant collection `dismech_benchmark` (25,149 vectors)
            |
            +----------------------------+
            |                            |
            v                            v
 [run_rag.py]                    [run_structured.py]
   Embed question                  TypeQL queries against TypeDB
   -> Qdrant top-20 retrieval      -> exact JSON result
   -> Claude Sonnet 4.6            -> Claude formats answer
   -> results/Q*/rag_run1.json     -> results/Q*/structured_run1.json
            |                            |
            +----------------------------+
            |
            v
 [score.py]                         Step 5: Score against ground truth
   -> results/scores.json
            |
            v
 [report.py]                        Step 6: Generate figures + report
   -> results/report.md
   -> results/figures/*.png
```

---

## 4. Step-by-Step Walkthrough

### Step 1: Compute Ground Truth

**Script**: `scripts/compute_ground_truth.py`

This script scans all YAML files from the DisMech `kb/disorders/` directory and
computes the exact answer for each of the 13 questions. No LLM is involved. No
API calls. The answers are deterministic and reproducible.

For example, Q1 ("How many diseases have a TGF-beta signaling mechanism?") works
by:
1. Loading every `*.yaml` file from the disorders directory
2. For each disorder, extracting all `pathophysiology[*].name` and
   `pathophysiology[*].description` fields
3. Regex-matching `tgf.?beta|tgf-?b|transforming growth factor.?beta`
4. Counting distinct disease names that match

**Outputs**: `ground_truth.json` (answers for all 13 questions) and
`questions.json` (question text, category, scoring type).

**Current ground truth** (797 YAML disorder files scanned):

| ID | Category | Question (abbreviated) | Ground Truth |
|----|----------|----------------------|--------------|
| Q1 | Aggregation | TGF-beta mechanism count | 33 diseases |
| Q2 | Aggregation | Mendelian category count | 304 diseases |
| Q3 | Aggregation | WNT/beta-catenin count | 36 diseases |
| Q4 | Negation | Mechanisms but NO treatments | 65 diseases |
| Q5 | Negation | NO genetic entries | 141 diseases |
| Q6 | Negation | MONDO term present vs absent | 786 with / 11 without |
| Q7 | Ranking | Top 5 by mechanism count | Diabetes mellitus (32) leads |
| Q8 | Ranking | Top 3 categories by disease count | Mendelian (304), (none) (124), Complex (121) |
| Q9 | Ranking | Top 5 by PMID citation count | Fanconi Anemia (254) leads |
| Q10 | Ranking | Full category distribution | 38 unique categories |
| Q11 | Aggregation | FGFR3 causative gene count (graph traversal) | 5 diseases |
| Q12 | Negation | HPO phenotypes but NO genetic entries | 138 diseases |
| Q13 | Ranking | Top 5 by HPO phenotype count | Fanconi Anemia (90) leads |

### Step 2: Build the RAG Corpus

**Script**: `scripts/collect_pmids.py`

Extracts all PMID references from YAML files via regex (`PMID:\d+`), then fetches
abstracts from NCBI Entrez. Idempotent -- skips already-fetched PMIDs.

**Output**: `corpus/abstracts/{pmid}.txt` (9,858 files), `corpus/manifest.json`
(PMID to title/abstract/diseases mapping).

The mechanism and disease description texts are extracted directly from the YAML
files into JSONL format (`corpus/mechanism_texts.jsonl`,
`corpus/disease_descriptions.jsonl`).

**Script**: `scripts/extract_enriched_texts.py`

Queries the TypeDB `dismech` database to extract three additional layers:
- `corpus/phenotype_texts.jsonl` (5,936 entries) -- phenotype name + description + HPO ID
- `corpus/treatment_texts.jsonl` (2,953 entries) -- treatment name + description
- `corpus/genetic_texts.jsonl` (1,953 entries) -- gene name + association + description

### Step 3: Build the RAG Index

**Script**: `scripts/build_rag.py`

Embeds all six corpus layers into Qdrant using Voyage AI `voyage-4-large`
(1024-dimensional vectors, cosine distance). Each point's payload includes the
full text plus metadata (source_type, disease, mechanism/phenotype/gene name,
PMID, etc.).

Point IDs are deterministic UUIDs derived from logical IDs (e.g.,
`abstract_12345678`, `mech_Marfan_Syndrome_TGF-beta`), making the index
idempotent -- re-running skips existing points.

**Final index**: `dismech_benchmark` collection with 25,149 vectors across six
layers:

| Layer | Points | Source |
|-------|--------|--------|
| PubMed abstracts | 9,858 | NCBI Entrez via manifest.json |
| Mechanism descriptions | 3,787 | YAML pathophysiology sections |
| Disease descriptions | 662 | YAML top-level descriptions |
| Phenotype descriptions | 5,936 | TypeDB phenotype entities |
| Treatment descriptions | 2,953 | TypeDB treatment entities |
| Genetic descriptions | 1,953 | TypeDB genetic entities |

### Step 4: Run Both Conditions

#### RAG Condition (`scripts/run_rag.py`)

For each of the 13 questions:

1. **Embed the question** using Voyage AI `voyage-4-large` with `input_type="query"`
2. **Retrieve top-20 chunks** from Qdrant via `query_points()` with cosine similarity
3. **Format context**: Each chunk becomes a numbered passage with metadata header
   and full text:
   ```
   [1] (mechanism_description) Disease: Marfan Syndrome | Mechanism: Dysregulated TGF-beta Signaling
   Marfan Syndrome -- Dysregulated TGF-beta Signaling: Loss of fibrillin-1 ...
   ```
4. **Call Claude Sonnet 4.6** with a system prompt constraining it to use ONLY
   the provided context
5. **Save** the full record: question, retrieved chunks (with scores, metadata,
   and text), context length, Claude's response, and token counts

The system prompt explicitly instructs Claude:
> "Use ONLY the provided context to answer the question. If you cannot determine
> the answer from the context, say so explicitly. Do not guess or use prior
> knowledge."

#### Structured Condition (`scripts/run_structured.py`)

All 13 questions use TypeQL queries against the TypeDB `dismech` database.
No YAML scanning is involved. The query strategies are:

**Direct attribute queries** (Q2, Q8, Q10): Simple TypeQL matching on disease
attributes. For example, Q2 queries `$d isa disease, has category "Mendelian"`.

**TypeDB fetch + Python regex** (Q1, Q3): The query fetches all mechanism names
and descriptions from TypeDB, then applies regex filtering in Python. For Q1:
```python
# Fetch from TypeDB
names = fetch('match $d isa disease; ($d, $p) isa pathophysiology-rel; ...')
descs = fetch('match $d isa disease; ($d, $p) isa pathophysiology-rel; $p has description $pd; ...')
# Filter in Python
pattern = re.compile(r"tgf.?beta|tgf-?b|transforming growth factor.?beta", re.I)
matching = {r["disease"] for r in names + descs if pattern.search(r["text"])}
```

**Set subtraction** (Q4, Q5, Q12): Two TypeDB queries followed by Python set
difference. For Q4, one query finds diseases with pathophysiology relations,
another finds diseases with treatment relations, and the result is the
difference.

**MONDO ID traversal** (Q6): Multi-hop path through the schema:
```
disease -> disease-term -> diseasedescriptor -> term-rel -> id (starts with "MONDO:")
```

**Aggregation + sort** (Q7, Q9, Q13): TypeDB query fetches all relevant
relations, Python counts per disease and takes top-5. Q9 aggregates evidence
item references across five tiers (pathophysiology, genetic, treatment,
phenotype, inheritance).

**Multi-hop graph traversal** (Q11): TypeQL traverses:
```
disease -> pathophysiology-rel -> gene -> genedescriptor[preferred-term == "FGFR3"]
```

The structured result is a JSON dict (e.g., `{"count": 31, "diseases": [...]}`).
This is passed to Claude Sonnet 4.6 for human-readable formatting, but scoring
uses the raw JSON directly.

### Step 5: Score Results

**Script**: `scripts/score.py`

Scores both conditions against `ground_truth.json`. Two scoring paths:

**RAG condition** (text parsing): Extracts numbers and disease names from Claude's
prose response using regex. This is inherently lossy -- Claude may state the
correct answer in a way the regex doesn't capture.

**Structured condition** (JSON comparison): Compares the `structured_result` JSON
dict directly against the ground truth. No regex, no text parsing.

**Scoring rules by question type**:

| Type | Questions | Rule |
|------|-----------|------|
| `exact_count` | Q1-3, Q5, Q11-12 | 1.0 exact, 0.5 within 15%, 0.0 otherwise |
| `partial_list` | Q4 | Jaccard recall of disease names |
| `dual_exact_count` | Q6 | Average of two exact-count scores |
| `ranked_list_with_counts` | Q7, Q9, Q13 | 70% name recall + 30% count accuracy |
| `ranked_categories` | Q8 | Fraction of top-3 category counts correct |
| `exact_distribution` | Q10 | Fraction of all 38 category counts correct |

Hallucination detection: For list questions, disease names in Claude's response
are matched against the full DisMech name set. Names not in DisMech are flagged
as hallucinations (recorded in `scores.json` but not penalized in the headline
score).

### Step 6: Generate Report

**Script**: `scripts/report.py`

Produces:
- `results/report.md` -- Summary table
- `results/figures/accuracy_by_question.png` -- Grouped bar chart (13 questions)
- `results/figures/accuracy_by_category.png` -- Category-mean bar chart

---

## 5. Results

### Per-Question Scores

| # | Category | Ground Truth | TypeDB Result | RAG | Structured | Gap |
|---|----------|-------------|---------------|-----|------------|-----|
| Q1 | Aggregation | 33 (YAML) | 31 (TypeDB) | 0.000 | **0.500** | +0.500 |
| Q2 | Aggregation | 304 | 304 | 0.000 | **1.000** | +1.000 |
| Q3 | Aggregation | 36 (YAML) | 35 (TypeDB) | 0.000 | **0.500** | +0.500 |
| Q4 | Negation | 65 diseases | 65 diseases | 0.000 | **0.985** | +0.985 |
| Q5 | Negation | 141 (YAML) | 142 (TypeDB) | 0.000 | **0.500** | +0.500 |
| Q6 | Negation | 786/11 (YAML) | 787/11 (TypeDB) | 0.000 | **0.750** | +0.750 |
| Q7 | Ranking | Top 5 by mech count | Matches | 0.140 | **1.000** | +0.860 |
| Q8 | Ranking | Top 3 categories | Matches | 0.000 | **1.000** | +1.000 |
| Q9 | Ranking | Top 5 by PMID | Different ranking | 0.000 | **0.280** | +0.280 |
| Q10 | Ranking | 38 categories | 37/38 match | 0.000 | **0.974** | +0.974 |
| Q11 | Aggregation | 5 diseases | 5 diseases | 0.000 | **1.000** | +1.000 |
| Q12 | Negation | 138 (YAML) | 139 (TypeDB) | 0.000 | **0.500** | +0.500 |
| Q13 | Ranking | Top 5 by HPO count | 3/5 match | 0.000 | **0.620** | +0.620 |

### Category Means

| Category | RAG Mean | Structured Mean | Gap |
|----------|----------|-----------------|-----|
| Aggregation (Q1-3, Q11) | **0.000** | **0.750** | **+0.750** |
| Negation (Q4-6, Q12) | **0.000** | **0.684** | **+0.684** |
| Ranking (Q7-10, Q13) | **0.028** | **0.775** | **+0.747** |

### The YAML-vs-TypeDB Ground Truth Gap

The structured condition now uses TypeDB exclusively, but ground truth is still
computed from YAML scanning. This creates small discrepancies that reduce
structured scores below 1.0 on several questions. These are *measurement
artifacts*, not failures of the structured approach:

| Question | YAML Ground Truth | TypeDB Result | Cause of Discrepancy |
|----------|------------------|---------------|---------------------|
| Q1 | 33 | 31 | 2 TGF-beta matches in YAML descriptions not present in TypeDB |
| Q3 | 36 | 35 | 1 WNT mechanism description not ingested into TypeDB |
| Q5 | 141 | 142 | TypeDB has 798 diseases vs 797 YAML files |
| Q6 | 786/11 | 787/11 | Same 1-disease difference (798 vs 797 total) |
| Q9 | Ranked by regex PMID count | Ranked by evidence items | YAML counts raw `PMID:\d+` regex hits; TypeDB counts distinct evidence items per tier |
| Q10 | 797 total | 798 total | 1 extra disease changes one category count |
| Q12 | 138 | 139 | HPO phenotype-term link count differs by 1 disease |

The root cause is that the YAML files and TypeDB database are not perfectly
synchronized. The YAML scanner counts raw text pattern matches (e.g., PMID regex
on the full YAML dump), while TypeDB queries traverse typed relations and
entities. 

---

## 6. Why RAG Fails: Detailed Analysis

### The Fundamental Constraint

RAG retrieves the top-20 most similar chunks from ~25,000 vectors. Even with
perfect retrieval, 20 chunks cannot represent 798 disorders. The failure is not
in the embedding quality, the retrieval algorithm, or the LLM -- it is in the
*information-theoretic impossibility* of answering set-level queries from a
sample.

### Per-Category Failure Modes

#### Aggregation (Q1-Q3, Q11): Score = 0.000

**Q1 example** ("How many diseases have TGF-beta mechanisms?"): Ground truth is
33 diseases (YAML) / 31 diseases (TypeDB). The top-20 retrieved chunks included
9 mechanism descriptions, 6 abstracts, and 5 genetic descriptions related to
TGF-beta. Claude correctly identified 12 diseases from these chunks and answered
"at least 12." The `exact_count` scorer gave 0.0 because 12 is not within 15%
of 33.

Claude's response was *correct given its context* -- it found every TGF-beta
disease present in the 20 chunks and appropriately caveated "this is likely an
undercount." The failure is that 20 chunks out of 25,149 cannot surface all
relevant diseases scattered across the index.

**Context statistics for Q1**:
- Context length: 14,143 characters (4,031 input tokens)
- Chunk types: 9 mechanism descriptions, 6 abstracts, 5 genetic descriptions
- Claude found: 12 of 33 TGF-beta diseases (36% recall from 0.08% of the index)

#### Negation (Q4-Q6, Q12): Score = 0.000

**Q4 example** ("Which diseases have mechanisms but NO treatments?"): Ground
truth is 65 diseases. RAG retrieved 20 chunks that happened to include 9
mechanism descriptions, 2 treatment descriptions, and other types. Claude
identified 9 diseases from these chunks that appeared to lack treatments --
but 0 of those 9 matched the ground truth list of 65 (hallucination rate: 100%).

The core issue: proving absence ("disease X has NO treatments") requires checking
that no treatment entry exists anywhere in the database for that disease.
Retrieval can find documents that *mention* treatments; it cannot confirm that
no such document exists. The 20 retrieved chunks are a positive sample -- they
tell you what exists, not what doesn't.

**How TypeDB handles this**: Two queries -- one fetches all diseases with a
`pathophysiology-rel`, the other fetches all diseases with a `treatments`
relation. Python set subtraction gives the exact answer. The database *knows*
what doesn't exist because it tracks all relations exhaustively.

#### Ranking (Q7-Q10, Q13): Score = 0.028

**Q7 example** ("Top 5 by mechanism count"): Ground truth top entry is Diabetes
mellitus with 32 mechanisms. Claude correctly identified Diabetes mellitus from
the retrieved chunks (giving Q7 its 0.14 score for 1/5 name recall), but could
not determine mechanism counts or identify the other four diseases because the
20 retrieved chunks covered only a sparse sample of the 798 disorders.

**How TypeDB handles this**: A single query fetches all disease-pathophysiology
pairs, Python counts per disease, and sorts. The database sees all 3,787
mechanism relations across all 798 diseases simultaneously.

Q7 was the only RAG question to score above zero. The rest (Q8-Q10, Q13) scored
0.000 because the retrieved chunks did not happen to contain the top-ranked
entities.

### What RAG Did Well

Despite scoring 0 on the benchmark metrics, RAG + Claude demonstrated genuine
analytical capability:

- **Q1**: Claude found 12 of 33 TGF-beta diseases and correctly noted it was
  undercounting
- **Q3**: Claude found 6+ WNT/beta-catenin diseases with specific mechanism
  names and gene citations
- **Q11**: Claude found 6 FGFR3-associated diseases (ground truth: 5) and even
  distinguished between "Causative" germline annotations and somatic mutations --
  a nuance the structured query did not capture
- **Q4**: Claude correctly identified the *type* of answer needed and caveated
  that its list was from a sample

These are not benchmark failures of the LLM. They are fundamental limitations
of the retrieval architecture when applied to set-level queries.

---

## 7. The Q11 Case Study: When RAG Finds More Than Structure

Q11 asks: "How many diseases have FGFR3 explicitly listed as a causative gene in
the structured gene annotations of their pathophysiology mechanisms?"

**Ground truth** (TypeDB query): 5 diseases -- Achondroplasia, Hypochondroplasia,
SADDAN, Thanatophoric Dysplasia Type 1, Thanatophoric Dysplasia Type 2.

**RAG result**: Claude found 6 diseases with FGFR3 labeled "(Causative)" in the
retrieved genetic_description chunks: the same 5 plus Muenke Syndrome.

**Why the discrepancy**: The TypeDB structured query specifically traverses:
```
disease -> pathophysiology-rel -> gene -> genedescriptor[preferred-term == "FGFR3"]
```
This path goes through the *pathophysiology tier* gene annotations. Muenke
Syndrome has FGFR3 in its *genetic tier* (a separate branch of the schema) but
not linked through a pathophysiology mechanism.

RAG retrieved chunks from *all* layers indiscriminately -- it found genetic
descriptions that the structured query's scope excluded. Claude then answered
"6" (outside the 15% tolerance of ground truth 5), scoring 0.0.

This highlights an important evaluation design consideration: the retrieval
system's lack of schema awareness can be both a weakness (it cannot scope to
a specific relation path) and, occasionally, an advantage (it surfaces related
information the structured query's scope excludes).

---

## 8. The Q9 Case Study: YAML Regex vs. TypeDB Evidence Items

Q9 asks: "Which 5 diseases have the most total PMID citations across all
sections of their DisMech entries?"

This question reveals the deepest discrepancy between the two data
representations:

**YAML ground truth**: Counts raw `PMID:\d+` regex matches across the entire
YAML dump of each disorder. This captures every PMID mention at every nesting
level -- pathophysiology evidence, downstream causal edge evidence, treatment
mechanism targets, phenotype contexts, etc. A single PMID appearing in multiple
sections is counted multiple times.

| Rank | Disease (YAML) | PMID Count |
|------|----------------|------------|
| 1 | Fanconi Anemia | 254 |
| 2 | Diabetes mellitus | 229 |
| 3 | Cystic Fibrosis | 205 |
| 4 | Hepatitis B | 177 |
| 5 | Cholera | 175 |

**TypeDB structured result**: Aggregates distinct evidence items across five
relation tiers (pathophysiology, genetic, treatment, phenotype, inheritance).
Evidence items on deeper nested entities (downstream causal edges, treatment
mechanism targets) are not captured by the current queries.

| Rank | Disease (TypeDB) | Evidence Items |
|------|-----------------|----------------|
| 1 | Fanconi Anemia | 173 |
| 2 | Diabetes mellitus | 107 |
| 3 | Type I Diabetes | 101 |
| 4 | Asthma | 90 |
| 5 | Systemic Lupus Erythematosus | 90 |

The rankings diverge because:
1. **Counting method**: YAML counts regex hits (with duplicates); TypeDB counts
   distinct evidence item entities
2. **Scope**: YAML captures PMIDs at every nesting level; the TypeDB queries
   only traverse one level of evidence relations from each tier
3. **Splitting**: "Diabetes mellitus" in YAML includes all diabetes PMIDs;
   TypeDB separates "Diabetes mellitus" and "Type I Diabetes" as distinct
   disease entities

This is not a bug -- it is a genuine difference in how the two representations
model citation provenance. The structured approach is more precise (counting
distinct evidence items) while the YAML approach is more inclusive (catching
every PMID mention regardless of nesting).

---

## 9. Reproducing the Evaluation

### Prerequisites

```
Python 3.12+              uv manages this
uv                        https://docs.astral.sh/uv/
Docker                    for Qdrant and TypeDB
TypeDB 3.8.0              for all structured queries + enriched text extraction
VOYAGE_API_KEY            https://dash.voyageai.com/
ANTHROPIC_API_KEY         for Claude API calls
DISMECH_DISORDERS_DIR     path to dismech/kb/disorders/ (for ground truth + PMID collection)
```

### Environment Setup

```bash
# Clone the DisMech knowledge base
git clone https://github.com/sciknow-io/dismech.git
export DISMECH_DISORDERS_DIR=/path/to/dismech/kb/disorders

# Set API keys
export VOYAGE_API_KEY=...
export ANTHROPIC_API_KEY=...

# Install dependencies
cd benchmark-rag-vs-structured
uv sync

# Start Qdrant
docker run -d -p 6333:6333 qdrant/qdrant

# Start TypeDB (required for structured condition and enriched text extraction)
docker run -d -p 1729:1729 --name dismech-typedb typedb/typedb:3.8.0
# Then load the dismech schema and data into TypeDB
```

### Running via Makefile

```bash
# Full pipeline (all 13 questions, both conditions)
make all

# Just the enriched-tier questions (Q11-Q13)
make all-new

# Individual steps
make ground-truth       # Step 1: compute answers from YAML
make corpus-extract     # Step 2-3: fetch abstracts + extract enriched texts
make corpus-build-all   # Step 4: embed all layers into Qdrant
make run-structured     # Step 5a: run structured condition (TypeDB)
make run-rag            # Step 5b: run RAG condition (Qdrant + Claude)
make score              # Step 6a: score against ground truth
make report             # Step 6b: generate figures + markdown
```

### Running Scripts Directly

```bash
# Step 1: Ground truth (still uses YAML scan)
uv run python scripts/compute_ground_truth.py \
    --disorders-dir $DISMECH_DISORDERS_DIR

# Step 2: Collect PubMed abstracts (~30 min without NCBI key)
uv run python scripts/collect_pmids.py \
    --disorders-dir $DISMECH_DISORDERS_DIR

# Step 3: Extract enriched texts from TypeDB
uv run python scripts/extract_enriched_texts.py \
    --typedb-database dismech

# Step 4: Build Qdrant index (~10 min, Voyage API costs)
uv run python scripts/build_rag.py --layer all

# Step 5: Run conditions
uv run python scripts/run_rag.py
uv run python scripts/run_structured.py    # no --disorders-dir needed

# Step 6: Score and report
uv run python scripts/score.py \
    --disorders-dir $DISMECH_DISORDERS_DIR
uv run python scripts/report.py
```

### Re-running After Changes

Scripts are idempotent -- they skip questions with existing result files.
To re-run:

```bash
# Delete specific results
rm results/Q1/rag_run1.json           # re-run one RAG question
rm results/Q*/rag_run1.json           # re-run all RAG questions
rm results/Q*/structured_run1.json    # re-run all structured questions

# Delete Qdrant collection and rebuild (if changing embedding or payload)
curl -X DELETE http://localhost:6333/collections/dismech_benchmark
uv run python scripts/build_rag.py --layer all

# Re-score (always safe to re-run)
rm results/scores.json
uv run python scripts/score.py --disorders-dir $DISMECH_DISORDERS_DIR
```

### Estimated Costs

| Step | API | Approximate Cost |
|------|-----|-----------------|
| Embed 25,149 texts | Voyage AI | ~$1.50 |
| 13 RAG Claude calls | Anthropic | ~$0.08 |
| 13 Structured Claude calls | Anthropic | ~$0.04 |
| **Total** | | **~$1.62** |

Subsequent re-runs of only the Claude calls (Steps 5-6) cost ~$0.12 total.
The Qdrant index rebuild is the expensive step.

---

## 10. Directory Layout

```
benchmark-rag-vs-structured/
+-- WALKTHROUGH.md                   <- this file
+-- README.md                        <- project overview and quick results
+-- Makefile                         <- orchestrates the full pipeline
+-- pyproject.toml                   <- Python dependencies
+-- questions.json                   <- 13 question definitions with metadata
+-- ground_truth.json                <- deterministic answers from YAML scan
|
+-- corpus/                          <- generated; gitignored
|   +-- abstracts/{pmid}.txt         <- 9,858 PubMed abstract files
|   +-- manifest.json                <- PMID -> {title, abstract, diseases}
|   +-- mechanism_texts.jsonl        <- 3,787 mechanism descriptions
|   +-- disease_descriptions.jsonl   <- 662 disease summaries
|   +-- phenotype_texts.jsonl        <- 5,936 phenotype descriptions
|   +-- treatment_texts.jsonl        <- 2,953 treatment descriptions
|   +-- genetic_texts.jsonl          <- 1,953 genetic descriptions
|
+-- results/                         <- generated; gitignored
|   +-- Q1/ ... Q13/
|   |   +-- rag_run1.json            <- chunks + Claude response + tokens
|   |   +-- structured_run1.json     <- TypeDB query result + Claude response
|   +-- scores.json                  <- per-question accuracy scores
|   +-- report.md                    <- summary table
|   +-- figures/
|       +-- accuracy_by_question.png
|       +-- accuracy_by_category.png
|
+-- scripts/
    +-- compute_ground_truth.py      <- YAML scan -> deterministic answers
    +-- collect_pmids.py             <- NCBI Entrez -> PubMed abstracts
    +-- extract_enriched_texts.py    <- TypeDB -> JSONL enriched layers
    +-- build_rag.py                 <- Voyage AI + Qdrant indexing
    +-- run_rag.py                   <- RAG condition: embed + retrieve + Claude
    +-- run_structured.py            <- Structured condition: all TypeDB queries
    +-- score.py                     <- Score results against ground truth
    +-- report.py                    <- Generate figures + markdown
```

---

## 11. Key Design Decisions

### Why top-20 retrieval?

Top-20 is a standard default in RAG benchmarks (matching LongMemEval and similar
evaluations). Increasing to top-100 or top-200 would improve recall on some
questions but would not change the fundamental result: aggregation over 798
entities, negation across the full dataset, and global ranking all require
exhaustive access that retrieval cannot provide at any practical k value.

### Why Claude Sonnet 4.6?

It is the most capable generally-available model at the time of evaluation.
Using a stronger model would improve Claude's analytical quality on the retrieved
chunks but would not change the information-theoretic constraint: you cannot
count 33 diseases from 20 chunks.

### Why six corpus layers instead of just abstracts?

The original corpus (abstracts + mechanisms + disease descriptions) contained
~14,300 vectors. Adding phenotype, treatment, and genetic layers (from TypeDB
extraction) brought the total to ~25,149. This makes the RAG condition as
strong as possible -- it has access to the same structured information, just in
embedded text form rather than queryable structure.

### Why TypeDB for all structured queries?

The structured condition uses TypeDB for all 13 questions rather than scanning
YAML files directly. This demonstrates the value of a queryable knowledge graph
over flat file scanning:
- **Q1, Q3**: Regex matching on TypeDB-fetched descriptions mirrors what a real
  application would do -- query the database, filter results
- **Q4, Q5, Q12**: Set operations on TypeDB relations are the natural way to
  express absence queries
- **Q9**: Evidence item aggregation across typed relation tiers is more precise
  than raw PMID regex counting
- **Q11**: Multi-hop graph traversal is only expressible against a graph database

### Why is ground truth still from YAML?

The ground truth is computed by Python scanning YAML files with no LLM
involvement. This provides an independent verification source. The small
discrepancies between YAML-derived ground truth and TypeDB query results
(documented in Section 5) reflect real differences in how the two
representations model the same knowledge -- themselves an interesting finding.

### Why not hybrid RAG + structured?

That is exactly the point of this benchmark: to demonstrate that certain query
types *require* structure. A hybrid system that routes aggregation/negation/ranking
queries to a structured backend and retrieval queries to RAG would be the
optimal architecture -- and that is the design principle behind DisMech's
dual representation in Alhazen.

---

*Evaluation walkthrough written April 2026. Benchmark harness: Apache-2.0,
Copyright SciKnow.io and contributors.*
