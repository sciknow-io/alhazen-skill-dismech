"""
compute_ground_truth.py
-----------------------
Scan all DisMech YAML disorder files and compute authoritative answers for the
10 benchmark questions. Outputs:
  - ground_truth.json   — { question_id: { answer, provenance, computed_at } }
  - questions.json      — full question definitions with metadata

Usage:
    python compute_ground_truth.py \
        --disorders-dir /path/to/dismech/kb/disorders \
        --output-dir ..

The answers are computed entirely from YAML source data, independent of Claude
or any LLM. This is the gold standard for scoring.
"""

import argparse
import collections
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# YAML loading helpers
# ---------------------------------------------------------------------------

def load_all_disorders(disorders_dir: str) -> list[dict]:
    """Load all non-history YAML files. Returns list of dicts with a
    ``_filename`` key added for provenance."""
    paths = sorted(
        p for p in glob.glob(os.path.join(disorders_dir, "*.yaml"))
        if ".history." not in os.path.basename(p)
    )
    disorders = []
    for p in paths:
        try:
            with open(p, encoding="utf-8") as f:
                d = yaml.safe_load(f)
            if d is None:
                continue
            d["_filename"] = os.path.basename(p)
            disorders.append(d)
        except Exception as e:
            print(f"[WARN] skipping {p}: {e}", file=sys.stderr)
    return disorders


def collect_pmids_from_disorder(d: dict) -> list[str]:
    """Extract all PMID strings from every section of a disorder dict."""
    text = yaml.dump(d)
    return re.findall(r"PMID:\d+", text)


def mechanism_descriptions(d: dict) -> list[str]:
    """Return list of (name + description) strings from pathophysiology."""
    mechs = d.get("pathophysiology") or []
    result = []
    for m in mechs:
        if not isinstance(m, dict):
            continue
        parts = []
        if m.get("name"):
            parts.append(m["name"])
        if m.get("description"):
            parts.append(m["description"])
        result.append(" ".join(parts))
    return result


# ---------------------------------------------------------------------------
# Question computations
# ---------------------------------------------------------------------------

def q1_tgfbeta_count(disorders: list[dict]) -> dict:
    """Q1: How many diseases have >= 1 TGF-beta mechanism?"""
    pattern = re.compile(r"tgf.?beta|tgf-?b|transforming growth factor.?beta",
                         re.IGNORECASE)
    matching = []
    for d in disorders:
        texts = mechanism_descriptions(d)
        if any(pattern.search(t) for t in texts):
            matching.append(d["name"])
    matching.sort()
    return {
        "count": len(matching),
        "diseases": matching,
        "question": "How many diseases in DisMech have at least one TGF-beta signaling mechanism documented in their pathophysiology?",
    }


def q2_mendelian_count(disorders: list[dict]) -> dict:
    """Q2: How many diseases are classified as category 'Mendelian'?"""
    matching = sorted(d["name"] for d in disorders if d.get("category") == "Mendelian")
    return {
        "count": len(matching),
        "diseases": matching,
        "question": "How many diseases in DisMech are classified as category 'Mendelian'?",
    }


def q3_wnt_count(disorders: list[dict]) -> dict:
    """Q3: How many diseases involve WNT/beta-catenin pathway?"""
    pattern = re.compile(r"wnt|beta.?catenin|\u03b2.?catenin", re.IGNORECASE)
    matching = []
    for d in disorders:
        texts = mechanism_descriptions(d)
        if any(pattern.search(t) for t in texts):
            matching.append(d["name"])
    matching.sort()
    return {
        "count": len(matching),
        "diseases": matching,
        "question": "How many diseases in DisMech involve WNT/beta-catenin pathway mechanisms?",
    }


def q4_no_treatments(disorders: list[dict]) -> dict:
    """Q4: Diseases with >= 1 mechanism but NO documented treatments."""
    results = []
    for d in disorders:
        has_mechs = bool(d.get("pathophysiology"))
        treatments = d.get("treatments") or []
        has_treatments = bool(treatments)
        if has_mechs and not has_treatments:
            results.append(d["name"])
    results.sort()
    return {
        "count": len(results),
        "diseases": results,
        "question": (
            "Which diseases in DisMech have documented pathophysiology mechanisms "
            "but NO documented treatments? List them."
        ),
    }


def q5_no_genetic(disorders: list[dict]) -> dict:
    """Q5: Diseases with NO genetic entries documented."""
    results = []
    for d in disorders:
        genetic = d.get("genetic") or []
        if not genetic:
            results.append(d["name"])
    results.sort()
    return {
        "count": len(results),
        "diseases": results,
        "question": "Which diseases in DisMech have NO genetic entries documented at all?",
    }


