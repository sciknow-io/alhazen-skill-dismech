# Annotation and Collection Probe — DisMech Skill

**Date:** 2026-04-15
**Task:** Attach a research note to Marfan Syndrome in the knowledge graph; create a named collection of connective tissue disorders.
**Databases available:** `dismech` (DisMech knowledge graph), `alhazen_notebook` (Alhazen researcher notebook)

---

## Disease Lookup

Marfan Syndrome exists in the `dismech` database under the name `"Marfan Syndrome"` (case-sensitive; `"Marfan syndrome"` returns not-found). It belongs to the `"Connective Tissue Disorder"` parent category and has 6 curated pathophysiology mechanisms:

1. **FBN1 Gene Mutation** — defective fibrillin-1 affects elasticity and strength of connective tissue
2. **Dysregulated TGF-beta Signaling** — increased TGF-beta bioavailability drives SMAD2/3 signaling, vascular smooth muscle phenotypic switching, and ECM remodeling
3. **Extracellular Matrix Remodeling** — elevated MMPs, elastic fiber fragmentation, altered collagen and proteoglycan (versican) accumulation weaken the aortic medial wall
4. **Impaired Mechanotransduction** — perturbed integrin-fibrillin interactions alter focal adhesion signaling and vascular response to hemodynamic stress
5. **Vascular Inflammation** — widespread inflammation of medium-sized arteries including coronary arteries
6. **Mitochondrial Dysfunction** — arsenic-induced mechanism (likely mis-curated entry for this disease)

---

## Operation (a): Attach a Research Note to Marfan Syndrome

### What was attempted

A TypeQL insert query was issued against the `dismech` database targeting the `note` entity type and `aboutness` relation:

```typeql
match $d isa disease, has name "Marfan Syndrome";
insert $n isa note, has content "...";
(note: $n, subject: $d) isa aboutness;
```

### Result: FAILED

**TypeDB error:**
```
[INF2] Type label 'note' not found.
Caused: [QUA1] Type inference error while compiling query annotations.
Near 3:23
-->  insert $n isa note, has content "...";
                   ^
```

### Why it fails

The `dismech` TypeQL schema (generated from the DisMech LinkML schema) defines no `note` entity type and no `aboutness` relation. The schema's entity hierarchy (`disease`, `descriptor` subtypes, `mechanism`, `dataset`, etc.) is a read-only curated knowledge graph — it has no annotation layer. There is nowhere in the `dismech` database to store free-text researcher notes attached to disease records.

The relevant schema excerpt confirms the `disease` entity's `plays` clauses include no annotation-related roles. The `aboutness` relation is defined only in the `alhazen_notebook` schema, in a separate database.

### Alternative attempted: alhazen_notebook note

A note was inserted into the `alhazen_notebook` database using the `typedb-notebook` skill's `insert-note` command with `--subject "marfan-syndrome-dismech"`:

```
{"success": true, "note_id": "note-9062403960d4", "subject": "marfan-syndrome-dismech"}
```

**However**, this is a **silent partial failure**. The `insert-note` command:
1. Inserts the `note` entity into `alhazen_notebook` — this succeeds.
2. Attempts to create the `aboutness` relation by matching `$s isa identifiable-entity, has id "marfan-syndrome-dismech"` — this matches zero rows (there is no entity with that ID in `alhazen_notebook`), but the transaction commits silently without error.
3. The note is a **floating orphan** — it has no `aboutness` link to any subject entity.

**Verified:** A `query-notes --subject "marfan-syndrome-dismech"` call returns `"count": 0`. The note exists in `alhazen_notebook` (confirmed by direct TypeQL query) but is not attached to anything.

### Root cause summary for operation (a)

| Database | `note` type | `aboutness` relation | Disease entity present | Result |
|---|---|---|---|---|
| `dismech` | Missing | Missing | Yes (`Marfan Syndrome`) | Hard TypeQL error [INF2] |
| `alhazen_notebook` | Present | Present | No (not mirrored) | Silent orphan — note created but unlinked |

**To correctly attach a note to a DisMech disease record**, one of the following schema extensions is needed:
- **Option A (dismech-native):** Add `entity note, owns content; relation aboutness, relates note, relates subject; entity disease plays aboutness:subject;` to the `dismech` schema.
- **Option B (cross-database bridge):** Mirror `dismech` disease entities into `alhazen_notebook` (e.g., as `domain-thing` entities with a `dismech-id` attribute), then use `aboutness` in `alhazen_notebook` to attach notes to the mirrored entities.

---

## Operation (b): Create a Named Collection of Connective Tissue Disorders

### What was attempted — dismech database

**Step 1:** Queried for all diseases with a "Connective" parent (case-insensitive substring on the `parents` attribute). Found **10 diseases**:

| Disease Name | Parent (as stored) |
|---|---|
| ALDH18A1-Related Autosomal Dominant Cutis Laxa Type 3 | Connective Tissue Disease |
| Ehlers-Danlos Syndrome | Connective Tissue Disorder |
| Loeys-Dietz Syndrome | Connective Tissue Disorders |
| Marfan Syndrome | Connective Tissue Disorder |
| Menkes Disease | Connective tissue disorder |
| Mixed Connective Tissue Disease | Connective Tissue Disease |
| Penttinen_Premature_Aging_Syndrome | Connective Tissue Disorder |
| Shprintzen-Goldberg Syndrome | Connective Tissue Disorders |
| Spondylodysplastic Ehlers-Danlos Syndrome | Connective Tissue Disorder |
| Systemic Sclerosis | Connective Tissue Disease |

Note: The parent strings are inconsistently cased and pluralized in the data (`"Connective Tissue Disorder"`, `"Connective Tissue Disorders"`, `"Connective Tissue Disease"`, `"Connective tissue disorder"`). This is a data quality issue.

**Step 2:** Attempted to create a named `diseasecollection` in `dismech`:

```typeql
insert $c isa diseasecollection, has name "Connective Tissue Disorders";
```

**Result: FAILED**

**TypeDB error:**
```
[INF11] Type-inference was unable to find compatible types for the pair of variables
'c' & '_anonymous' across a 'has' constraint.
- c: [diseasecollection]
- _anonymous: [name]
Near 2:42
-->  insert $c isa diseasecollection, has name "Connective Tissue Disorders";
                                      ^
```

**Why it fails:** The `diseasecollection` entity is defined in the schema as:

```typeql
entity diseasecollection,
    plays diseases:diseasecollection;
```

It has **no owned attributes** — no `name`, no `id`, no `description`. It exists solely as a structural grouping node in the `diseases` relation. A collection cannot be named, identified, or queried by label.

**Step 3:** An **unnamed** `diseasecollection` with `diseases` relations to all matching disease entities was successfully inserted:

```typeql
match $d isa disease, has name $n, has parents $p;
$p contains "Connective";
insert $c isa diseasecollection; (diseasecollection: $c, disease: $d) isa diseases;
```

This succeeded but creates an anonymous grouping that cannot be retrieved by name or ID.

### What was attempted — alhazen_notebook database

A named collection was created using the `typedb-notebook` skill:

```bash
uv run python typedb_notebook.py insert-collection \
  --name "Connective Tissue Disorders" \
  --description "Named collection of connective tissue disorders from DisMech"
```

**Result: SUCCESS**

```json
{"success": true, "collection_id": "collection-7351a9a8ae11", "name": "Connective Tissue Disorders"}
```

The collection exists in `alhazen_notebook` with ID `collection-7351a9a8ae11`. However, it is an **empty shell** — it contains no disease entities because `alhazen_notebook` does not hold DisMech disease records. To populate it, DisMech disease entities would need to be mirrored into `alhazen_notebook` as `domain-thing` instances and then linked to the collection via the `membership` relation.

### Root cause summary for operation (b)

| Database | Collection type | `name` attribute | Can hold disease members | Result |
|---|---|---|---|---|
| `dismech` | `diseasecollection` exists | Missing | Yes (via `diseases` relation) | Unnamed anonymous group only |
| `alhazen_notebook` | `collection` exists | Present (`name @key`) | No (no DisMech diseases mirrored) | Named collection created, but empty |

**To correctly create a named, populated collection of DisMech connective tissue disorders**, one of the following is needed:
- **Option A (dismech-native):** Add `owns name;` (and optionally `owns id @key;`) to the `diseasecollection` entity in the `dismech` schema.
- **Option B (cross-database):** Mirror DisMech diseases into `alhazen_notebook` as `domain-thing` entities and add them to the `"Connective Tissue Disorders"` collection via the `membership` relation.

---

## Summary

| Operation | In `dismech` | In `alhazen_notebook` | Blocker |
|---|---|---|---|
| (a) Attach note to Marfan Syndrome | Hard fail — `note` type missing, `aboutness` relation missing | Silent fail — note created as orphan, no `aboutness` link (no mirrored entity to link to) | Schema gap in `dismech`; no entity mirror in `alhazen_notebook` |
| (b) Create named collection of connective tissue disorders | Hard fail — `diseasecollection` has no `name` attribute | Partial success — named collection `collection-7351a9a8ae11` created, but empty (no mirrored diseases) | `diseasecollection` lacks `name`; no entity mirror in `alhazen_notebook` |

**Connective tissue disorders found in DisMech:** 10 diseases across parent strings `"Connective Tissue Disorder"`, `"Connective Tissue Disorders"`, and `"Connective Tissue Disease"` (inconsistent naming in source data).

**Current state of alhazen_notebook after probing:**
- Note `note-9062403960d4` ("Marfan Syndrome research note") inserted but orphaned — should be cleaned up.
- Collection `collection-7351a9a8ae11` ("Connective Tissue Disorders") created — useful as a placeholder if diseases are later mirrored.
