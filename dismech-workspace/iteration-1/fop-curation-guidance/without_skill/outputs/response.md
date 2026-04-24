# FOP Curation Guidance for DisMech

**Important disclaimer:** I do not have direct access to DisMech and cannot browse its interface, submit data, or verify its exact current schema. The guidance below is based on my general knowledge of disease mechanism databases, rare disease curation standards, and what is publicly known about DisMech as a resource. Treat this as a starting framework — you should verify every field name and submission format against DisMech's own documentation or curator guidelines before submitting.

---

## What is DisMech?

DisMech (Disease Mechanisms Database) is a curated resource focused on the mechanistic underpinnings of rare and complex diseases. Unlike gene-disease association databases (e.g., OMIM, Orphanet) that primarily record what is associated with a disease, DisMech aims to capture *how* a disease works at the molecular and cellular level — the causal chain from mutation to phenotype.

Its data model typically captures:
- The disease entity (with standard ontology identifiers)
- The gene and variant class involved
- The molecular mechanism (gain-of-function, loss-of-function, dominant-negative, etc.)
- The downstream cellular/tissue-level consequence
- Supporting evidence (publications, experimental models)

---

## Fibrodysplasia Ossificans Progressiva (FOP): What You Need to Know

FOP is an exceptionally well-characterized rare disease, which makes it a good curation candidate. Here is the core mechanistic picture you will need to document.

### Disease Identity

| Field | Value |
|---|---|
| Disease name | Fibrodysplasia Ossificans Progressiva |
| Synonyms | Myositis ossificans progressiva; Stone Man syndrome |
| OMIM | #135100 |
| Orphanet | ORPHA:337 |
| MONDO | MONDO:0007763 |
| ICD-10 | M61.1 |
| Inheritance | Autosomal dominant (de novo in >97% of cases) |

### Causative Gene and Variant

| Field | Value |
|---|---|
| Gene symbol | ACVR1 |
| Gene full name | Activin A receptor type 1 |
| Gene ID (NCBI) | 90 |
| Canonical mutation | c.617G>A, p.Arg206His (R206H) |
| Variant class | Missense, gain-of-function (GoF) |
| Protein | ALK2 (Activin-like kinase 2), a type I BMP receptor serine/threonine kinase |
| Mutation effect | Constitutive, ligand-independent activation of SMAD1/5/8 signaling; also confers aberrant responsiveness to Activin A (which normally inhibits the wild-type receptor) |

### Molecular Mechanism

The R206H mutation locks ACVR1/ALK2 in a partially active conformation. Two mechanistic effects combine:

1. **Constitutive BMP signaling:** The mutant receptor signals through the canonical SMAD1/5/8 pathway even in the absence of BMP ligand, driving osteogenic differentiation of progenitor cells.

2. **Activin A neo-agonism:** In wild-type cells, Activin A binds ACVR1 but does not activate SMAD1/5/8 (it signals through SMAD2/3 via ACVR2). The R206H mutation converts Activin A into an agonist for the BMP/SMAD1/5/8 axis. This is mechanistically critical because inflammatory episodes (trauma, infection, injection) elevate local Activin A, which then drives aberrant ossification through the mutant receptor. This explains the episodic, injury-triggered "flare-up" phenotype.

### Cellular and Tissue Mechanism

| Level | Detail |
|---|---|
| Cell type affected | Fibro/adipogenic progenitors (FAPs), muscle satellite cells, endothelial cells (endothelial-to-mesenchymal transition has been proposed) |
| Process | Heterotopic ossification (HO) — formation of bone in soft tissues (muscle, tendons, ligaments, fascia) |
| Trigger | Injury, inflammation, surgical procedures, intramuscular injections, viral illness |
| Pathway | BMP-SMAD1/5/8 → SOX9, RUNX2 upregulation → chondrogenic and then osteogenic differentiation |
| Downstream consequence | Progressive replacement of skeletal muscle and connective tissue with ectopic bone; joint ankylosis; respiratory failure from thoracic HO |

### Animal/Experimental Models

These will be relevant for evidence curation:

- **Knock-in mouse:** `Acvr1[R206H]` conditional knock-in (Acvr1 R206H/+; Rosa26CreERT2) — recapitulates HO after injury
- **Zebrafish model:** acvr1 R206H zebrafish — used for drug screening
- **iPSC models:** Patient-derived iPSCs differentiated to relevant lineages

---

## What to Research Before Curating

Before filling in a DisMech entry, gather evidence for each mechanistic claim. Recommended sources:

### Key Primary Literature

1. **Shore et al. (2006)** — *Nature Genetics* 38:525-527. Original discovery of ACVR1 R206H as the cause of FOP. This is the foundational paper.

2. **Hatsell et al. (2015)** — *Science Translational Medicine* 7:303ra137. Established that Activin A acts as a neo-agonist via the R206H mutant receptor — the key mechanistic insight for the flare-up model.

3. **Dey et al. (2016)** — *JCI Insight*. Further characterization of aberrant Activin A signaling.

4. **Lees-Shepard et al. (2018)** — *Nature Communications*. Identified FAPs as the primary cellular source of HO in FOP.

5. **Moustakas & Heldin (2016)** — Review of BMP/Activin signaling crosstalk relevant to mechanism.

For a DisMech submission you will want PubMed IDs (PMIDs) for each supporting claim. Look up specific PMIDs via PubMed rather than relying on these citations verbatim.

### Databases to Consult

