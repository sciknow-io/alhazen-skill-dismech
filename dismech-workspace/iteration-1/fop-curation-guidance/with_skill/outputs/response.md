# DisMech Curation Guide: Fibrodysplasia Ossificans Progressiva (FOP)

## Key Finding: FOP Already Exists in DisMech

Before walking through the curation process from scratch, the first thing to establish is that
FOP is already in the DisMech knowledge base. A live database query confirms this:

```bash
uv run python /Users/gullyburns/Documents/GitHub/alhazen-skill-dismech/skills/dismech/dismech.py \
  show-disease --name "Fibrodysplasia Ossificans Progressiva"
```

The existing entry contains:
- 5 pathophysiology mechanisms (Constitutive BMP Signaling, FKBP1A Regulatory Binding,
  Activin A Neomorphic Signaling, Heterotopic Ossification, Inflammatory Triggering)
- 6 HPO phenotypes (congenital great toe malformation, HO, joint immobility, joint stiffness,
  scoliosis, restrictive ventilatory defect)
- 1 causal gene (ACVR1, autosomal dominant)
- 2 environmental triggers (trauma, viral illness)
- 5 treatments (palovarotene, corticosteroids, trauma avoidance, genetic counseling, garetosmab)
- MONDO:0007606 binding
- Prevalence data for the US (0.88/million) and France (1.36/million)

The upstream YAML is at:
`https://github.com/monarch-initiative/dismech/blob/main/kb/disorders/Fibrodysplasia_Ossificans_Progressiva.yaml`

What follows is a complete explanation of the DisMech curation process, using FOP as the worked
example. This also serves as a guide for expanding or improving the existing entry.

---

## 1. Overview of DisMech's Data Model

DisMech uses structured YAML files that are validated against a LinkML schema. Each disorder
file has up to seven top-level sections:

| Section | Purpose |
|---|---|
| `name`, `category`, `parents`, `description` | Identity and classification |
| `disease_term` | MONDO ontology binding |
| `prevalence` | Epidemiology with PMID evidence |
| `pathophysiology` | Named mechanisms with GO terms, CL terms, downstream edges, and PMIDs |
| `phenotypes` | HPO-bound clinical features with frequency and evidence |
| `genetic` | Gene associations with inheritance and PMIDs |
| `environmental` | Environmental triggers with PMIDs |
| `treatments` | Therapies with MAXO/CHEBI/NCIT terms and PMIDs |
| `references` | Background references without specific claim attachments |

Every claim in every section is backed by a PMID with an **exact verbatim snippet** from the
paper's abstract and a `supports` classification.

---

## 2. What Research You Need to Do Before Writing YAML

### 2a. Disease Identifier (MONDO)

Look up the canonical MONDO term using OAK:

```bash
uv run runoak -i sqlite:obo:mondo info "fibrodysplasia ossificans progressiva"
# Returns: MONDO:0007606 "fibrodysplasia ossificans progressiva"
```

The `term.label` field in your YAML must exactly match the MONDO canonical label — lowercase
as returned by the ontology, even if the display name uses title case.

### 2b. HPO Phenotype Terms

For each clinical feature, verify the exact HPO term and ID:

```bash
uv run runoak -i sqlite:obo:hp info "ectopic ossification in muscle tissue"
uv run runoak -i sqlite:obo:hp info "limitation of joint mobility"
```

Key HPO terms for FOP (already verified in the existing YAML):

| Phenotype | HPO ID | Canonical Label |
|---|---|---|
| Congenital great toe malformation | HP:0001844 | Abnormal hallux morphology |
| Heterotopic ossification | HP:0011987 | Ectopic ossification in muscle tissue |
| Progressive joint immobility | HP:0001376 | Limitation of joint mobility |
| Joint stiffness | HP:0001387 | Joint stiffness |
| Scoliosis | HP:0002650 | Scoliosis |
| Restrictive ventilatory defect | HP:0002091 | Restrictive ventilatory defect |

Critical note: the `preferred_term` field in your YAML can be a human-readable alias (e.g.,
"Congenital Great Toe Malformation"), but `term.label` must be the exact ontology string.

### 2c. Gene Term (HGNC)

