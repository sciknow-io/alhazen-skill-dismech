# RASopathies in DisMech: RAS/MAPK Pathway Disorders

**Query date:** 2026-04-15
**Database:** DisMech (605 diseases, 2770 mechanisms, TypeDB 3.x)
**Skill:** `/Users/gullyburns/Documents/GitHub/alhazen-skill-dismech/skills/dismech/`

---

## Overview

The DisMech knowledge graph contains four germline RASopathy disorders explicitly curated as part of the RAS/MAPK pathway disease family, plus Neurofibromatosis Type 1 (which mechanistically belongs to the same pathway). These are Mendelian/Genetic disorders caused by gain-of-function mutations in components of the RAS-MAPK signaling cascade.

---

## Germline RASopathies in DisMech

### 1. Noonan Syndrome
**Category:** Genetic
**Parent categories:** Congenital Heart Disease, RASopathy
**Disease term:** Noonan syndrome

**Mechanisms (10 curated):**

| Mechanism | Description |
|---|---|
| SHP2 Gain-of-Function Activation | PTPN11 mutations destabilize the autoinhibitory N-SH2/PTP domain interaction, yielding constitutively elevated phosphatase activity and enhanced ERK activation. SHP2 is a positive regulator of RAS-MAPK signaling. |
| SOS1-Mediated RAS-GTP Loading | SOS1 gain-of-function mutations encode guanine nucleotide exchange factor variants with enhanced activity, increasing the rate of RAS-GDP to RAS-GTP conversion and amplifying downstream MAPK signaling. |
| RAF1 Kinase Hyperactivation | RAF1 mutations (particularly at Ser259 and flanking residues) disrupt 14-3-3 binding and autoinhibition, resulting in constitutively elevated serine-threonine kinase activity and enhanced MEK phosphorylation. |
| RIT1-Mediated RAF Recruitment | RIT1 gain-of-function mutations cause aberrant membrane localization and RAF recruitment, bypassing normal RAS regulation and driving excessive MAPK pathway activation. |
| LZTR1-Mediated RAS Proteostasis Defect | Loss of LZTR1-mediated RAS proteostasis through CRL3 E3 ligase increases RAS-family protein levels (MRAS, RIT1, KRAS) and MAPK signaling. Dominant LZTR1 mutations disrupt ubiquitination and degradation of RAS proteins. |
| ERK Cascade Hyperactivation | Convergent point where all upstream defects lead to sustained ERK1/2 phosphorylation. Affects cell proliferation, differentiation, and survival during embryonic development and postnatal life. |
| Cortical Layer Development Abnormalities | NS-derived cortical organoid models show abnormal excitatory-neuron layer specification and reduced synaptic connectivity. |
| Lymphatic Structural Abnormalities | Severe central and peripheral lymphatic abnormalities producing clinically significant fluid and lymphatic-flow complications. |
| Cardiac Valve Morphogenesis Defects | Perturbed ERK signaling in endocardial/valvular tissues alters endocardial-mesenchymal transition and valve morphogenesis, underlying pulmonary valve stenosis. |
| Cardiomyocyte Hypertrophy | Sustained ERK signaling (and intersecting AKT/mTOR activity) promotes hypertrophic cardiomyocyte growth and fetal gene reprogramming, particularly in RAF1 and RIT1 mutation carriers. |

---

### 2. Costello Syndrome
**Category:** Mendelian
**Parent categories:** RASopathies
**Disease term:** Costello syndrome
**Causal gene:** HRAS (gain-of-function germline mutation)

**Mechanisms (9 curated):**

| Mechanism | Description |
|---|---|
| Germline HRAS gain-of-function mutation | Heterozygous germline activating HRAS variants initiate Costello syndrome and create the constitutive signaling state driving its multisystem phenotype. |
| Constitutive HRAS signaling | Mutant HRAS remains aberrantly active, persistently engaging downstream Ras effector programs and creating a shared upstream driver for cardiac, metabolic, connective tissue, developmental, and oncogenic abnormalities. |
| Cardiac mitochondrial bioenergetic dysfunction | Impaired mitochondrial proteostasis and oxidative phosphorylation in cardiac tissue — indicating the disease is not solely a surface signaling disorder but also a bioenergetic one. |
| Atrial cardiomyocyte pacemaker-nodal transcriptional reprogramming | HRAS-mutant atrial-like cardiomyocytes acquire a pacemaker-nodal-like gene expression program (increased ISL1, TBX3, TBX18), shifting atrial cells toward an arrhythmogenic identity state. |
| Enhanced automaticity and funny current in atrial cardiomyocytes | Reprogrammed HRAS-mutant atrial cardiomyocytes beat faster, contain more pacemaker-like cells, and show elevated funny current density — the proximate electrophysiologic substrate for tachyarrhythmia. |
| Fibroblast metabolic rewiring and increased energetic expenditure | HRAS-driven metabolic dysregulation with abnormal glucose transporter activation, accelerated glycolysis, increased fatty acid synthesis/storage, and accelerated autophagic flux. |
| Impaired fibroblast elastogenesis | Costello syndrome fibroblasts fail to assemble elastic fibers efficiently, with reduced elastin deposition and abnormal extracellular matrix organization. |
| Dysregulated neural progenitor development | HRAS activation alters the balance of neural progenitor expansion, cortical neuron production, and gliogenesis — a basis for neurodevelopmental impairment. |
| Tumor Predisposition | The same activating HRAS signaling architecture creates susceptibility to embryonal and later-onset malignant neoplasms. |