| Resource | URL | What to extract |
|---|---|---|
| OMIM #135100 | omim.org | Variant table, inheritance, gene-disease link |
| Orphanet ORPHA:337 | orpha.net | Prevalence, clinical summary, gene panel |
| ClinVar | clinvar.ncbi.nlm.nih.gov | Variant pathogenicity classifications for ACVR1 R206H |
| UniProt Q04771 | uniprot.org | ACVR1 protein function, domain, active site |
| Reactome | reactome.org | BMP signaling pathway context |
| HGNC | genenames.org | Canonical gene symbol, ID |

---

## Likely DisMech Data Format

Since I cannot access DisMech directly, I am describing the general pattern used by disease mechanism databases of this type. You must verify the exact field names and ontology requirements against DisMech's submission portal or curator documentation.

### Core Record Structure (inferred)

A DisMech entry for FOP would likely be structured around a **disease-gene-mechanism triplet**, with evidence attached. A notional representation:

```
Disease:
  name: "Fibrodysplasia Ossificans Progressiva"
  OMIM: 135100
  Orphanet: ORPHA:337
  MONDO: MONDO:0007763

Gene/Protein:
  symbol: ACVR1
  HGNC_id: 171
  UniProt: Q04771

Variant:
  HGVS_c: c.617G>A
  HGVS_p: p.Arg206His
  variant_class: missense
  mechanism_class: gain-of-function

Molecular Mechanism:
  description: "Constitutive SMAD1/5/8 activation; Activin A neo-agonism"
  pathway: BMP signaling (Reactome: R-HSA-201451)
  normal_function_disrupted: "Ligand-dependent gating of BMP receptor kinase activity"

Cellular Consequence:
  cell_type: "Fibro/adipogenic progenitors (FAPs)"
  process: "Aberrant osteogenic differentiation"
  tissue: "Skeletal muscle, connective tissue"

Clinical Consequence:
  phenotype: "Heterotopic ossification"
  HPO: HP:0100871
  progression: "Progressive joint ankylosis, respiratory failure"

Evidence:
  - PMID: 16642017  (Shore 2006 — discovery)
  - PMID: 26290597  (Hatsell 2015 — Activin A neo-agonism)
  - PMID: 29472543  (Lees-Shepard 2018 — FAP cell type)
  experimental_models:
    - "Acvr1[R206H] conditional knock-in mouse"
    - "Patient-derived iPSCs"
```

### Ontologies Likely Required

| Slot | Ontology |
|---|---|
| Disease | MONDO, Orphanet, OMIM |
| Phenotype | HPO (Human Phenotype Ontology) |
| Gene | HGNC |
| Protein | UniProt |
| Pathway | Reactome or GO Biological Process |
| Cell type | Cell Ontology (CL) |
| Tissue | UBERON |
| Variant class | SO (Sequence Ontology) or ClinVar terms |
| Mechanism class | Likely a DisMech-specific controlled vocabulary |

---

## Submission Process (General Pattern)

Again — I cannot confirm this matches DisMech's actual workflow. This is the typical pattern for curated rare disease databases:

1. **Register or log in** as a curator on the DisMech submission portal.

2. **Search for the disease** to confirm it does not already have a record (or to find a stub you would be extending).

3. **Create a new disease record** using the disease's canonical ontology identifiers (MONDO preferred as a cross-reference hub; Orphanet and OMIM as additional xrefs).

4. **Add the gene-disease association** specifying ACVR1, the variant (R206H), and the mechanism class (gain-of-function). If DisMech distinguishes between constitutive GoF and neo-agonism GoF, you may need two mechanism records.

5. **Add mechanistic detail** — molecular pathway, cell types, downstream processes — linking to controlled vocabulary terms where required.

6. **Add evidence** — PubMed IDs for each mechanistic claim. Some systems require you to tag which specific claim each PMID supports.

7. **Curator review** — Most curated databases have a review step before the record goes live. You may be asked to justify term choices or resolve conflicts with existing records.

---

## FOP-Specific Curation Challenges

A few aspects of FOP that may require careful handling:

- **Two distinct molecular mechanisms in one disease:** The constitutive BMP signaling and the Activin A neo-agonism are separable mechanistic events caused by the same mutation. DisMech may handle these as one record with two mechanism entries, or as two linked records. Check how the schema handles compound mechanisms.

- **Cell-of-origin debate:** The primary cell type responsible for HO has been debated (satellite cells, endothelial cells, FAPs). Current evidence (Lees-Shepard 2018) favors FAPs. Be prepared to cite evidence for the cell type you record.

- **Flare-up trigger model:** The role of inflammation (Activin A release during injury) as a proximate trigger is mechanistically important but distinct from the constitutive signaling. Some databases separate "baseline" mechanism from "triggered" mechanism.

- **Nearly all cases are de novo:** While the inheritance pattern is autosomal dominant, >97% of FOP cases arise from de novo mutations. This is worth flagging in the inheritance field if DisMech supports it.

---

## Recommended Next Steps

1. **Access DisMech directly** — go to the DisMech website, download their data submission template or curator guide, and map the fields above to their actual schema.

2. **Pull the key PMIDs** — use PubMed to confirm the PMIDs for Shore 2006, Hatsell 2015, and Lees-Shepard 2018 before entering them.

3. **Check existing FOP entries** — search DisMech for ACVR1, ORPHA:337, or MONDO:0007763 to see if a stub exists.

4. **Contact DisMech curators** if you have questions about how to represent the dual mechanism (constitutive GoF + Activin A neo-agonism) — this is unusual enough that a curator conversation may save time.

---

*Generated 2026-04-15. Based on general knowledge of disease mechanism databases and published FOP biology. DisMech-specific field names, required ontologies, and submission workflow must be verified against DisMech's own documentation.*
