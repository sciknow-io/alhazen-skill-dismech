"""
run_structured.py
-----------------
Run each of the 13 benchmark questions under the structured condition.

All questions use TypeQL queries against the TypeDB `dismech` database.
For questions requiring regex matching on text fields (Q1, Q3), the query
fetches mechanism names and descriptions, then filters in Python.

For each question:
  1. Execute TypeDB structured query (deterministic)
  2. Pass structured result + question to Claude Sonnet 4.6 to format the answer
  3. Save full run record to results/{question_id}/structured_run1.json

Usage:
    python run_structured.py \
        [--questions-file ../questions.json] \
        [--results-dir ../results] \
        [--question-ids Q1,Q2,Q3]   # optional: run subset

Environment:
    ANTHROPIC_API_KEY  — required for Claude API
    TYPEDB_HOST        — TypeDB host (default: localhost)
    TYPEDB_PORT        — TypeDB port (default: 1729)
    TYPEDB_DATABASE    — TypeDB database name (default: dismech)
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# TypeDB connection config
# ---------------------------------------------------------------------------
TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "dismech")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")


def get_typedb_driver():
    from typedb.driver import Credentials, DriverOptions, TypeDB
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = (
    "You are answering questions about DisMech, a curated database of rare disease "
    "mechanisms maintained by the Monarch Initiative.\n\n"
    "You have been given the exact, authoritative result from a structured database query. "
    "Format it as a clear, direct answer to the question. Do not hedge or add caveats — "
    "the structured result is complete and accurate. Present numbers exactly as given."
)


# ---------------------------------------------------------------------------
# TypeDB helper: fetch all results for a query
# ---------------------------------------------------------------------------

def _fetch(driver, query: str) -> list[dict]:
    from typedb.driver import TransactionType
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        return list(tx.query(query).resolve())


# ---------------------------------------------------------------------------
# Structured queries (all TypeDB-backed)
# ---------------------------------------------------------------------------

def q1_structured():
    """Q1: Count diseases with TGF-beta signaling in pathophysiology name or description."""
    driver = get_typedb_driver()
    try:
        # Fetch mechanism names
        names = _fetch(driver, '''
            match $d isa disease, has name $dn;
              ($d, $p) isa pathophysiology-rel;
              $p isa pathophysiology, has name $pn;
            fetch { "disease": $dn, "text": $pn };
        ''')
        # Fetch mechanism descriptions
        descs = _fetch(driver, '''
            match $d isa disease, has name $dn;
              ($d, $p) isa pathophysiology-rel;
              $p isa pathophysiology, has description $pd;
            fetch { "disease": $dn, "text": $pd };
        ''')
        pattern = re.compile(r"tgf.?beta|tgf-?b|transforming growth factor.?beta", re.IGNORECASE)
        matching = set()
        for r in names + descs:
            if pattern.search(r["text"]):
                matching.add(r["disease"])
        diseases = sorted(matching)
        return {"count": len(diseases), "diseases": diseases}
    finally:
        driver.close()


def q2_structured():
    """Q2: Count diseases classified as category 'Mendelian'."""
    driver = get_typedb_driver()
    try:
        results = _fetch(driver, '''
            match $d isa disease, has name $dn, has category $c;
              $c == "Mendelian";
            fetch { "name": $dn };
        ''')
        diseases = sorted(r["name"] for r in results)
        return {"count": len(diseases), "diseases": diseases}
    finally:
        driver.close()


def q3_structured():
    """Q3: Count diseases with WNT/beta-catenin pathway in pathophysiology name or description."""
    driver = get_typedb_driver()
    try:
        names = _fetch(driver, '''
            match $d isa disease, has name $dn;
              ($d, $p) isa pathophysiology-rel;
              $p isa pathophysiology, has name $pn;
            fetch { "disease": $dn, "text": $pn };
        ''')
        descs = _fetch(driver, '''
            match $d isa disease, has name $dn;
              ($d, $p) isa pathophysiology-rel;
              $p isa pathophysiology, has description $pd;
            fetch { "disease": $dn, "text": $pd };
        ''')
        pattern = re.compile(r"wnt|beta.?catenin|\u03b2.?catenin", re.IGNORECASE)
        matching = set()
        for r in names + descs:
            if pattern.search(r["text"]):
                matching.add(r["disease"])
        diseases = sorted(matching)
        return {"count": len(diseases), "diseases": diseases}
    finally:
        driver.close()


def q4_structured():
    """Q4: Diseases with pathophysiology mechanisms but NO treatments."""
    driver = get_typedb_driver()
    try:
        has_mech = set(r["name"] for r in _fetch(driver, '''
            match $d isa disease, has name $dn;
              ($d, $p) isa pathophysiology-rel;
            fetch { "name": $dn };
        '''))
        has_treat = set(r["name"] for r in _fetch(driver, '''
            match $d isa disease, has name $dn;
              ($d, $t) isa treatments;
            fetch { "name": $dn };
        '''))
        diseases = sorted(has_mech - has_treat)
        return {"count": len(diseases), "diseases": diseases}
    finally:
        driver.close()


def q5_structured():
    """Q5: Diseases with NO genetic entries."""
    driver = get_typedb_driver()
    try:
        all_diseases = set(r["name"] for r in _fetch(driver, '''
            match $d isa disease, has name $dn;
            fetch { "name": $dn };
        '''))
        has_genetic = set(r["name"] for r in _fetch(driver, '''
            match $d isa disease, has name $dn;
              ($d, $g) isa genetic-rel;
            fetch { "name": $dn };
        '''))
        diseases = sorted(all_diseases - has_genetic)
        return {"count": len(diseases), "diseases": diseases}
    finally:
        driver.close()


def q6_structured():
    """Q6: Diseases with/without a MONDO disease term."""
    driver = get_typedb_driver()
    try:
        # Get all diseases with a disease-term -> descriptor -> term-rel -> id
        term_results = _fetch(driver, '''
            match $d isa disease, has name $dn;
              ($d, $dd) isa disease-term;
              $dd isa diseasedescriptor;
              ($dd, $t) isa term-rel;
              $t has id $tid;
            fetch { "name": $dn, "term_id": $tid };
        ''')
        mondo_diseases = set()
        for r in term_results:
            if r["term_id"].startswith("MONDO:"):
                mondo_diseases.add(r["name"])

        all_diseases = set(r["name"] for r in _fetch(driver, '''
            match $d isa disease, has name $dn;
            fetch { "name": $dn };
        '''))
        without_mondo = all_diseases - mondo_diseases

        return {
            "count_with_mondo": len(mondo_diseases),
            "count_without_mondo": len(without_mondo),
            "total": len(all_diseases),
            "with_mondo_diseases": sorted(mondo_diseases),
            "without_mondo_diseases": sorted(without_mondo),
        }
    finally:
        driver.close()


def q7_structured():
    """Q7: Top 5 diseases by pathophysiology mechanism count."""
    driver = get_typedb_driver()
    try:
        results = _fetch(driver, '''
            match $d isa disease, has name $dn;
              ($d, $p) isa pathophysiology-rel;
              $p isa pathophysiology, has name $pn;
            fetch { "disease": $dn, "mech": $pn };
        ''')
        counts = Counter(r["disease"] for r in results)
        top5 = [{"name": n, "count": c} for n, c in counts.most_common(5)]
        return {"ranking": top5}
    finally:
        driver.close()


def q8_structured():
    """Q8: Top 3 disease categories by disease count."""
    driver = get_typedb_driver()
    try:
        cat_results = _fetch(driver, '''
            match $d isa disease, has name $dn, has category $c;
            fetch { "name": $dn, "cat": $c };
        ''')
        all_diseases = set(r["name"] for r in _fetch(driver, '''
            match $d isa disease, has name $dn;
            fetch { "name": $dn };
        '''))
        has_cat = set(r["name"] for r in cat_results)
        cat_counts = Counter(r["cat"] for r in cat_results)
        no_cat = len(all_diseases - has_cat)
        if no_cat > 0:
            cat_counts["(none)"] = no_cat
        top3 = [{"category": cat, "count": n} for cat, n in cat_counts.most_common(3)]
        return {"top3": top3}
    finally:
        driver.close()


def q9_structured():
    """Q9: Top 5 diseases by total PMID citation count across all evidence tiers."""
    driver = get_typedb_driver()
    try:
        evidence_queries = [
            # Pathophysiology evidence
            '''match $d isa disease, has name $dn;
                ($d, $p) isa pathophysiology-rel;
                ($p, $ei) isa evidence;
                $ei isa evidenceitem, has reference $ref;
            fetch { "disease": $dn, "ref": $ref };''',
            # Genetic evidence
            '''match $d isa disease, has name $dn;
                ($d, $g) isa genetic-rel;
                ($g, $ei) isa evidence;
                $ei isa evidenceitem, has reference $ref;
            fetch { "disease": $dn, "ref": $ref };''',
            # Treatment evidence
            '''match $d isa disease, has name $dn;
                ($d, $t) isa treatments;
                ($t, $ei) isa evidence;
                $ei isa evidenceitem, has reference $ref;
            fetch { "disease": $dn, "ref": $ref };''',
            # Phenotype evidence
            '''match $d isa disease, has name $dn;
                ($d, $ph) isa phenotypes;
                ($ph, $ei) isa evidence;
                $ei isa evidenceitem, has reference $ref;
            fetch { "disease": $dn, "ref": $ref };''',
            # Inheritance evidence
            '''match $d isa disease, has name $dn;
                ($d, $i) isa inheritance-rel;
                ($i, $ei) isa evidence;
                $ei isa evidenceitem, has reference $ref;
            fetch { "disease": $dn, "ref": $ref };''',
        ]
        all_refs = []
        for query in evidence_queries:
            all_refs.extend(_fetch(driver, query))

        counts = Counter(r["disease"] for r in all_refs)
        top5 = [{"name": n, "total_citations": c} for n, c in counts.most_common(5)]
        return {"ranking": top5}
    finally:
        driver.close()


def q10_structured():
    """Q10: Full disease category distribution."""
    driver = get_typedb_driver()
    try:
        cat_results = _fetch(driver, '''
            match $d isa disease, has name $dn, has category $c;
            fetch { "name": $dn, "cat": $c };
        ''')
        all_diseases = set(r["name"] for r in _fetch(driver, '''
            match $d isa disease, has name $dn;
            fetch { "name": $dn };
        '''))
        has_cat = set(r["name"] for r in cat_results)
        cat_counts = Counter(r["cat"] for r in cat_results)
        no_cat = len(all_diseases - has_cat)
        if no_cat > 0:
            cat_counts["(none)"] = no_cat
        distribution = sorted(
            [{"category": cat, "count": n} for cat, n in cat_counts.items()],
            key=lambda x: -x["count"],
        )
        return {"total_diseases": len(all_diseases), "distribution": distribution}
    finally:
        driver.close()


def q11_structured():
    """Q11: TypeDB graph traversal — diseases with FGFR3 in gene annotations."""
    driver = get_typedb_driver()
    try:
        results = _fetch(driver, '''
            match
              $d isa disease, has name $dn;
              (disease: $d, pathophysiology: $p) isa pathophysiology-rel;
              (pathophysiology: $p, genedescriptor: $gd) isa gene;
              $gd has preferred-term $pt;
              $pt == "FGFR3";
            fetch { "disease": $dn };
        ''')
        diseases = sorted(set(r["disease"] for r in results))
        return {"count": len(diseases), "diseases": diseases}
    finally:
        driver.close()


def q12_structured():
    """Q12: TypeDB cross-tier NOT EXISTS — HPO phenotypes but no genetic entries."""
    driver = get_typedb_driver()
    try:
        has_hpo = set(r["disease"] for r in _fetch(driver, '''
            match
              $d isa disease, has name $dn;
              (disease: $d, phenotype: $ph) isa phenotypes;
              (phenotype: $ph, phenotypedescriptor: $pd) isa phenotype-term;
            fetch { "disease": $dn };
        '''))
        has_genetic = set(r["disease"] for r in _fetch(driver, '''
            match
              $d isa disease, has name $dn;
              (disease: $d, genetic: $g) isa genetic-rel;
            fetch { "disease": $dn };
        '''))
        result = sorted(has_hpo - has_genetic)
        return {"count": len(result), "diseases": result}
    finally:
        driver.close()


def q13_structured():
    """Q13: TypeDB phenotype aggregation — top 5 by HPO phenotype count."""
    driver = get_typedb_driver()
    try:
        results = _fetch(driver, '''
            match
              $d isa disease, has name $dn;
              (disease: $d, phenotype: $ph) isa phenotypes;
              (phenotype: $ph, phenotypedescriptor: $pd) isa phenotype-term;
            fetch { "disease": $dn };
        ''')
        counts = Counter(r["disease"] for r in results)
        top5 = [{"name": n, "count": c} for n, c in counts.most_common(5)]
        return {"ranking": top5}
    finally:
        driver.close()


QUERY_FUNCTIONS = {
    "Q1": q1_structured,
    "Q2": q2_structured,
    "Q3": q3_structured,
    "Q4": q4_structured,
    "Q5": q5_structured,
    "Q6": q6_structured,
    "Q7": q7_structured,
    "Q8": q8_structured,
    "Q9": q9_structured,
    "Q10": q10_structured,
    "Q11": q11_structured,
    "Q12": q12_structured,
    "Q13": q13_structured,
}


# ---------------------------------------------------------------------------
# Claude formatting
# ---------------------------------------------------------------------------

def format_result_for_prompt(qid: str, result: dict) -> str:
    """Format the structured result as a human-readable string for Claude's context."""
    lines = [f"Structured query result for {qid}:", ""]
    for key, value in result.items():
        if isinstance(value, list):
            if len(value) > 20:
                preview = value[:20]
                lines.append(f"{key}: {json.dumps(preview)} ... ({len(value)} total)")
            else:
                lines.append(f"{key}: {json.dumps(value, indent=2)}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def call_claude(question: str, structured_result_text: str) -> dict | None:
    """Call Claude to format the structured result. Returns None if API key is missing."""
    try:
        import anthropic
    except ImportError:
        print("  [warn] anthropic not installed — storing structured result without LLM formatting", file=sys.stderr)
        return None
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("  [warn] ANTHROPIC_API_KEY not set — storing structured result without LLM formatting", file=sys.stderr)
        return None
    client = anthropic.Anthropic(api_key=api_key)
    user_message = (
        f"Structured query result:\n\n{structured_result_text}\n\n"
        f"---\n\nQuestion: {question}\n\nAnswer:"
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return {
        "response": response.content[0].text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run DisMech benchmark under structured condition (all TypeDB)"
    )
    parser.add_argument(
        "--questions-file",
        default=str(Path(__file__).parent.parent / "questions.json"),
    )
    parser.add_argument(
        "--results-dir",
        default=str(Path(__file__).parent.parent / "results"),
    )
    parser.add_argument(
        "--question-ids",
        default="",
        help="Comma-separated list of question IDs to run (default: all)",
    )
    args = parser.parse_args()

    print(f"[info] TypeDB: {TYPEDB_HOST}:{TYPEDB_PORT}/{TYPEDB_DATABASE}", file=sys.stderr)

    with open(args.questions_file) as f:
        questions = json.load(f)

    if args.question_ids:
        target_ids = set(args.question_ids.split(","))
        questions = [q for q in questions if q["id"] in target_ids]

    print(f"[info] Running {len(questions)} questions under structured condition", file=sys.stderr)

    for q in questions:
        qid = q["id"]
        out_dir = os.path.join(args.results_dir, qid)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "structured_run1.json")

        if os.path.exists(out_path):
            print(f"[skip] {qid}: {out_path} already exists", file=sys.stderr)
            continue

        print(f"\n[{qid}] {q['question'][:80]}...", file=sys.stderr)

        if qid not in QUERY_FUNCTIONS:
            print(f"  [ERROR] No query function for {qid}", file=sys.stderr)
            continue

        try:
            # Run structured query
            print(f"  [query] Running TypeDB structured query...", file=sys.stderr)
            structured_result = QUERY_FUNCTIONS[qid]()
            result_text = format_result_for_prompt(qid, structured_result)

            # Format answer with Claude (optional)
            print(f"  [claude] Calling {MODEL} to format answer...", file=sys.stderr)
            llm_result = call_claude(q["question"], result_text)

            record = {
                "question_id": qid,
                "question": q["question"],
                "category": q.get("category"),
                "category_name": q.get("category_name"),
                "condition": "structured",
                "model": MODEL,
                "structured_result": structured_result,
                "structured_result_text": result_text,
                "response": llm_result["response"] if llm_result else result_text,
                "llm_formatted": llm_result is not None,
                "input_tokens": llm_result["input_tokens"] if llm_result else 0,
                "output_tokens": llm_result["output_tokens"] if llm_result else 0,
                "run_at": datetime.now(timezone.utc).isoformat(),
            }

            with open(out_path, "w") as f:
                json.dump(record, f, indent=2)
            print(f"  [saved] {out_path}", file=sys.stderr)
            preview = record["response"][:200]
            print(f"  [response preview] {preview}...", file=sys.stderr)

        except Exception as e:
            print(f"  [ERROR] {qid}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        time.sleep(0.3)

    print("\n[done] Structured condition complete", file=sys.stderr)


if __name__ == "__main__":
    main()
