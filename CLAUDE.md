# Claude Code Notes for alhazen-skill-dismech

## Project Overview

This is a self-contained [Alhazen](https://github.com/sciknow/alhazen) skill plugin
that ingests the [DisMech](https://github.com/sciknow-io/dismech) disease mechanism
knowledge base into a TypeDB 3.x graph database and exposes CLI commands + a web
dashboard for browsing and querying the data.

---

## Commands

Always use `--python 3.12`. The `typedb-driver` package segfaults on Python 3.14.

```bash
SKILL=plugins/dismech/skills/dismech

# Initialize TypeDB database + load schema
uv run --project $SKILL --python 3.12 python $SKILL/alhazen_core.py init

# Ingest all disorder YAMLs (requires a local copy of the dismech kb)
uv run --project $SKILL --python 3.12 python $SKILL/dismech.py ingest \
  --source /path/to/dismech/kb/disorders

# Quick smoke test (5 files)
uv run --project $SKILL --python 3.12 python $SKILL/dismech.py ingest \
  --source /path/to/dismech/kb/disorders --max 5

# Queries
uv run --project $SKILL --python 3.12 python $SKILL/dismech.py stats
uv run --project $SKILL --python 3.12 python $SKILL/dismech.py show-disease --name "Achondroplasia"
uv run --project $SKILL --python 3.12 python $SKILL/dismech.py search --query "FGFR3"
uv run --project $SKILL --python 3.12 python $SKILL/dismech.py list-diseases --category Mendelian

# Reset database (destroys all data)
uv run --project $SKILL --python 3.12 python $SKILL/alhazen_core.py reset --yes

# Dashboard
uv run --project $SKILL --python 3.12 python $SKILL/dismech.py serve --port 7777
```

Makefile wraps the common commands — see `make help` or read `Makefile` directly.

---

## Repository Structure

```
alhazen-skill-dismech/
├── CLAUDE.md
├── .gitignore
├── LICENSE                          Apache-2.0
├── Makefile                         init / ingest / serve / stats / demo targets
├── README.md
├── .claude-plugin/
│   └── marketplace.json             Repo-level plugin catalog
└── plugins/dismech/                 The plugin bundle
    ├── .claude-plugin/
    │   └── plugin.json              Plugin manifest (name, version, skills path)
    ├── hooks/
    │   └── hooks.json               SessionStart: runs alhazen_core.py init
    └── skills/dismech/
        ├── SKILL.md                 Alhazen trigger phrases + quick start
        ├── USAGE.md                 Full CLI reference
        ├── alhazen_core.py          TypeDB lifecycle: start, init DB, load schema
        ├── dismech.py               CLI: ingest + 5 query commands + serve
        ├── schema.tql               Pre-generated TypeQL schema (from LinkML)
        ├── pyproject.toml           typedb-driver, pyyaml, tqdm, requests
        ├── uv.lock
        └── dashboard/
            └── index.html           Single-page Bootstrap 5 dashboard
```

---

## TypeDB 3.x — Critical Patterns

These patterns are non-obvious and were worked out by trial and error.

### Fetch results are plain dicts with string values

TypeDB 3.x fetch queries return Python `dict` objects where values are **plain strings**
(not `{"value": "..."}` nested dicts as in older driver versions):

```python
# Query:
results = list(tx.query('match $d isa disease, has name $n; fetch {"n": $n};').resolve())

# Result structure (each row is a dict):
results[0]   # -> {'n': 'Achondroplasia'}
results[0]["n"]  # -> 'Achondroplasia'  (plain string, NOT {'value': 'Achondroplasia'})
```

### Dot-notation attribute fetch does NOT work

`fetch {"name": $d.name}` produces empty results — TypeDB 3.x requires explicit
attribute variable binding:

```python
# WRONG — returns empty results:
tx.query('match $d isa disease, has name "Achondroplasia"; fetch {"name": $d.name};')

# RIGHT — bind attribute to a variable:
tx.query('match $d isa disease, has name "Achondroplasia", has category $cat; fetch {"cat": $cat};')
```

### Reduce count returns a `_ConceptRow`, not a subscriptable dict

```python
results = list(tx.query('match $e isa disease, has name $n; reduce $c = count;').resolve())

# WRONG — raises TypeError:
results[0]["c"]

# RIGHT:
results[0].get("c").get_integer()   # -> int
```

The `_count_query()` helper in `dismech.py` wraps this pattern.

### Fetching entity variables is not supported

`fetch {"d": $d}` raises `[FEX5] Fetching entities is not supported`.
Always fetch attributes, not entity variables.

---

## Schema Notes

`schema.tql` was generated from the LinkML `dismech.yaml` model via:

```bash
uv run gen-typedb dismech.yaml
```

**Key entity types and their primary attributes:**

| Entity | Primary attribute | Notes |
|--------|------------------|-------|
| `disease` | `name @key` | Only entity with `@key` on name |
| `pathophysiology` | `name` | No `@key` — same name can appear across many diseases |
| `diseasedescriptor` | `preferred-term` | Subtype of `descriptor`; does NOT own `name` |

The `@key` annotation was removed from `owns name` on all entity types **except**
`disease`. The original generated schema had `@key` on all 29 entity types (because
LinkML `identifier: true` propagates via inheritance), which caused insert failures
when any mechanism name — e.g., "Inflammation" — appeared in more than one disease.

**Key relations:**

| Relation | Roles | Meaning |
|----------|-------|---------|
| `disease-term` | `disease`, `diseasedescriptor` | Links disease to MONDO/OMIM term |
| `pathophysiology-rel` | `disease`, `pathophysiology` | Links disease to mechanism entries |

---

## Ingestion Architecture

`_ingest_disease_file(driver, data)` inserts three tiers per disorder YAML:

1. **Disease entity** — one WRITE transaction inserting `name`, `category`,
   `parents` (multi-valued), `synonyms` (multi-valued)
2. **Disease term** — MATCH the disease entity, INSERT a `diseasedescriptor` entity
   and a `disease-term` relation; skipped if `disease_term` key is absent from YAML
3. **Pathophysiology mechanisms** — for each entry in `data["pathophysiology"]`,
   MATCH the disease entity, INSERT a `pathophysiology` entity and a
   `pathophysiology-rel` relation

Each tier is a separate transaction. Errors per file are caught, counted, and
reported at the end; a partial failure does not abort the whole batch.

**Performance:** 605 disorders with 2770 mechanisms ingest in ~19 seconds on a
local TypeDB container (≈ 32 files/second).

---

## Python Version

`typedb-driver >= 3.8.0` **segfaults on Python 3.14** (the current Homebrew default).
Always invoke with `--python 3.12`. The `pyproject.toml` pins `requires-python = ">=3.11,<3.14"`.

---

## Schema Regeneration

If the LinkML `dismech.yaml` schema changes, regenerate `schema.tql` in a
linkml workspace:

```bash
cd /path/to/linkml
uv run gen-typedb /path/to/dismech/src/dismech/schema/dismech.yaml > \
  /path/to/alhazen-skill-dismech/plugins/dismech/skills/dismech/schema.tql
```

After regeneration, review the output for `@key` annotations and remove them from
all `owns name` lines **except** the `disease` entity (line search: `owns name @key`).