---

### 3. Cardiofaciocutaneous (CFC) Syndrome
**Category:** Mendelian
**Parent categories:** RASopathies
**Disease term:** Cardiofaciocutaneous syndrome
**Causal genes:** BRAF (~75%), MEK1, MEK2

**Mechanisms (1 curated):**

| Mechanism | Description |
|---|---|
| RAS-MAPK Pathway Hyperactivation | Mutations in BRAF, MEK1, or MEK2 cause constitutive or enhanced activation of the RAS-MAPK signaling cascade, affecting cell proliferation and differentiation during development. BRAF mutations are most common (~75%), followed by MEK1/MEK2 mutations. |

---

### 4. Neurofibromatosis Type 1 (NF1)
**Category:** (uncategorized in DisMech)
**Parent categories:** hereditary cancer-predisposing syndrome
**Disease term:** neurofibromatosis type 1
**Causal gene:** NF1 (neurofibromin, a RAS GAP — loss-of-function)

**Mechanisms (6 curated):**

| Mechanism | Description |
|---|---|
| NF1 Tumor Suppressor Loss | Germline heterozygous NF1 mutations result in haploinsufficiency for neurofibromin. Somatic loss of the wild-type allele eliminates neurofibromin completely, losing RAS negative regulation and driving tumorigenesis (Knudson's two-hit hypothesis). |
| RAS-MAPK Pathway Hyperactivation | Constitutive RAS-MAPK pathway activation due to loss of neurofibromin's RAS-GAP (GTPase-activating protein) function. |
| Uncontrolled Neural Crest Cell Proliferation | Neural crest-derived cells (Schwann cells, melanocytes) show particular dependence on RAS-MAPK signaling. Loss of neurofibromin drives uncontrolled proliferation, resulting in neurofibromas and cafe-au-lait macules. |
| Tumor Development | Progressive accumulation of genomic alterations in the context of elevated RAS signaling leads to transformation. |
| Neurodevelopmental Circuit Dysfunction | Constitutive RAS-MAPK signaling in developing brain circuits disrupts synaptic maturation, attention control, and executive function, contributing to the cognitive/learning phenotype. |
| Skeletal Dysplasia | NF1-related dysregulation of osteoblast and osteoclast signaling alters bone modeling and spinal structural integrity, predisposing to deformity. |

---

## Shared Mechanistic Themes Across RASopathies

All four disorders share a common mechanistic foundation: **sustained hyperactivation of the RAS-MAPK (ERK) signaling cascade during embryonic development and postnatal life**, arising from different points of mutation in the same linear pathway:

```
Growth factor receptor
        |
   GRB2/SOS1 (Noonan: SOS1 GOF)
        |
   RAS-GTP  <--> RAS-GDP
        |            ^
   HRAS (Costello)   |
   LZTR1 (Noonan)    | NF1/neurofibromin (NF1: LOF GAP)
        |
      RAF1 (Noonan: RAF1 GOF)
      BRAF  (CFC: BRAF GOF)
        |
   MEK1/MEK2 (CFC: MEK1/2 GOF)
        |
   ERK1/ERK2  ← Convergent hyperactivation endpoint
        |
  Proliferation / Differentiation / Survival
```

### 1. Convergent ERK Hyperactivation
Every RASopathy in DisMech converges on **sustained ERK1/2 phosphorylation**, regardless of which upstream node is mutated. Noonan syndrome's curated record explicitly names "ERK Cascade Hyperactivation" as the convergent mechanism.

### 2. Gain-of-Function vs. Loss-of-Function Logic
- **Gain-of-function (Noonan, Costello, CFC):** Activating mutations in positive regulators (SHP2/PTPN11, SOS1, RAF1, RIT1, HRAS, BRAF, MEK1/2) drive the cascade upward.
- **Loss-of-function (NF1):** Inactivating mutations in neurofibromin (a RAS-GTPase activating protein) remove the brake that normally terminates RAS-GTP signaling. Net effect is identical: excessive RAS-GTP and ERK activation.

### 3. Multi-Organ Developmental Pathology
All four disorders produce overlapping multi-system phenotypes because the RAS-MAPK pathway is active in virtually every tissue during development:
- **Cardiac:** Pulmonary valve stenosis, hypertrophic cardiomyopathy (Noonan/CFC); arrhythmia (Costello); vascular neurofibromas (NF1)
- **Neurodevelopmental:** Cognitive impairment, learning difficulties across all four
- **Facial dysmorphism:** Characteristic overlapping craniofacial features (Noonan, CFC, Costello share similar facies, contributing to initial diagnostic confusion)
- **Growth:** Short stature is near-universal across the germline RASopathies

### 4. Tumor Predisposition
All RASopathies carry elevated cancer risk:
- **Costello:** Embryonal tumors (rhabdomyosarcoma), bladder carcinoma
- **NF1:** Neurofibromas with malignant transformation risk, gliomas, leukemia
- **Noonan:** Juvenile myelomonocytic leukemia (JMML), particularly with PTPN11 and CBL mutations
- **CFC:** Lower penetrance tumor risk, leukemia reported

The mechanism is the same: the same constitutive signaling that disrupts development lowers the threshold for oncogenic transformation.

### 5. Tissue-Specific Amplification of MAPK Effects
Different mutated nodes create different tissue-specific emphases despite pathway convergence:
- **HRAS (Costello):** Particularly affects cardiac electrophysiology (atrial reprogramming, arrhythmia) and connective tissue (impaired elastogenesis)
- **RAF1 (Noonan):** Strongly associated with hypertrophic cardiomyopathy
- **BRAF/MEK (CFC):** More severe intellectual disability, ectodermal abnormalities (sparse hair, skin keratosis)
- **NF1:** Schwann cell lineage (neurofibromas) and melanocyte lineage (cafe-au-lait) predominance due to neural crest cell susceptibility

### 6. Druggable Nodes
The shared pathway creates a shared therapeutic opportunity: MEK inhibitors (e.g., trametinib, selumetinib) are being explored or approved across multiple RASopathies. Selumetinib is FDA-approved for NF1-associated plexiform neurofibromas; MEK inhibitor trials are ongoing in Noonan, Costello, and CFC syndromes.

---

## Summary Table

| Disorder | Gene(s) | Mutation Type | Pathway Node | Cardiac | Neurodevelopment | Cancer Risk |
|---|---|---|---|---|---|---|
| Noonan Syndrome | PTPN11, SOS1, RAF1, RIT1, LZTR1, others | GOF (mostly) | Multiple (SHP2, SOS1, RAF1, RIT1, RAS proteostasis) | Pulmonary stenosis, HCM | Cognitive delay, learning | JMML, leukemia |
| Costello Syndrome | HRAS | GOF | RAS (HRAS) | Arrhythmia, HCM | Intellectual disability | Embryonal tumors, bladder Ca |
| CFC Syndrome | BRAF, MEK1, MEK2 | GOF | RAF/MEK | Septal defects, HCM | Severe ID, absent speech | Leukemia (lower risk) |
| Neurofibromatosis Type 1 | NF1 | LOF (GAP function) | RAS negative regulator | Vascular anomalies | Learning disability, ADHD | Neurofibromas, glioma, JMML |

**GOF** = gain-of-function; **LOF** = loss-of-function; **HCM** = hypertrophic cardiomyopathy; **ID** = intellectual disability; **JMML** = juvenile myelomonocytic leukemia

---

## Notes on DisMech Coverage

- **Not found in DisMech:** Noonan Syndrome with Multiple Lentigines (formerly LEOPARD syndrome, caused by PTPN11 loss-of-function at Asn308Asp), Legius Syndrome (SPRED1), Capillary Malformation-Arteriovenous Malformation (RASA1). These are additional canonical RASopathies not yet curated in the current database (605 diseases).
- **Cancer entries with RAS/MAPK involvement** (KRAS-mutant cancers, BRAF-mutant cancers, NRAS-mutant melanoma) are in DisMech but represent somatic oncogenesis rather than germline RASopathies; they share the pathway but are etiologically distinct.
- The term "RASopathy" does not appear as a searchable string in disease names or mechanism names in DisMech — disorders are found via pathway component terms (RAS, MAPK, HRAS, SOS1, RAF1, ERK, etc.) or by browsing parent categories (RASopathy, RASopathies).