def _has_mondo(dt) -> bool:
    """Check if a disease_term field contains a MONDO ID.

    The YAML structure is:
        disease_term:
          term:
            id: MONDO:0007947
    """
    if not dt or not isinstance(dt, dict):
        return False
    term = dt.get("term") or {}
    if isinstance(term, dict):
        return term.get("id", "").startswith("MONDO:")
    return False


def q6_mondo_coverage(disorders: list[dict]) -> dict:
    """Q6: Which diseases have a MONDO disease term? Which don't?"""
    with_mondo = []
    without_mondo = []
    for d in disorders:
        dt = d.get("disease_term")
        if _has_mondo(dt):
            with_mondo.append(d["name"])
        else:
            without_mondo.append(d["name"])
    with_mondo.sort()
    without_mondo.sort()
    return {
        "count_with_mondo": len(with_mondo),
        "count_without_mondo": len(without_mondo),
        "total": len(disorders),
        "without_mondo_diseases": without_mondo,
        "question": (
            "Which diseases in DisMech have a documented MONDO disease term? "
            "Which do NOT?"
        ),
    }


def q7_top5_by_mechanisms(disorders: list[dict]) -> dict:
    """Q7: Top 5 diseases by pathophysiology mechanism count."""
    counts = []
    for d in disorders:
        mechs = d.get("pathophysiology") or []
        counts.append((d["name"], len(mechs)))
    counts.sort(key=lambda x: (-x[1], x[0]))
    top5 = [{"name": n, "count": c} for n, c in counts[:5]]
    return {
        "ranking": top5,
        "full_ranking": [{"name": n, "count": c} for n, c in counts],
        "question": (
            "Which 5 diseases in DisMech have the most documented pathophysiology "
            "mechanisms? Give counts."
        ),
    }


def q8_top3_categories(disorders: list[dict]) -> dict:
    """Q8: Top 3 disease categories by disease count."""
    cat_counts = collections.Counter(d.get("category", "(none)") for d in disorders)
    top3 = [{"category": cat, "count": n}
            for cat, n in cat_counts.most_common(3)]
    all_cats = [{"category": cat, "count": n}
                for cat, n in cat_counts.most_common()]
    return {
        "top3": top3,
        "all_categories": all_cats,
        "question": (
            "Which 3 disease categories (Mendelian, Genetic, Complex, etc.) "
            "have the most diseases in DisMech?"
        ),
    }


def q9_top5_by_pmids(disorders: list[dict]) -> dict:
    """Q9: Top 5 diseases by total PMID citation count across all sections."""
    counts = []
    for d in disorders:
        pmids = collect_pmids_from_disorder(d)
        counts.append((d["name"], len(pmids), len(set(pmids))))
    counts.sort(key=lambda x: (-x[1], x[0]))
    top5 = [{"name": n, "total_citations": t, "unique_pmids": u}
            for n, t, u in counts[:5]]
    return {
        "ranking": top5,
        "question": (
            "Which 5 diseases have the most total PMID citations across all "
            "sections of their DisMech entries?"
        ),
    }


def q11_fgfr3_diseases(disorders: list[dict]) -> dict:
    """Q11: How many diseases have FGFR3 explicitly in structured gene annotations?"""
    fgfr3_diseases = set()
    for d in disorders:
        for m in (d.get("pathophysiology") or []):
            if not isinstance(m, dict):
                continue
            # Single gene field
            gene = m.get("gene") or {}
            if isinstance(gene, dict) and gene.get("preferred_term") == "FGFR3":
                fgfr3_diseases.add(d["name"])
                break
            # Multiple genes list
            for g in (m.get("genes") or []):
                if isinstance(g, dict) and g.get("preferred_term") == "FGFR3":
                    fgfr3_diseases.add(d["name"])
                    break
    result = sorted(fgfr3_diseases)
    return {
        "count": len(result),
        "diseases": result,
        "question": (
            "How many diseases in DisMech have FGFR3 explicitly listed as a causative gene "
            "in the structured gene annotations of their pathophysiology mechanisms?"
        ),
    }


