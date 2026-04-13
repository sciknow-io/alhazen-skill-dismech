# alhazen-skill-dismech

An [Alhazen](https://github.com/sciknow/alhazen) skill plugin for the
**DisMech** Disease Mechanism Knowledge Graph — 750+ curated rare and complex
disorders with pathophysiology mechanisms, parent hierarchies, and disease terms
stored in a [TypeDB 3.x](https://typedb.com) graph database.

---

## What is DisMech?

[DisMech](https://github.com/sciknow-io/dismech) is a curated knowledge base of
human disease mechanisms. Each disorder entry contains:

- **Name and category** (Mendelian, Complex, Infectious, Other)
- **Parent categories** (disease hierarchy)
- **Disease term** — preferred MONDO/OMIM identifier and label
- **Pathophysiology mechanisms** — named, prose-described molecular and cellular
  mechanisms that explain the disorder

This plugin bulk-ingests those YAML files into TypeDB 3.x, enabling graph queries
across diseases, mechanisms, and ontology terms from Claude Code or the included
web dashboard.

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) — TypeDB runs as a container
- [uv](https://docs.astral.sh/uv/) — Python environment manager
- **Python 3.12** — the `typedb-driver` package segfaults on Python 3.14 (the
  current Homebrew default); `uv` will download 3.12 automatically

### 1. Clone and initialize

```bash
git clone https://github.com/sciknow-io/alhazen-skill-dismech.git
cd alhazen-skill-dismech
make init
```

`make init` pulls `typedb/typedb:3.8.0`, starts the container, creates the
`dismech` database, and loads the TypeQL schema. Safe to run multiple times.

### 2. Get the disorder data

The knowledge base YAML files live in the
[dismech repo](https://github.com/sciknow-io/dismech):

```bash
git clone https://github.com/sciknow-io/dismech.git
```

### 3. Ingest disorders

```bash
make ingest DISORDERS_DIR=/path/to/dismech/kb/disorders
```

On the first full run this ingests all 605 non-history disorder files
(~2770 pathophysiology mechanisms) in about 20 seconds.

### 4. Query

```bash
# Database statistics
make stats
# -> {"success": true, "diseases": 605, "mechanisms": 2770, "disease_terms": 600}

# Look up a specific disease
uv run --project plugins/dismech/skills/dismech --python 3.12 \
  python plugins/dismech/skills/dismech/dismech.py show-disease \
  --name "Achondroplasia"

# Search by gene / term / mechanism keyword
uv run --project plugins/dismech/skills/dismech --python 3.12 \
  python plugins/dismech/skills/dismech/dismech.py search --query "FGFR3"
```

### 5. Open the dashboard

```bash
make serve    # starts on http://localhost:7777
```

Open `http://localhost:7777` for the interactive dashboard: browse all diseases
with category filters, look up individual disease detail cards, and run full-text
search.

---

## Architecture

```
dismech/kb/disorders/*.yaml
        │
        ▼  alhazen_core.py init
  TypeDB 3.x (Docker)
        │  schema.tql loaded once
        │
        ▼  dismech.py ingest
  ┌─────────────────────────────────┐
  │  disease entities               │  name (@key), category, parents, synonyms
  │    └── disease-term relations   │  → diseasedescriptor (preferred-term)
  │    └── pathophysiology-rel      │  → pathophysiology (name, description)
  └─────────────────────────────────┘
        │
        ▼  dismech.py serve
  HTTP dashboard + /api/* endpoints
```

**Three-tier ingestion model:**

| Tier | Entity type | Key attributes | TypeDB relation |
|------|------------|----------------|-----------------|
| 1 | `disease` | `name` (key), `category`, `parents` | — |
| 2 | `diseasedescriptor` | `preferred-term` | `disease-term` |
| 3 | `pathophysiology` | `name`, `description` | `pathophysiology-rel` |

### Schema

`plugins/dismech/skills/dismech/schema.tql` is the TypeQL schema, generated from
the LinkML `dismech.yaml` model via the `gen-typedb` generator in
[linkml](https://github.com/linkml/linkml). It is committed to this repo so no
regeneration step is needed at runtime.

One post-generation modification was applied: the `@key` constraint was removed
from `owns name` on all entity types **except** `disease`. The raw generated
schema annotates every entity's `name` attribute as `@key` (because LinkML
`identifier: true` propagates via inheritance), but mechanism names like
"Inflammation" legitimately repeat across many diseases, causing insertion
failures.  Only disease names are globally unique.

---

## CLI Reference

See [`plugins/dismech/skills/dismech/USAGE.md`](plugins/dismech/skills/dismech/USAGE.md)
for the full command reference with all options and example JSON output.

| Command | Description |
|---------|-------------|
| `alhazen_core.py init` | Start TypeDB container, create DB, load schema |
| `dismech.py ingest` | Bulk-ingest disorder YAML files |
| `dismech.py list-diseases` | List all (or category-filtered) diseases |
| `dismech.py show-disease` | Full disease record with mechanisms |
| `dismech.py search` | Substring search over names and mechanism names |
| `dismech.py stats` | Counts of diseases, mechanisms, disease terms |
| `dismech.py serve` | Start dashboard + REST API server |

---

## Alhazen Integration

When loaded as an Alhazen Claude Code skill, this plugin:

- Auto-initializes TypeDB on session start (via `hooks/hooks.json` `SessionStart` hook)
- Responds to natural-language prompts routed by `SKILL.md` trigger phrases, e.g.:
  - "show me disease mechanisms for Marfan syndrome"
  - "what genes are associated with achondroplasia?"
  - "pathophysiology of alpha-1 antitrypsin deficiency"
  - "list Mendelian bone diseases"

---

## Makefile Targets

```bash
make init                              # Start TypeDB + load schema
make ingest                            # Ingest from default disorders dir
make ingest DISORDERS_DIR=/custom/path
make stats                             # Print database counts
make serve                             # Dashboard on port 7777
make serve PORT=8080
make demo                              # init + ingest + stats
```

---

## Repository Layout

```
alhazen-skill-dismech/
├── skills/dismech/      ← edit here — the only manually maintained source
│   ├── dismech.py
│   ├── schema.tql
│   ├── SKILL.md / USAGE.md
│   ├── pyproject.toml / uv.lock
│   └── dashboard/       empty dir for future browser UI
├── infra/dismech/       ← plugin wrapper files (rarely change)
│   ├── alhazen_core.py  TypeDB lifecycle (start, init, load schema)
│   ├── plugin.json      Plugin manifest + SessionStart hook reference
│   └── hooks.json       SessionStart hook definition
└── plugins/dismech/     ← AUTO-BUILT by CI — do not edit by hand
    ├── .claude-plugin/
    ├── hooks/
    └── skills/dismech/  (skills/ + infra/ merged here)
```

`plugins/dismech/` is assembled automatically by the
[build-plugin workflow](.github/workflows/build-plugin.yml) whenever
`skills/dismech/` or `infra/dismech/` changes on `main`. Alhazen points
at the `plugins/dismech/` path to load the skill.

## Development Notes

For Claude Code agent-specific notes (command invocations, TypeDB 3.x driver
quirks, schema regeneration), see [`CLAUDE.md`](CLAUDE.md).

---

## Requirements

- Docker
- Python ≥ 3.11, < 3.14 (3.12 recommended; `typedb-driver` segfaults on 3.14)
- [uv](https://docs.astral.sh/uv/) — handles virtual environment and dependencies

Python dependencies (`typedb-driver`, `pyyaml`, `tqdm`, `requests`) are declared
in `plugins/dismech/skills/dismech/pyproject.toml` and installed automatically.

---

## License

Apache-2.0. See [LICENSE](LICENSE).

Copyright SciKnow.io and contributors, 2025.
