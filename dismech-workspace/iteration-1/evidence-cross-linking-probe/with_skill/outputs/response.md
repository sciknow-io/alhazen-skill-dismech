# Evidence Cross-Linking: ACVR1 Inhibitor Paper + FOP in DisMech + Alhazen Notebook

## What I Did

I read the DisMech SKILL.md and USAGE.md, examined the full TypeQL schema, queried the live DisMech database for FOP, and checked the Alhazen notebook (`alhazen_notebook`) for any existing papers. Here is an honest account of what is possible, what is not, and how to proceed.

---

## Step 1: The FOP Entry in DisMech Is Real and Relevant

FOP (Fibrodysplasia Ossificans Progressiva) exists in the DisMech database as `"Fibrodysplasia Ossificans Progressiva"` (category: Genetic, parents: Genetic Disease, Musculoskeletal Disease).

The current entry has five pathophysiology mechanisms already curated:

1. **Constitutive BMP Signaling Activation** — ACVR1 R206H mutation creates pH-sensitive switch causing ligand-independent BMP activation and inappropriate osteogenic differentiation.
2. **Impaired FKBP1A Regulatory Binding** — R206H reduces FKBP1A/FKBP12 binding, releasing a key safeguard against inappropriate BMP signaling.
3. **Activin A Neomorphic Signaling** — ACVR1 R206H renders the receptor responsive to Activin A (normally an antagonist), driving heterotopic ossification. Anti-Activin A antibodies can block HO.
4. **Heterotopic Ossification** — Progressive extraskeletal bone formation following inflammatory flare-ups, proceeding through endochondral ossification phases.
5. **Inflammatory Triggering of Flare-ups** — Macrophage/mast cell infiltration during the catabolic phase creates a permissive microenvironment for HO.

**ACVR1 is not yet searchable by name** (the `search` command returned 0 results for "ACVR1"), but it appears embedded in the mechanism descriptions. The mechanisms are stored in a `pathophysiology` entity that holds only `name` and `description` as plain text — gene symbols are not normalized to separate `genedescriptor` entities in the current ingested data.

---

## Step 2: How to Add PubMed Evidence to a DisMech Disease Record

### What the Schema Supports

The DisMech schema has a purpose-built `evidenceitem` entity:

```typeql
entity evidenceitem,
    owns reference,        # e.g. "PMID:39876543"
    owns reference-title,  # paper title
    owns supports,         # WRONG_STATEMENT | SUPPORT | REFUTE | NO_EVIDENCE | PARTIAL
    owns evidence-source,  # HUMAN_CLINICAL | MODEL_ORGANISM | IN_VITRO | COMPUTATIONAL | OTHER
    owns snippet,          # quoted supporting passage
    owns explanation,      # your interpretive note
    plays evidence:evidenceitem,
    plays literature-evidence:evidenceitem;
```

The `evidence` relation connects an `evidenceitem` to many entity types in DisMech, including `pathophysiology`, `disease`, `phenotype`, `genetic`, `clinicaltrial`, etc.

There is also a `publicationreference` entity with a `reference @key` that can be attached to a `disease` via the `references` relation.

### What Is NOT Supported by the CLI Today

**The `dismech.py` CLI has no `add-evidence` or `insert-evidence` command.** The commands currently available are:

- `init` — initialize the database
- `ingest` — bulk-load YAML disorder files
- `list-diseases` — list disease names
- `show-disease` — show disease + mechanisms (name + description only)
- `search` — substring search over names/mechanisms
- `stats` — count entities
- `serve` — start the dashboard

To add evidence, you must write TypeQL directly or extend the CLI. Here is the TypeQL to insert an evidence item linked to the FOP pathophysiology mechanism for ACVR1 inhibition:

```typeql
# Step 1: Insert the evidenceitem
insert
  $ev isa evidenceitem,
    has reference "PMID:XXXXXXXX",
    has reference-title "Title of your 2024 ACVR1 inhibitor paper",
    has supports "SUPPORT",
    has evidence-source "HUMAN_CLINICAL",
    has snippet "Paste the key sentence from the abstract here",
    has explanation "This paper provides direct evidence that ACVR1 inhibition reduces HO in FOP patients.";
```

```typeql
# Step 2: Link it to the relevant pathophysiology mechanism
match
  $path isa pathophysiology, has name "Constitutive BMP Signaling Activation";
  $ev isa evidenceitem, has reference "PMID:XXXXXXXX";
insert
  (pathophysiology: $path, evidence: $ev) isa evidence;
```

```typeql
# Step 3 (optional): Also link to the disease entity directly
match
  $d isa disease, has name "Fibrodysplasia Ossificans Progressiva";
  $ev isa evidenceitem, has reference "PMID:XXXXXXXX";
insert
  (disease: $d, evidence: $ev) isa evidence;
```

Run these via the TypeDB Python driver targeting `TYPEDB_DATABASE=dismech`, or via the TypeDB Studio UI at `localhost:1729`.

---

## Step 3: Cross-Linking to Alhazen Notebook — What Is and Is Not Possible

### The Core Architectural Constraint

DisMech runs in TypeDB database `dismech`. Alhazen Notebook runs in TypeDB database `alhazen_notebook`. **These are separate TypeDB databases sharing the same TypeDB server instance (port 1729), but TypeDB does not support cross-database joins or references.** There is no foreign-key-style mechanism to link an `evidenceitem` in `dismech` to a `scilit-paper` in `alhazen_notebook`.

### What the Alhazen Notebook Contains

I checked the `alhazen_notebook` database. It currently contains no FOP-related papers (keyword search for "FOP" returned 0 results). The notebook has papers on unrelated topics (AlphaFold, LLM benchmarks, etc.).