def q12_hpo_no_genetic(disorders: list[dict]) -> dict:
    """Q12: Diseases with >= 1 HPO phenotype term but NO genetic entries."""
    def has_hpo_phenotype(d: dict) -> bool:
        for ph in (d.get("phenotypes") or []):
            if not isinstance(ph, dict):
                continue
            pt = ph.get("phenotype_term") or {}
            if isinstance(pt, dict):
                term = pt.get("term") or {}
                if isinstance(term, dict) and term.get("id", "").startswith("HP:"):
                    return True
        return False

    results = []
    for d in disorders:
        if has_hpo_phenotype(d) and not d.get("genetic"):
            results.append(d["name"])
    results.sort()
    return {
        "count": len(results),
        "diseases": results,
        "question": (
            "How many diseases in DisMech have at least one HPO phenotype term documented "
            "but NO documented genetic entries?"
        ),
    }


def q13_top5_by_hpo_phenotypes(disorders: list[dict]) -> dict:
    """Q13: Top 5 diseases by count of HPO-annotated phenotypes."""
    def hpo_phenotype_count(d: dict) -> int:
        count = 0
        for ph in (d.get("phenotypes") or []):
            if not isinstance(ph, dict):
                continue
            pt = ph.get("phenotype_term") or {}
            if isinstance(pt, dict):
                term = pt.get("term") or {}
                if isinstance(term, dict) and term.get("id", "").startswith("HP:"):
                    count += 1
        return count

    counts = [(d["name"], hpo_phenotype_count(d)) for d in disorders]
    counts = [(n, c) for n, c in counts if c > 0]
    counts.sort(key=lambda x: (-x[1], x[0]))
    top5 = [{"name": n, "count": c} for n, c in counts[:5]]
    return {
        "ranking": top5,
        "question": (
            "Which 5 diseases in DisMech have the most documented HPO phenotypes? "
            "Give the count for each."
        ),
    }


def q10_all_categories(disorders: list[dict]) -> dict:
    """Q10: All unique disease categories with counts."""
    cat_counts = collections.Counter(d.get("category", "(none)") for d in disorders)
    distribution = sorted(
        [{"category": cat, "count": n} for cat, n in cat_counts.items()],
        key=lambda x: -x["count"],
    )
    return {
        "total_diseases": len(disorders),
        "category_count": len(cat_counts),
        "distribution": distribution,
        "question": (
            "List all unique disease categories in DisMech and the count of "
            "diseases in each."
        ),
    }


# ---------------------------------------------------------------------------
# Questions metadata (for questions.json)
# ---------------------------------------------------------------------------