For ACVR1: `hgnc:171` — note the lowercase `hgnc:` prefix, which is the canonical form in
DisMech (not `HGNC:171`).

### 2d. Biological Process Terms (GO)

| Process | GO ID |
|---|---|
| BMP signaling pathway | GO:0030509 |
| Ossification | GO:0001503 |
| Endochondral ossification | GO:0001958 |
| Cartilage development | GO:0051216 |
| Inflammatory response | GO:0006954 |

### 2e. Cell Type Terms (CL)

| Cell | CL ID | Canonical Label |
|---|---|---|
| Osteoblast | CL:0000062 | osteoblast |
| Chondrocyte | CL:0000138 | chondrocyte |
| Macrophage | CL:0000235 | macrophage |
| Mast cell | CL:0000097 | mast cell |

### 2f. Treatment Terms (MAXO / CHEBI / NCIT)

| Treatment | ID |
|---|---|
| Pharmacotherapy (MAXO) | MAXO:0000058 |
| Genetic counseling (MAXO) | MAXO:0000079 |
| Palovarotene (CHEBI) | CHEBI:188559 |
| Garetosmab (NCIT) | NCIT:C170022 |

### 2g. Literature (PMIDs with Exact Abstracts)

DisMech requires PMID-backed snippets that are **verbatim quotes from the paper's abstract**.
The reference validator (`just validate-references`) fetches the abstract and does a substring
match. If the text is not in the abstract, validation fails.

PMIDs used in the existing FOP YAML:

| PMID | Reference | Evidence role |
|---|---|---|
| 17572636 | Groppe et al. 2007, Nature — ACVR1 R206H protein modeling | Mutation mechanism, toe malformation, inheritance, FKBP1A binding |
| 20463014 | Kaplan et al. 2010 — Molecular consequences of R206H | FKBP1A binding loss, BMP activation in muscle |
| 26896819 | Chakkalakal et al. 2016 — Palovarotene mouse model | HO pathophysiology, joint stiffness, treatment efficacy |
| 29097342 | Haupt et al. 2018 — Variable ACVR1 signaling | Variant mutations, R206H prevalence |
| 34353327 | Morales-Piga et al. 2021 — U.S. prevalence | Prevalence: 0.88 per million |
| 28666455 | Ramos-Pleguezuelos et al. 2017 — French prevalence | Prevalence: 1.36 per million |

Papers to consider for improving the existing entry (not yet used with SUPPORT-level snippets):
- **PMID:25640599** — Hatsell et al. 2015, Nature Medicine: directly establishes neomorphic
  Activin A signaling through mutant ACVR1. This would upgrade the Activin A mechanism from
  PARTIAL to SUPPORT.
- Garetosmab OPTIMA Phase 3 trial (NCT03188666): would provide HUMAN_CLINICAL evidence for
  the garetosmab treatment entry, replacing the current PARTIAL mouse-model citation.
- Papers on mast cell/macrophage depletion in FOP: would provide direct evidence for the
  Inflammatory Triggering mechanism (currently cited with NO_EVIDENCE).

Always cache references before writing snippets:
```bash
just fetch-reference PMID:17572636
just fetch-reference PMID:20463014
just fetch-reference PMID:26896819
```

---

## 3. The YAML Format in Full

Files live at `kb/disorders/<Disease_Name_With_Underscores>.yaml` in the dismech knowledge
base repo (`https://github.com/monarch-initiative/dismech`).

Below is the complete annotated format for FOP, reflecting the actual upstream YAML structure:

