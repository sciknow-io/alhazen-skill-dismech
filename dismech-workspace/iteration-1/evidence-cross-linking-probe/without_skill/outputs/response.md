# Evidence Cross-Linking: ACVR1 Inhibitor Paper -> DisMech + Alhazen Notebook

## Honest Scope Declaration

I do not have live access to DisMech or to your Alhazen notebook. The answer below describes what would typically be required based on general knowledge of knowledge graph design, the Alhazen notebook data model (which I can read from the codebase), and what DisMech is understood to do as a disease-mechanism database. No actual linking has been performed.

---

## What You Are Trying to Do

You have three pieces of evidence that belong together:

1. A 2024 paper on ACVR1 inhibitors for fibrodysplasia ossificans progressiva (FOP) treatment.
2. An entry for FOP in DisMech — a structured database of disease mechanisms.
3. A record of that paper already stored in your Alhazen notebook as a `domain-thing` (e.g., a `scilit-paper` entity) with associated `artifact`, `fragment`, and `note` entities.

You want to create a cross-reference so that the evidence in the paper is explicitly connected to the disease mechanism record in DisMech, and to the paper record in Alhazen.

---

## What Would Be Needed in DisMech

DisMech is (as I understand it) a structured database of disease mechanisms — likely organized around disease entries with associated molecular actors, pathway steps, and evidence citations. To connect the paper to the FOP entry, you would typically need:

1. **The FOP entry identifier in DisMech** — for example, a MONDO ID (e.g., `MONDO:0008289`) or a DisMech-internal disease ID.
2. **The paper identifier** — a DOI, PubMed ID (PMID), or bioRxiv ID.
3. **The specific mechanism claim** being evidenced — e.g., "ACVR1 (ALK2) kinase inhibition suppresses heterotopic ossification in FOP" — and the DisMech field it maps to (e.g., a pathway node, a therapeutic target, a molecular evidence slot).
4. **An evidence link** — DisMech presumably has a mechanism for associating papers with specific mechanistic claims. Without a DisMech API or write interface, this step requires either:
   - Manual curation through a DisMech submission/annotation form, or
   - Programmatic access via a DisMech curator API (if one exists), submitting a structured evidence record (paper ID + mechanism slot + assertion type + confidence).

**Without a DisMech skill or API integration in Alhazen, this half of the linking cannot happen automatically.** A DisMech skill would need to encapsulate: the DisMech data model, the API endpoints for reading disease entries and writing evidence links, and TypeDB schema extensions to mirror DisMech entities locally.

---

## What Would Be Needed in Alhazen

The Alhazen notebook has the infrastructure to connect papers to claims via its core schema:

- The paper is stored as a `domain-thing` (likely a `scilit-paper` entity with `id`, `name`, `source-uri`, `provenance`).
- Associated content is stored as `artifact` (PDF or HTML) and `fragment` (extracted passages) entities.
- Analysis is stored as `note` entities, linked to the paper via `(note: $n, subject: $paper) isa aboutness`.

To connect the paper to FOP-mechanism evidence, you would:

1. **Retrieve the paper entity** — query by DOI, PMID, or stored `id`.
2. **Create or locate a `note`** summarizing the ACVR1-inhibition evidence claim from the paper. If you have already annotated the paper, this note may already exist.
3. **Create a `domain-thing` representing the DisMech FOP entry** — for example, a new entity subtype (e.g., `dismech-entry sub domain-thing`) with the DisMech entry IRI or MONDO ID as its `iri` attribute. Without a DisMech skill, this would be a stub record.
4. **Link the note as evidence about both entities** using the `aboutness` relation:
   - `(note: $n, subject: $paper) isa aboutness` — note is about the paper.
   - `(note: $n, subject: $dismech_entry) isa aboutness` — same note is also about the DisMech FOP entry.
5. **Optionally use the `evidence-chain` relation** (already in the schema) to express that the note serves as evidence for a specific claim: `(claim: $claim_note, evidence: $evidence_note) isa evidence-chain`.

The `semantic-triple` relation in the schema is also relevant here — it allows expressing structured assertions like "ACVR1 inhibitor X reduces heterotopic ossification in FOP model" as a subject-predicate-object triple linked to both the paper and the DisMech entry.

---

## The Missing Piece: A DisMech Skill

The key gap is that Alhazen does not currently have a DisMech skill. A DisMech skill would need to:

1. Define a TypeDB schema extension — `dismech-entry`, `dismech-mechanism`, `dismech-pathway-step` as `domain-thing` subtypes — mirroring DisMech's data model.
2. Implement commands to fetch FOP (and other disease) entries from DisMech via its API.
3. Implement commands to link Alhazen `note` or `fragment` entities to DisMech mechanism records as evidence.
4. Possibly implement a write-back to DisMech if it has a curator API.

Without this skill, the workflow requires manual bridging: you record the connection as a note in Alhazen and maintain a separate, manually curated link to DisMech outside the notebook.

---

## Summary of Steps (With Full Integration)

| Step | Where | What |
|------|--------|------|
| 1. Find the paper in Alhazen | Alhazen / TypeDB | Query `scilit-paper` by DOI or PMID |
| 2. Retrieve or create the evidence note | Alhazen / TypeDB | `note` entity about ACVR1-inhibition claim, linked via `aboutness` |
| 3. Fetch the FOP DisMech entry | DisMech skill (needed) | Pull entry by MONDO ID; store as `dismech-entry` in TypeDB |
| 4. Link the note to the DisMech entry | Alhazen / TypeDB | `(note: $n, subject: $dismech_entry) isa aboutness` |
| 5. Link the note to the paper | Alhazen / TypeDB | `(note: $n, subject: $paper) isa aboutness` |
| 6. Optionally submit evidence to DisMech | DisMech skill (needed) | Curator API call if DisMech accepts external evidence submissions |

Steps 1, 2, 4, and 5 can be done today using the `typedb-notebook` skill. Steps 3 and 6 require a DisMech skill that does not yet exist.
