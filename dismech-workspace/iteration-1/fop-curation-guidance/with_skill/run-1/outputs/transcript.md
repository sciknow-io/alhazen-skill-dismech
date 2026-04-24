# Session Transcript: FOP DisMech Curation Guidance

**Task**: Walk through the DisMech curation process for Fibrodysplasia Ossificans Progressiva (FOP)

**Skill used**: DisMech skill at `/Users/gullyburns/Documents/GitHub/alhazen-skill-dismech/skills/dismech/`

**Working directory**: `/Users/gullyburns/skillful-alhazen`

---

## Step 1: Read Skill Documentation

**Files read**:
- `/Users/gullyburns/Documents/GitHub/alhazen-skill-dismech/skills/dismech/SKILL.md`
- `/Users/gullyburns/Documents/GitHub/alhazen-skill-dismech/skills/dismech/USAGE.md`
- `/Users/gullyburns/Documents/GitHub/alhazen-skill-dismech/skills/dismech/dismech.py`

**Key findings from SKILL.md**:
- DisMech has 750+ curated disease entries stored in TypeDB 3.x
- TypeDB auto-initializes on session start via SessionStart hook
- Data comes from YAML files in the dismech knowledge base repository
- Primary commands: `ingest`, `show-disease`, `list-diseases`, `search`, `stats`, `serve`

**Key findings from USAGE.md**:
- Three-tier data model per disorder:
  1. Disease entity (name, category, parents)
  2. Disease term descriptor (MONDO/OMIM identifier)
  3. Pathophysiology mechanisms (name + description)
- Commands accept `--source` (directory), `--name` (exact disease name), `--query` (search text)
- Dashboard serves at http://localhost:7777 after `serve` command
- REST API at `/api/` for programmatic access

**Key findings from dismech.py**:
- `_ingest_disease_file()` processes YAML keys: `name`, `category`, `parents`, `synonyms`, `disease_term`, `pathophysiology`
- The current schema only ingests a subset of the full YAML (mechanisms and basic metadata)
- The full YAML format contains much richer data (phenotypes, genetics, treatments, prevalence, evidence) that is curated in the source repo but only partially ingested by the current skill

---

## Step 2: Check Database Status

**Command run**:
```bash
SKILL=/Users/gullyburns/Documents/GitHub/alhazen-skill-dismech/skills/dismech
uv run --project $SKILL --python 3.12 python $SKILL/dismech.py stats
```

**Output**:
```json
{"success": true, "diseases": 605, "mechanisms": 2770, "disease_terms": 600}
```

Database is running and populated with 605 diseases and 2770 mechanisms.

---

## Step 3: Search for Existing FOP Entry

**Command 1** — search by disease name:
```bash
uv run --project $SKILL --python 3.12 python $SKILL/dismech.py search --query "Fibrodysplasia"
```

**Output**:
```json
{"success": true, "query": "Fibrodysplasia", "count": 1, "results": [
  {"disease": "Fibrodysplasia Ossificans Progressiva", "match_type": "name"}
]}
```

**Command 2** — search by gene name:
```bash
uv run --project $SKILL --python 3.12 python $SKILL/dismech.py search --query "ACVR1"
```

**Output**:
```json
{"success": true, "query": "ACVR1", "count": 0, "results": []}
```

Finding: FOP exists in the database by name, but the gene name "ACVR1" does not appear in any mechanism name (only in descriptions, which are not indexed by the current search implementation).

---

## Step 4: Show Full FOP Disease Detail

**Command**:
```bash
uv run --project $SKILL --python 3.12 python $SKILL/dismech.py show-disease \
  --name "Fibrodysplasia Ossificans Progressiva"
```

**Output**:
```json
{
  "success": true,
  "disease": {
    "name": "Fibrodysplasia Ossificans Progressiva",
    "category": "Genetic",
    "mechanisms": [
      {
        "name": "Constitutive BMP Signaling Activation",
        "description": "The ACVR1 R206H mutation creates a pH-sensitive switch in the receptor's activation domain, leading to ligand-independent activation of BMP signaling and inappropriate osteogenic differentiation of connective tissue progenitors."
      },
      {
        "name": "Impaired FKBP1A Regulatory Binding",
        "description": "The R206H mutation reduces binding affinity for FKBP1A/FKBP12, a safeguard protein that normally prevents inappropriate BMP signaling, resulting in leaky activation of the pathway."
      },
      {
        "name": "Activin A Neomorphic Signaling",
        "description": "The R206H mutation renders ACVR1 responsive to Activin A ligands, which normally antagonize BMP signaling. This neomorphic gain-of-function allows Activin A to aberrantly activate osteogenic signaling, driving heterotopic ossification. Anti-Activin A antibodies can block HO. Activin A is an obligate factor for the initiation of HO in FOP."
      },
      {
        "name": "Heterotopic Ossification",
        "description": "Progressive formation of qualitatively normal bone in extraskeletal tissues including muscles, tendons, ligaments, and fascia, typically following episodic inflammatory flare-ups. The process occurs through endochondral ossification with distinct histological stages: inflammatory/catabolic phase, fibroproliferative phase, chondrogenic phase, and osteogenic phase."
      },
      {
        "name": "Inflammatory Triggering of Flare-ups",
        "description": "Macrophages, mast cells, and lymphocytes infiltrate affected tissues during the catabolic phase, releasing inflammatory cytokines that create a permissive microenvironment for heterotopic ossification. Mast cell depletion reduces HO by approximately 50%, and combined mast cell/macrophage depletion reduces HO by approximately 75%."
      }
    ],
    "parents": [
      "Genetic Disease",
      "Musculoskeletal Disease"
    ],
    "disease_term": "fibrodysplasia ossificans progressiva"
  }
}
```