```yaml
name: Fibrodysplasia Ossificans Progressiva    # Unique key — used as the display name
creation_date: '2025-12-19T01:18:09Z'          # ISO 8601 UTC — set once and never change
updated_date: '2026-02-27T22:30:27Z'           # Update whenever content changes
category: Genetic                              # Mendelian | Genetic | Complex | Infectious | Other
parents:                                       # Free-text hierarchy used for browsing
- Musculoskeletal Disease
- Genetic Disease
description: >-                                # 2-5 sentence prose summary
  A rare, severely disabling genetic disorder characterized by progressive
  heterotopic ossification of skeletal muscles, fascia, tendons, and ligaments,
  with congenital malformation of the great toes. The condition is caused by
  gain-of-function mutations in the ACVR1 gene encoding a BMP type I receptor,
  leading to aberrant bone formation in soft tissues.

disease_term:
  preferred_term: fibrodysplasia ossificans progressiva  # Human-readable (can alias)
  term:
    id: MONDO:0007606                          # Verified with OAK — do NOT guess
    label: fibrodysplasia ossificans progressiva  # MUST exactly match MONDO canonical label

prevalence:
- population: United States residents
  percentage: 0.88 per million
  notes: >-
    A 2021 U.S. ascertainment study across major treatment centers and a
    patient organization estimated prevalence at 0.88 per million residents.
  evidence:
  - reference: PMID:34353327
    supports: SUPPORT
    evidence_source: HUMAN_CLINICAL
    snippet: >-
      An adjusted prevalence of 0.88 per million US residents was calculated
      using either an average survival rate estimate of 98.4% or a conservative
      survival rate estimate of 92.3% (based on the Kaplan-Meier survival curve
      from a previous study) and the US Census 2020 estimate of 329,992,681 on
      prevalence day.
    explanation: >-
      Direct population-based U.S. prevalence estimate for FOP.

pathophysiology:
- name: Constitutive BMP Signaling Activation   # Short mechanism name (matched by downstream.target)
  description: >-
    The ACVR1 R206H mutation creates a pH-sensitive switch in the receptor's
    activation domain, leading to ligand-independent activation of BMP
    signaling and inappropriate osteogenic differentiation of connective
    tissue progenitors.
  biological_processes:
  - preferred_term: BMP signaling pathway
    term:
      id: GO:0030509
      label: BMP signaling pathway             # Must EXACTLY match GO canonical label
  - preferred_term: ossification
    term:
      id: GO:0001503
      label: ossification
  downstream:                                  # Causal edges to other mechanisms or phenotypes
  - target: Heterotopic Ossification           # Must match name in pathophysiology or phenotypes
    description: >-
      Aberrant BMP signaling drives differentiation of muscle and connective
      tissue progenitor cells into chondrocytes and osteoblasts.
    evidence:
    - reference: PMID:20463014
      reference_title: "Molecular consequences of the ACVR1(R206H) mutation..."
      supports: SUPPORT
      snippet: >-
        mild activation of osteogenic BMP-signaling in extraskeletal sites
        such as muscle, which eventually lead to delayed and progressive
        ectopic bone formation in FOP patients
      explanation: >-
        Demonstrates R206H causes BMP activation in muscle leading to ectopic bone.
  - target: Congenital Great Toe Malformation
    description: Aberrant ACVR1 signaling during embryonic patterning disrupts
      first digit development.
  - target: Activin A Neomorphic Signaling
    description: Mutant receptor acquires abnormal signaling response to Activin A.
  evidence:
  - reference: PMID:17572636
    reference_title: "Functional modeling of the ACVR1 (R206H) mutation in FOP."
    supports: SUPPORT
    evidence_source: IN_VITRO
    snippet: >-
      Protein modeling predicts that substitution with histidine, and only
      histidine, creates a pH-sensitive switch within the activation domain
      of the receptor that leads to ligand-independent activation of ACVR1
      in fibrodysplasia ossificans progressiva.
    explanation: >-
      Establishes the molecular basis of pH-dependent receptor dysregulation.

- name: Impaired FKBP1A Regulatory Binding
  description: >-
    The R206H mutation reduces binding affinity for FKBP1A/FKBP12, a safeguard
    protein that normally prevents inappropriate BMP signaling, resulting in
    leaky activation of the pathway.
  cell_types:
  - preferred_term: Osteoblast
    term:
      id: CL:0000062
      label: osteoblast
  evidence:
  - reference: PMID:20463014
    reference_title: "Molecular consequences of the ACVR1(R206H) mutation..."
    supports: SUPPORT
    snippet: >-
      The R206H mutant showed a decreased binding affinity for FKBP1A/FKBP12,
      a known safeguard molecule against the leakage of transforming growth
      factor (TGF)-beta or BMP signaling
    explanation: >-
      Loss of FKBP1A binding is a key mechanism allowing leaky BMP signaling.
  downstream:
  - target: Constitutive BMP Signaling Activation
    description: Loss of FKBP1A inhibition lowers the activation threshold.

- name: Activin A Neomorphic Signaling
  description: >-
    The R206H mutation renders ACVR1 responsive to Activin A ligands, which
    normally antagonize BMP signaling. This neomorphic gain-of-function allows
    Activin A to aberrantly activate osteogenic signaling, driving heterotopic
    ossification. Activin A is an obligate factor for the initiation of HO in FOP.
  biological_processes:
  - preferred_term: BMP signaling pathway
    term:
      id: GO:0030509
      label: BMP signaling pathway
  evidence:
  - reference: PMID:26896819
    supports: PARTIAL                          # Note: Hatsell 2015 (PMID:25640599) would be SUPPORT
    snippet: >-
      Most FOP patients carry an activating mutation in a bone morphogenetic
      protein (BMP) type I receptor gene, ACVR1(R206H), that promotes ectopic
      chondrogenesis and osteogenesis and, in turn, HO
    explanation: >-
      Supports mutant ACVR1-driven ectopic osteochondrogenesis but does not
      directly establish Activin A neomorphic signaling.
  notes: >-
    This discovery led to development of garetosmab (anti-Activin A antibody).
  downstream:
  - target: Heterotopic Ossification
    description: Activin A-driven mutant receptor signaling initiates ectopic bone.

- name: Heterotopic Ossification
  description: >-
    Progressive formation of qualitatively normal bone in extraskeletal tissues
    including muscles, tendons, ligaments, and fascia, typically following
    episodic inflammatory flare-ups. The process occurs through endochondral
    ossification with distinct histological stages.
  cell_types:
  - preferred_term: Osteoblast
    term:
      id: CL:0000062
      label: osteoblast
  - preferred_term: Chondrocyte
    term:
      id: CL:0000138
      label: chondrocyte
  biological_processes:
  - preferred_term: Endochondral ossification
    term:
      id: GO:0001958
      label: endochondral ossification
  evidence:
  - reference: PMID:26896819
    supports: SUPPORT
    snippet: >-
      Fibrodysplasia ossificans progressiva (FOP), a rare and as yet untreatable
      genetic disorder of progressive extraskeletal ossification, is the most
      disabling form of heterotopic ossification (HO) in humans
    explanation: >-
      Establishes FOP as the most severe form of heterotopic ossification.
  downstream:
  - target: Progressive Joint Immobility
    description: Bridging ectopic bone progressively ankyloses major joints.
  - target: Restrictive Ventilatory Defect
    description: Thoracic cage ossification limits chest wall expansion.

- name: Inflammatory Triggering of Flare-ups
  description: >-
    Macrophages, mast cells, and lymphocytes infiltrate affected tissues during
    the catabolic phase, releasing inflammatory cytokines that create a permissive
    microenvironment for heterotopic ossification.
  cell_types:
  - preferred_term: Macrophage
    term:
      id: CL:0000235
      label: macrophage
  - preferred_term: Mast cell
    term:
      id: CL:0000097
      label: mast cell
  biological_processes:
  - preferred_term: Inflammatory response
    term:
      id: GO:0006954
      label: inflammatory response
  evidence:
  - reference: PMID:26896819
    supports: NO_EVIDENCE                     # Needs a direct inflammatory mechanism paper
    snippet: >-
      Fibrodysplasia ossificans progressiva (FOP), a rare and as yet untreatable
      genetic disorder of progressive extraskeletal ossification
    explanation: >-
      Snippet does not directly address immune-cell inflammatory triggering.
  downstream:
  - target: Heterotopic Ossification
    description: Cytokine-rich flare environments recruit progenitors.

phenotypes:
- category: Skeletal
  name: Congenital Great Toe Malformation
  frequency: VERY_FREQUENT                    # OBLIGATE | VERY_FREQUENT | FREQUENT | OCCASIONAL | VERY_RARE
  diagnostic: true                            # Pathognomonic — present at birth
  notes: >-
    Bilateral hallux valgus with short first metatarsals and monophalangic
    great toes. Present at birth.
  evidence:
  - reference: PMID:17572636
    reference_title: "Functional modeling of the ACVR1 (R206H) mutation in FOP."
    supports: SUPPORT
    snippet: >-
      Individuals with fibrodysplasia ossificans progressiva are born with
      malformations of the great toes
    explanation: >-
      Congenital toe malformation described as cardinal feature present from birth.
  phenotype_term:
    preferred_term: Abnormal hallux morphology
    term:
      id: HP:0001844
      label: Abnormal hallux morphology       # EXACTLY matches HPO canonical label

- category: Skeletal
  name: Heterotopic Ossification
  frequency: VERY_FREQUENT
  diagnostic: true
  evidence:
  - reference: PMID:17572636
    supports: SUPPORT
    snippet: >-
      Individuals with fibrodysplasia ossificans progressiva are born with
      malformations of the great toes and develop a heterotopic skeleton
      during childhood
    explanation: >-
      Development of a second skeleton is the defining feature of the disease.
  phenotype_term:
    preferred_term: Ectopic ossification in muscle tissue
    term:
      id: HP:0011987
      label: Ectopic ossification in muscle tissue

genetic:
- name: ACVR1
  association: Causative                      # Causative | Contributory | Protective | Modifier
  inheritance:
  - name: Autosomal Dominant
  notes: >-
    The c.617G>A (p.R206H) mutation found in ~97% of classically affected
    individuals. One of the most highly conserved disease-causing mutations
    in the human genome.
  evidence:
  - reference: PMID:17572636
    reference_title: "Functional modeling of the ACVR1 (R206H) mutation in FOP."
    supports: SUPPORT
    snippet: >-
      Substitution of adenine for guanine at nucleotide 617 replaces an
      evolutionarily conserved arginine with histidine at residue 206 of
      ACVR1 in all classically affected individuals, making this one of the
      most highly conserved disease-causing mutations in the human genome.
    explanation: >-
      R206H identified as the causative mutation in all classic FOP cases.

environmental:
- name: Trauma
  notes: >-
    Physical trauma, including minor injuries, intramuscular injections, and
    surgical procedures, can trigger flare-ups leading to new heterotopic
    ossification. Avoidance of trauma is a key management strategy.
  evidence:
  - reference: PMID:26896819
    supports: PARTIAL
    snippet: >-
      palovarotene effectively inhibited HO in injury-induced and genetic
      mouse models of the disease
    explanation: >-
      The use of injury-induced models demonstrates trauma as a key trigger.

treatments:
- name: Palovarotene
  description: >-
    RARgamma agonist inhibiting endochondral ossification. FDA-approved 2023
    for patients 8+ years (females) and 10+ years (males).
  evidence:
  - reference: PMID:26896819
    supports: PARTIAL
    snippet: >-
      palovarotene maintained joint, limb, and body motion, providing clear
      evidence for its encompassing therapeutic potential as a treatment for FOP.
    explanation: >-
      Demonstrates therapeutic efficacy in FOP mouse models.
  treatment_term:
    preferred_term: pharmacotherapy
    term:
      id: MAXO:0000058
      label: pharmacotherapy
    therapeutic_agent:
    - preferred_term: palovarotene
      term:
        id: CHEBI:188559
        label: palovarotene

- name: Garetosmab
  description: >-
    Anti-Activin A monoclonal antibody. Phase 3 OPTIMA trial showed over 90%
    reduction in new heterotopic ossification lesions.
  treatment_term:
    preferred_term: pharmacotherapy
    term:
      id: MAXO:0000058
      label: pharmacotherapy
    therapeutic_agent:
    - preferred_term: garetosmab
      term:
        id: NCIT:C170022
        label: Garetosmab

references:                                   # Background references without claim attachments
- reference: DOI:10.1631/jzus.b2300779
  title: "Advancements in mechanisms and drug treatments for FOP"
  findings: []
```