QUESTIONS = [
    {
        "id": "Q1", "category": 3, "category_name": "pathway_aggregation",
        "scoring": "exact_count",
        "expected_rag_performance": "low",
        "structured_method": "typedb_count",
        "relational_primitive": "GROUP BY + COUNT",
    },
    {
        "id": "Q2", "category": 3, "category_name": "pathway_aggregation",
        "scoring": "exact_count",
        "expected_rag_performance": "low",
        "structured_method": "typedb_count",
        "relational_primitive": "GROUP BY + COUNT",
    },
    {
        "id": "Q3", "category": 3, "category_name": "pathway_aggregation",
        "scoring": "exact_count",
        "expected_rag_performance": "low",
        "structured_method": "typedb_count",
        "relational_primitive": "GROUP BY + COUNT",
    },
    {
        "id": "Q4", "category": 5, "category_name": "negative_space",
        "scoring": "partial_list",
        "expected_rag_performance": "zero",
        "structured_method": "yaml_scan",
        "relational_primitive": "NOT EXISTS (subquery)",
    },
    {
        "id": "Q5", "category": 5, "category_name": "negative_space",
        "scoring": "exact_count",
        "expected_rag_performance": "zero",
        "structured_method": "yaml_scan",
        "relational_primitive": "NOT EXISTS (subquery)",
    },
    {
        "id": "Q6", "category": 5, "category_name": "negative_space",
        "scoring": "exact_count",
        "expected_rag_performance": "zero",
        "structured_method": "yaml_scan",
        "relational_primitive": "NOT EXISTS (subquery)",
    },
    {
        "id": "Q7", "category": 6, "category_name": "ranking",
        "scoring": "exact_ranked_list",
        "expected_rag_performance": "low",
        "structured_method": "typedb_rank",
        "relational_primitive": "ORDER BY … LIMIT N",
    },
    {
        "id": "Q8", "category": 6, "category_name": "ranking",
        "scoring": "exact_ranked_list",
        "expected_rag_performance": "low",
        "structured_method": "yaml_scan",
        "relational_primitive": "ORDER BY … LIMIT N",
    },
    {
        "id": "Q9", "category": 6, "category_name": "ranking",
        "scoring": "exact_ranked_list",
        "expected_rag_performance": "zero",
        "structured_method": "yaml_scan",
        "relational_primitive": "ORDER BY … LIMIT N",
    },
    {
        "id": "Q10", "category": 6, "category_name": "ranking",
        "scoring": "exact_distribution",
        "expected_rag_performance": "zero",
        "structured_method": "yaml_scan",
        "relational_primitive": "ORDER BY … LIMIT N",
    },
    {
        "id": "Q11", "category": 3, "category_name": "pathway_aggregation",
        "scoring": "exact_count",
        "expected_rag_performance": "low",
        "structured_method": "typedb_gene_traversal",
        "relational_primitive": "3-HOP GRAPH TRAVERSAL + COUNT",
    },
    {
        "id": "Q12", "category": 5, "category_name": "negative_space",
        "scoring": "exact_count",
        "expected_rag_performance": "zero",
        "structured_method": "typedb_cross_tier_negation",
        "relational_primitive": "SET SUBTRACTION ACROSS TWO TIERS",
    },
    {
        "id": "Q13", "category": 6, "category_name": "ranking",
        "scoring": "ranked_list_with_counts",
        "expected_rag_performance": "low",
        "structured_method": "typedb_phenotype_rank",
        "relational_primitive": "3-HOP AGGREGATION + ORDER BY LIMIT 5",
    },
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Compute DisMech benchmark ground truth")
    parser.add_argument(
        "--disorders-dir",
        default=os.getenv("DISMECH_DISORDERS_DIR", ""),
        help="Path to dismech/kb/disorders/ directory (or set DISMECH_DISORDERS_DIR env var)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent.parent),
        help="Directory to write ground_truth.json and questions.json",
    )
    args = parser.parse_args()

    print(f"Loading disorders from {args.disorders_dir}...", file=sys.stderr)
    disorders = load_all_disorders(args.disorders_dir)
    print(f"Loaded {len(disorders)} disorders.", file=sys.stderr)

    now = datetime.now(timezone.utc).isoformat()

    # Run all computations
    computations = [
        ("Q1",  q1_tgfbeta_count(disorders)),
        ("Q2",  q2_mendelian_count(disorders)),
        ("Q3",  q3_wnt_count(disorders)),
        ("Q4",  q4_no_treatments(disorders)),
        ("Q5",  q5_no_genetic(disorders)),
        ("Q6",  q6_mondo_coverage(disorders)),
        ("Q7",  q7_top5_by_mechanisms(disorders)),
        ("Q8",  q8_top3_categories(disorders)),
        ("Q9",  q9_top5_by_pmids(disorders)),
        ("Q10", q10_all_categories(disorders)),
        ("Q11", q11_fgfr3_diseases(disorders)),
        ("Q12", q12_hpo_no_genetic(disorders)),
        ("Q13", q13_top5_by_hpo_phenotypes(disorders)),
    ]

    # Build ground_truth.json
    ground_truth = {}
    for qid, result in computations:
        ground_truth[qid] = {
            "answer": result,
            "computed_at": now,
            "disorders_dir": args.disorders_dir,
            "total_disorders_scanned": len(disorders),
        }
        # Print summary
        question_text = result.get("question", "")
        print(f"\n{qid}: {question_text}")
        if "count" in result:
            print(f"     → count: {result['count']}")
        if "count_with_mondo" in result:
            print(f"     → with MONDO: {result['count_with_mondo']}, without: {result['count_without_mondo']}")
        if "ranking" in result:
            for item in result["ranking"][:3]:
                print(f"     → {item}")
        if "top3" in result:
            for item in result["top3"]:
                print(f"     → {item}")
        if "distribution" in result:
            for item in result["distribution"][:5]:
                print(f"     → {item}")

    # Build questions.json (merge metadata with ground truth)
    questions_out = []
    gt_map = dict(computations)
    for q in QUESTIONS:
        entry = dict(q)
        entry["question"] = gt_map[q["id"]].get("question", "")
        questions_out.append(entry)

    # Write outputs
    gt_path = os.path.join(args.output_dir, "ground_truth.json")
    q_path = os.path.join(args.output_dir, "questions.json")

    with open(gt_path, "w") as f:
        json.dump(ground_truth, f, indent=2)
    with open(q_path, "w") as f:
        json.dump(questions_out, f, indent=2)

    print(f"\n✓ ground_truth.json  →  {gt_path}", file=sys.stderr)
    print(f"✓ questions.json     →  {q_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
