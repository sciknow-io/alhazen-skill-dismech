# alhazen-skill-dismech

An [Alhazen](https://github.com/sciknow/alhazen) skill plugin for the
**DisMech** Disease Mechanism Knowledge Graph — 750+ curated rare and complex
disorders with pathophysiology mechanisms, HPO phenotypes, gene associations,
and therapeutic targets stored in a [TypeDB 3.x](https://typedb.com) graph
database.

---

## What is DisMech?

DisMech is a curated knowledge base of human disease mechanisms.  Each disorder
entry contains:

- **Name and category** (Mendelian, Complex, Infectious, Other)
- **Parent categories** (disease hierarchy)
- **Disease term** — preferred MONDO/OMIM identifier and label
- **Pathophysiology mechanisms** — named, prose-described molecular and cellular
  mechanisms that explain the disorder

The data is stored in TypeDB 3.x using a schema generated from a
[LinkML](https://linkml.io) model, enabling rich graph queries across diseases,
mechanisms, and ontology terms.

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/sciknow/alhazen-skill-dismech.git
cd alhazen-skill-dismech
make init
```

`make init` starts the TypeDB Docker container (pulling `typedb/typedb:3.8.0`
if needed), creates the `dismech` database, and loads the TypeQL schema.

### 2. Ingest disorder data

You need a local copy of the DisMech knowledge base YAML files:

```bash
make ingest DISORDERS_DIR=/path/to/dismech/kb/disorders
```

Or with the default path:

```bash
make ingest   # uses ~/Documents/GitHub/dismech/kb/disorders
```

### 3. Query the database

```bash
# Database statistics
make stats

# Show a specific disease (JSON output)
uv run --project plugins/dismech/skills/dismech --python 3.12 \
  python plugins/dismech/skills/dismech/dismech.py show-disease \
  --name "Achondroplasia"

# Full-text search
uv run --project plugins/dismech/skills/dismech --python 3.12 \
  python plugins/dismech/skills/dismech/dismech.py search \
  --query "FGFR3"
```

### 4. Open the dashboard

```bash
make serve    # starts on http://localhost:7777
```

Open your browser to `http://localhost:7777` for the interactive dashboard with
browse, detail, and search tabs.

---

## Architecture

```
dismech/kb/disorders/*.yaml
        │
        ▼  (dismech.py ingest)
  TypeDB 3.x graph database
        │
        ├── disease entities (name, category, parents, synonyms)
        ├── diseasedescriptor entities (preferred-term / MONDO)
        │   └── disease-term relations
        └── pathophysiology entities (name, description)
            └── pathophysiology-rel relations
        │
        ▼  (dismech.py serve)
  HTTP dashboard + REST API
```

**Three-tier ingestion model:**

| Tier | Entity type | Key attributes |
|---|---|---|
| 1 | `disease` | `name` (key), `category`, `parents`, `synonyms` |
| 2 | `diseasedescriptor` | `preferred-term` |
| 3 | `pathophysiology` | `name`, `description` |

The TypeQL schema is defined in `plugins/dismech/skills/dismech/schema.tql`,
derived from the LinkML `dismech.yaml` model via `gen-typedb`.

---

## CLI Reference

See [`plugins/dismech/skills/dismech/USAGE.md`](plugins/dismech/skills/dismech/USAGE.md)
for the full command reference with options and example outputs.

---

## Alhazen Integration

This skill auto-initializes TypeDB on Claude Code session start via the
`SessionStart` hook.  When loaded in Alhazen, it responds to prompts like:

- "show me disease mechanisms for Marfan syndrome"
- "pathophysiology of alpha-1 antitrypsin deficiency"
- "what are the mechanisms in Mendelian bone diseases?"

---

## Requirements

- Docker (for TypeDB container)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

Python dependencies are declared in
`plugins/dismech/skills/dismech/pyproject.toml` and managed automatically by
`uv`.

---

## License

Apache-2.0. See [LICENSE](LICENSE).

Copyright SciKnow.io and contributors, 2025.