---

## 4. Evidence Standards: The Rules That Matter Most

### The Golden Rule: Exact Verbatim Snippets

The `snippet` field in every evidence block must be a verbatim quote from the cited paper's
**PubMed abstract**. The reference validator fetches the abstract and does a substring match.
If the text does not appear in the abstract, validation fails — no exceptions.

**How to get snippets:**
1. Go to PubMed (https://pubmed.ncbi.nlm.nih.gov/17572636/)
2. Read the abstract
3. Copy a relevant sentence verbatim into `snippet`
4. Write your own `explanation` describing why this snippet supports the claim

**Do not fabricate PMIDs.** Do not paraphrase. Do not quote from the full text — only the
abstract is checked.

### Supports Classification

| Value | Meaning |
|---|---|
| `SUPPORT` | The snippet directly demonstrates the stated claim |
| `PARTIAL` | Related but does not fully establish the claim |
| `NO_EVIDENCE` | Paper reviewed but abstract does not address this claim |
| `REFUTE` | Paper contradicts the claim |
| `WRONG_STATEMENT` | The claim itself is incorrect |

### Evidence Source Classification

| Value | When to Use |
|---|---|
| `HUMAN_CLINICAL` | Human patients, cohorts, trials, case reports, epidemiology |
| `MODEL_ORGANISM` | Mouse, zebrafish, or other animal studies |
| `IN_VITRO` | Cell culture, biochemical assays, structural/computational modeling |
| `COMPUTATIONAL` | In silico predictions, molecular docking, network inference |

For FOP:
- ACVR1 mutation identification papers = `HUMAN_CLINICAL`
- Palovarotene mouse studies = `MODEL_ORGANISM`
- pH-switch structural modeling = `IN_VITRO` or `COMPUTATIONAL`
- Garetosmab OPTIMA trial = `HUMAN_CLINICAL`
- Prevalence studies = `HUMAN_CLINICAL`

---

## 5. How to Submit a New Entry or Improve the Existing One

### Step-by-Step Submission Workflow

**Step 1: Clone the dismech knowledge base repository**
```bash
git clone https://github.com/monarch-initiative/dismech.git
cd dismech
just install   # installs Python dependencies including LinkML and OAK
```

**Step 2: Create a branch**
```bash
# For a new disease:
git checkout -b add/fibrodysplasia-ossificans-progressiva

# For improving the existing FOP entry:
git checkout -b improve/fop-activin-a-evidence
```

**Step 3: Write or edit the YAML**

Place at: `kb/disorders/Fibrodysplasia_Ossificans_Progressiva.yaml`

File naming convention: `<Disease_Name_With_Underscores>.yaml`

**Step 4: Fetch all cited references**
```bash
just fetch-reference PMID:17572636
just fetch-reference PMID:20463014
just fetch-reference PMID:26896819
just fetch-reference PMID:29097342
just fetch-reference PMID:34353327
just fetch-reference PMID:28666455
# Add any new PMIDs you cite
```

**Step 5: Run validation**
```bash
# Schema validation against LinkML model
just validate kb/disorders/Fibrodysplasia_Ossificans_Progressiva.yaml

# Ontology term validation (catches non-existent IDs and label mismatches)
just validate-terms

# Reference snippet validation (checks snippets against fetched abstracts)
just validate-references kb/disorders/Fibrodysplasia_Ossificans_Progressiva.yaml

# Full QC suite (run all of the above)
just qc
```

**Step 6: Generate the HTML page (optional)**
```bash
uv run python -m dismech.render kb/disorders/Fibrodysplasia_Ossificans_Progressiva.yaml
```

**Step 7: Commit and open a pull request**
```bash
git add kb/disorders/Fibrodysplasia_Ossificans_Progressiva.yaml
git commit -m "curate: improve FOP Activin A mechanism evidence (PMID:25640599)"
gh pr create \
  --title "Improve FOP: add Hatsell 2015 evidence for Activin A neomorphic signaling" \
  --body "Adds SUPPORT-level PMID:25640599 to the Activin A Neomorphic Signaling mechanism,
upgrading from PARTIAL palovarotene paper. Also adds HGNC term to ACVR1 genetic entry."
```

**Step 8: Address CI failures**

GitHub CI runs `just qc` on every PR. Common failures:
- **Schema error**: A required field is missing or has the wrong type
- **Term validation error**: An ontology ID does not exist or the `label` does not match
  the canonical form — run `uv run runoak -i sqlite:obo:hp info "your term"` to verify
- **Reference validation error**: A `snippet` is not verbatim from the cited abstract

Fix each failure and push — CI re-runs automatically.

---

## 6. Verifying Your Work with the DisMech Skill CLI

After editing the YAML and re-ingesting into the local TypeDB instance:

```bash
SKILL=/Users/gullyburns/Documents/GitHub/alhazen-skill-dismech/skills/dismech

# Verify the disease is in the database
uv run python $SKILL/dismech.py show-disease --name "Fibrodysplasia Ossificans Progressiva"

# Search for related terms
uv run python $SKILL/dismech.py search --query "ACVR1"
uv run python $SKILL/dismech.py search --query "Activin A"

# Check overall stats
uv run python $SKILL/dismech.py stats
```

To re-ingest after editing the YAML (reset required since per-disease update is not yet
supported):
```bash
uv run python \
  /Users/gullyburns/Documents/GitHub/alhazen-skill-dismech/infra/dismech/alhazen_core.py \
  reset --yes

uv run python $SKILL/dismech.py ingest \
  --source /path/to/dismech/kb/disorders
```

---

## 7. What Is Already Done vs. What Could Be Improved

### Already Done (existing FOP YAML in upstream repo)

- MONDO term: `MONDO:0007606`
- 5 pathophysiology mechanisms with GO terms, CL terms, and downstream causal edges
- 6 HPO phenotypes with frequency annotations and diagnostic flags
- ACVR1 gene with inheritance pattern (autosomal dominant) and PMID evidence
- 2 environmental triggers (trauma, viral illness)
- 5 treatments including palovarotene (FDA-approved 2023) and garetosmab
- US prevalence (0.88/million, PMID:34353327) and French prevalence (1.36/million, PMID:28666455)
- 12 background references in the `references` section

### Areas That Could Be Improved

1. **Activin A mechanism needs a SUPPORT-level citation** — the current entry uses PMID:26896819
   (a palovarotene mouse study) with `PARTIAL` support. Hatsell et al. 2015 Nature Medicine
   (PMID:25640599) directly establishes neomorphic Activin A signaling through mutant ACVR1
   and would provide `SUPPORT`-level evidence.

2. **HGNC term missing from the genetic entry** — the `genetic` section for ACVR1 lacks a
   `gene_term` block with `id: hgnc:171` and `label: ACVR1`.

3. **Garetosmab needs HUMAN_CLINICAL evidence** — the treatment entry currently cites a mouse
   model paper. The Phase 3 OPTIMA trial results would provide direct HUMAN_CLINICAL support.

4. **Inflammatory triggering mechanism has NO_EVIDENCE citations** — papers specifically on
   mast cell/macrophage depletion in FOP mouse models would provide direct evidence here.

5. **Variant ACVR1 mutations not covered** — PMID:29097342 (Haupt 2018) covers variant FOP
   mutations (R258S, G325A, etc.) that could be added to the `genetic` section.

---

## 8. Quick Reference Card

```
Upstream YAML:
  https://github.com/monarch-initiative/dismech/blob/main/kb/disorders/Fibrodysplasia_Ossificans_Progressiva.yaml

Validation commands (run from dismech repo root):
  just validate <file>           -- schema check
  just validate-terms            -- ontology ID and label check
  just validate-references <f>   -- snippet verbatim check against PubMed abstracts
  just qc                        -- all of the above

Ontology lookup:
  uv run runoak -i sqlite:obo:hp info "joint stiffness"
  uv run runoak -i sqlite:obo:mondo info "fibrodysplasia ossificans progressiva"
  uv run runoak -i sqlite:obo:go info "BMP signaling pathway"

Key PMIDs for FOP:
  17572636  -- ACVR1 R206H protein modeling + toe malformation (Groppe 2007, Nature)
  20463014  -- FKBP1A binding loss + BMP activation in muscle (Kaplan 2010)
  26896819  -- Palovarotene FOP mouse model (Chakkalakal 2016)
  29097342  -- Variant ACVR1 mutations (Haupt 2018)
  34353327  -- US prevalence 0.88/million (Morales-Piga 2021)
  28666455  -- French prevalence 1.36/million (Ramos-Pleguezuelos 2017)
  25640599  -- Activin A neomorphic signaling (Hatsell 2015, Nature Medicine) [MISSING -- ADD THIS]

DisMech skill CLI:
  uv run python $SKILL/dismech.py show-disease --name "Fibrodysplasia Ossificans Progressiva"
  uv run python $SKILL/dismech.py search --query "ACVR1"
  uv run python $SKILL/dismech.py stats
```