### Three Strategies for Cross-Linking

**Strategy A: Shared identifier as a soft link (recommended, works today)**

Both systems can store a PubMed ID as a string. In DisMech:
- `evidenceitem.reference = "PMID:XXXXXXXX"`
- `publicationreference.reference = "PMID:XXXXXXXX"` (with `@key`, so queryable)

In Alhazen Notebook, after ingesting the paper via `scientific_literature.py ingest --pmid XXXXXXXX`:
- The paper is stored as a `scilit-paper` with `doi` and identifiers including the PMID.

The link is not enforced by either database, but you can manually look up a PMID in both systems and treat it as a shared identifier. This is the most pragmatic approach given current tooling.

**Strategy B: Note in Alhazen Notebook referencing DisMech**

Use `typedb_notebook.py insert-note` to add an annotation note to the paper in `alhazen_notebook`:

```bash
uv run python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
  --subject-id "paper-XXXXXXXXXXXX" \
  --content "This paper supports the 'Constitutive BMP Signaling Activation' mechanism in the DisMech FOP entry (Fibrodysplasia Ossificans Progressiva). The DisMech entry is stored in the separate TypeDB 'dismech' database. Key finding: [your summary]."
```

This stores your interpretive linkage as text in `alhazen_notebook`. It's not machine-queryable across databases, but it is human-readable and searchable.

**Strategy C: Add a `dismech-cross-ref` note to DisMech evidenceitem (future design)**

The DisMech `evidenceitem` has a free-text `explanation` field. You could store the Alhazen paper ID there:

```
explanation: "SUPPORT — ACVR1 R206H inhibition reduces HO. Cross-ref: alhazen_notebook paper-XXXXXXXXXXXX"
```

This is a string-embedded reference, not a live link, but it preserves the connection for a human (or a future script) to follow up.

---

## Step 4: Recommended Workflow for Your 2024 ACVR1 Paper

Here is the complete workflow assuming your paper has PMID `XXXXXXXX` (replace with actual):

### A. Ingest the paper into Alhazen Notebook

```bash
cd /Users/gullyburns/skillful-alhazen
uv run python .claude/skills/scientific-literature/scientific_literature.py ingest \
  --pmid XXXXXXXX
```

Note the returned paper ID (e.g., `paper-abc123def456`).

### B. Add the evidence to DisMech (requires TypeDB Python script or Studio)

There is no CLI command for this today. You need to run the TypeQL insert statements shown in Step 2 above. The most practical path is to write a small Python script:

```python
from typedb.driver import TypeDB, Credentials, DriverOptions, TransactionType

driver = TypeDB.driver(
    "localhost:1729",
    Credentials("admin", "password"),
    DriverOptions(is_tls_enabled=False),
)

with driver.transaction("dismech", TransactionType.WRITE) as tx:
    tx.query("""
        insert
          $ev isa evidenceitem,
            has reference "PMID:XXXXXXXX",
            has reference-title "Your 2024 ACVR1 Inhibitor Paper Title",
            has supports "SUPPORT",
            has evidence-source "HUMAN_CLINICAL",
            has snippet "Key quote from abstract",
            has explanation "Alhazen notebook cross-ref: paper-abc123def456";
    """).resolve()
    tx.commit()

with driver.transaction("dismech", TransactionType.WRITE) as tx:
    tx.query("""
        match
          $path isa pathophysiology, has name "Constitutive BMP Signaling Activation";
          $ev isa evidenceitem, has reference "PMID:XXXXXXXX";
        insert
          (pathophysiology: $path, evidence: $ev) isa evidence;
    """).resolve()
    tx.commit()
```

### C. Add a cross-reference note in Alhazen Notebook

```bash
uv run python .claude/skills/typedb-notebook/typedb_notebook.py insert-note \
  --subject-id "paper-abc123def456" \
  --content "DisMech cross-reference: This paper supports the 'Constitutive BMP Signaling Activation' and potentially the 'Activin A Neomorphic Signaling' mechanisms in the DisMech FOP entry ('Fibrodysplasia Ossificans Progressiva', dismech database). The ACVR1 inhibitor approach targets the neomorphic gain-of-function that allows Activin A to drive HO. PMID: XXXXXXXX."
```

---

## Honest Assessment: What Is Missing

| Gap | Severity | Notes |
|-----|----------|-------|
| No `add-evidence` CLI command in `dismech.py` | Moderate | The schema is ready; the CLI just doesn't expose it |
| No cross-database linking in TypeDB | Architectural | Two separate databases; PMID string is the only shared key |
| `evidenceitem.reference` has no enforced format | Minor | Could be PMID, DOI, or free text — no validation |
| `show-disease` output does not include evidenceitems | Moderate | The CLI only shows mechanisms; existing evidence is not surfaced |
| No `ingest-evidence` from PubMed metadata | Moderate | Would be a valuable addition — auto-populate `reference-title` etc. from PubMed API |
| ACVR1 not indexed as a `genedescriptor` | Minor | Mechanisms reference it in text but it is not a first-class queryable entity |

---

## Summary

- FOP is in DisMech with 5 curated ACVR1-related mechanisms.
- The DisMech schema fully supports `evidenceitem` with PubMed IDs, support status, and evidence source.
- **No CLI command exists to add evidence today** — you must write TypeQL directly.
- Cross-linking to `alhazen_notebook` is architecturally constrained (separate TypeDB databases, no cross-DB joins). The practical workaround is storing the PMID in DisMech's `evidenceitem.reference` and the Alhazen paper ID in `evidenceitem.explanation`, plus a note in the Alhazen notebook pointing back to DisMech.
- Filing a gap issue for an `add-evidence` CLI command would close the most actionable missing piece.