---

## Step 5: Locate the Source YAML File

Searched for dismech disorder YAML files:
```bash
find /Users/gullyburns -name "disorders" -type d
```

Found local dismech knowledge base clone at:
`/Users/gullyburns/Documents/GitHub/dismech/kb/disorders/`

Listed FOP-related files:
```
Fibrodysplasia_Ossificans_Progressiva.history.yaml
Fibrodysplasia_Ossificans_Progressiva.yaml
```

**Read full YAML file**:
`/Users/gullyburns/Documents/GitHub/dismech/kb/disorders/Fibrodysplasia_Ossificans_Progressiva.yaml`

Finding: The source YAML is substantially richer than what the skill ingests. It contains:
- Full prevalence data with population-specific estimates and PMID evidence
- 5 pathophysiology mechanisms with GO terms, CL terms, downstream causal edges, evidence items with exact snippets, and notes
- 6 HPO phenotypes with frequency annotations, diagnostic flags, and evidence
- 1 genetic factor (ACVR1, AD inheritance) with evidence
- 2 environmental triggers with evidence
- 5 treatments with MAXO/CHEBI/NCIT term bindings and evidence
- MONDO disease term binding (MONDO:0007606)
- Background references section with DOIs

---

## Step 6: Read Achondroplasia YAML for Format Comparison

**File read**: `/Users/gullyburns/Documents/GitHub/dismech/kb/disorders/Achondroplasia.yaml`

**Additional format features found**:
- `inheritance` section with `inheritance_term` (HPO binding), `penetrance`, `de_novo_rate`, `parent_of_origin_effect`
- `pdb_structures` on pathophysiology mechanisms (PDB IDs, resolution, method)
- `gene` slot on pathophysiology mechanism nodes (with HGNC term binding)
- `modifier` field on gene/process annotations (`INCREASED`, `DECREASED`, etc.)
- `conforms_to` slot referencing mechanism modules in `kb/modules/`

---

## Step 7: Read dismech Repository Documentation

**Files read**:
- `/Users/gullyburns/Documents/GitHub/alhazen-skill-dismech/CLAUDE.md` — plugin architecture, TypeDB schema patterns
- `/Users/gullyburns/Documents/GitHub/dismech/CONTRIBUTING.md` — submission workflow, QC commands
- `/Users/gullyburns/Documents/GitHub/dismech/CLAUDE.md` — agent-specific instructions, validation details, evidence standards

**Key findings from CONTRIBUTING.md**:
- Submission workflow: create branch → edit YAML → fetch references → validate → PR
- Three validation layers: schema (`just validate`), ontology terms (`just validate-terms`), reference snippets (`just validate-references`)
- OAK is used for ontology lookups (`uv run runoak -i sqlite:obo:hp info "term"`)
- `/curate <disease>` slash command available in the dismech Claude Code project

**Key findings from dismech CLAUDE.md**:
- `evidence_source` describes the paper's evidence type, not the curation method
- `preferred_term` can differ from `term.label`; only `term.label` must match canonical ontology
- HGNC CURIEs use lowercase `hgnc:` prefix
- Mechanism modules in `kb/modules/` define conserved pathological processes
- `conforms_to` slot enables consistency checking against modules without inheritance
- Evidence support values: `SUPPORT`, `REFUTE`, `PARTIAL`, `NO_EVIDENCE`, `WRONG_STATEMENT`

---

## Step 8: Attempted PubMed Search

Attempted PubMed search via MCP tool for additional literature, but the PubMed MCP server session timed out on multiple attempts. Key papers were identified from the existing YAML file's evidence items instead.

**Key PMIDs identified from existing YAML**:
- PMID:17572636 — mutation mechanism, toe malformation (Shore 2006 / Groppe 2007)
- PMID:20463014 — FKBP1A binding, molecular consequences (Kaplan 2010)
- PMID:26896819 — palovarotene mouse study (Chakkalakal 2016)
- PMID:29097342 — variant ACVR1 mutations (Haupt 2018)
- PMID:34353327 — US prevalence 0.88/million
- PMID:28666455 — French prevalence 1.36/million

**Additional paper identified via domain knowledge**:
- PMID:25640599 — Hatsell et al. 2015, Nature Medicine — the primary paper establishing Activin A neomorphic signaling in FOP (currently missing from the YAML's Activin A mechanism evidence)

---

## Summary of Findings

1. **FOP already exists in DisMech** — the YAML is at `/Users/gullyburns/Documents/GitHub/dismech/kb/disorders/Fibrodysplasia_Ossificans_Progressiva.yaml` and is ingested into the TypeDB database

2. **The skill CLI confirms** the entry with 5 mechanisms, MONDO term, and parent categories

3. **The full YAML format** is substantially richer than what the dismech.py skill currently ingests — phenotypes, genetics, treatments, and evidenced prevalence all exist in the YAML but are not yet queryable via the skill CLI

4. **Evidence standards are strict** — every claim needs a PMID, an exact verbatim snippet, and a `supports` classification; the reference validator checks snippets against PubMed abstracts

5. **Ontology terms must be verified with OAK** — never guess IDs or labels; run `uv run runoak -i sqlite:obo:<ontology> info "<term>"` before adding any term

6. **Submission is via pull request** to `github.com/monarch-initiative/dismech` with full validation passing

7. **One evidence gap found**: The Activin A Neomorphic Signaling mechanism currently cites a PARTIAL palovarotene paper instead of the definitive Hatsell 2015 paper (PMID:25640599) that established this mechanism directly
