# Annotation and Collection Features in the Alhazen Knowledge Graph

## Task Overview

The user wants to:
- (a) Write a short research note and attach it to the Marfan syndrome disease record
- (b) Create a named collection containing all connective tissue disorders from DisMech

Neither DisMech nor an Alhazen notebook instance is accessible here. The following explains what these operations require in terms of knowledge graph structure, drawing on the Alhazen schema as the concrete reference system.

---

## Part A: Attaching a Research Note to a Disease Record

### What is needed

To annotate a disease record with a note, a knowledge graph system requires at minimum:

1. **An entity representing the disease** — something like a `domain-thing` subtype (e.g., `dismech-disease`) with a stable unique identifier (e.g., MONDO ID or OMIM accession). In Alhazen's schema, any `identifiable-entity` can play the `aboutness:subject` role, so any entity type in the graph can receive notes.

2. **A `note` entity type** — a first-class content-bearing entity that stores the text of the annotation. In Alhazen, `note` is a subtype of `information-content-entity` and owns `content`, `format`, `confidence`, `created-at`, `provenance`, etc. This is distinct from a raw artifact: a note is researcher-generated synthesis, not captured source material.

3. **An `aboutness` relation** — the semantic link between the note and the disease entity. In Alhazen this is modeled as:
   ```
   relation aboutness,
       relates note,
       relates subject;
   ```
   A `note` entity plays `aboutness:note`, and the target disease entity plays `aboutness:subject`.

4. **Provenance tracking** — to record who wrote the note, when, and optionally with what model or tool. Alhazen provides `provenance-record` for this, and the `note` entity inherits `provenance`, `created-at`, and `source-uri` from `identifiable-entity`.

### What the operation looks like conceptually

```
INSERT note
    content: "Marfan syndrome is caused by FBN1 mutations affecting fibrillin-1 ..."
    format: "text/markdown"
    created-at: <now>
    provenance: "user-review-2026-04-15"

LINK note -> marfan-syndrome-entity
    via aboutness relation
```

### What is missing without a DisMech skill

Without a `dismech-disease` entity already in the graph (inserted by a DisMech ingestion skill), there is no subject to attach the note to. The note creation itself is generic and could be done with the `typedb-notebook` core skill's insert capabilities, but the disease entity must first exist. A DisMech skill would need to:
- Ingest disease records from DisMech into TypeDB as `dismech-disease` entities
- Expose a command like `insert-note --disease-id MONDO:0007947 --content "..."` that creates the note and the `aboutness` relation in a single transaction

---

## Part B: Creating a Named Collection of Connective Tissue Disorders

### What is needed

1. **A `collection` entity** — Alhazen's schema has a first-class `collection` type that owns `name`, `description`, `logical-query`, and `is-extensional`. A named collection for connective tissue disorders would be inserted as a `collection` entity with an appropriate name and description.

2. **`collection-membership` relations** — each disease entity to be tracked is linked to the collection via:
   ```
   relation collection-membership,
       owns created-at,
       owns provenance,
       relates collection,
       relates member;
   ```
   Any `identifiable-entity` (including `domain-thing` subtypes like `dismech-disease`) plays `collection-membership:member`.

3. **A way to enumerate the relevant diseases** — either:
   - **Extensional**: the researcher explicitly selects which diseases belong (stores specific `collection-membership` relations). `is-extensional: true`.
   - **Intensional**: the collection is defined by a query — e.g., "all diseases in DisMech classified as connective tissue disorders." `logical-query` stores the TypeQL query string; membership is computed at read time. `is-extensional: false`.

4. **The disease entities must already exist in the graph** — same dependency as Part A. Without DisMech ingestion, there are no `dismech-disease` entities to add to the collection.

### What the operation looks like conceptually

```
INSERT collection
    name: "Connective Tissue Disorders (DisMech)"
    description: "All connective tissue disorders indexed in DisMech as of 2026-04-15"
    is-extensional: true
    created-at: <now>

FOR EACH disease in DisMech classified as connective tissue disorder:
    INSERT collection-membership
        collection: <collection above>
        member: <dismech-disease entity>
        created-at: <now>
        provenance: "dismech-curation-2026-04-15"
```

Alternatively, if the collection is kept intensional:
```
INSERT collection
    name: "Connective Tissue Disorders (DisMech)"
    logical-query: "match $d isa dismech-disease, has disease-category 'connective-tissue-disorder'; fetch { 'id': $d.id, 'name': $d.name };"
    is-extensional: false
```

---

## Summary: What a DisMech Skill Would Need to Provide

| Capability | Required for | Schema element in Alhazen |
|---|---|---|
| Ingest disease records from DisMech | Both A and B | `dismech-disease sub domain-thing` entity type + `schema.tql` |
| Insert a note with free-text content | Part A | `note` entity (already exists in core schema) |
| Link a note to a disease | Part A | `aboutness` relation (already exists in core schema) |
| Create a named collection | Part B | `collection` entity (already exists in core schema) |
| Add diseases to a collection | Part B | `collection-membership` relation (already exists in core schema) |
| Classify diseases by category | Part B (intensional) | `classification` relation + `vocabulary-type` for disease categories |

The Alhazen core schema already has all the infrastructure needed for annotation and collection. The gap is a `dismech` namespace skill that defines `dismech-disease` (and any disease-specific attributes like MONDO IDs, inheritance modes, mechanism annotations) and provides CLI commands to ingest, annotate, and organize DisMech records.
