"""
run_structured.py
-----------------
Run each of the 10 benchmark questions under the structured condition.

Strategy per category:
  Cat 3 (aggregation) — Python YAML scan with regex/field matching (same logic as compute_ground_truth.py)
  Cat 5 (negative space) — Python YAML scan with absence detection
  Cat 6 (ranking) — Python YAML scan with sort/limit

For each question:
  1. Execute structured query (deterministic Python scan of YAML files)
  2. Pass structured result + question to Claude Sonnet 4.6 to format the answer
  3. Save full run record to results/{question_id}/structured_run1.json

Usage:
    python run_structured.py \
        [--questions-file ../questions.json] \
        [--disorders-dir /path/to/dismech/kb/disorders] \
        [--results-dir ../results] \
        [--question-ids Q1,Q2,Q3]   # optional: run subset

Environment:
    ANTHROPIC_API_KEY  — required for Claude API
"""

import argparse
import collections
import glob
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# TypeDB connection config (for Q11–Q13 TypeDB-backed structured queries)
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
DEFAULT_DISORDERS_DIR = "/Users/gullyburns/Documents/GitHub/dismech/kb/disorders"

SYSTEM_PROMPT = (
    "You are answering questions about DisMech, a curated database of rare disease "
    "mechanisms maintained by the Monarch Initiative. The database contains entries for "
    "approximately 605 diseases.\n\n"
    "You have been given the exact, authoritative result from a structured database query. "
    "Format it as a clear, direct answer to the question. Do not hedge or add caveats — "
    "the structured result is complete and accurate. Present numbers exactly as given."
)

# ---------------------------------------------------------------------------
# YAML loading (shared with compute_ground_truth.py)
# ---------------------------------------------------------------------------

PMID_RE = re.compile(r"PMID:(\d+)")


def load_disorders(disorders_dir: str) -> list[dict]:
    paths = sorted(
        p for p in glob.glob(os.path.join(disorders_dir, "*.yaml"))
        if ".history." not in os.path.basename(p)
    )
    disorders = []
    for p in paths:
        try:
            with open(p, encoding="utf-8") as f:
                d = yaml.safe_load(f)
            if d is None or "name" not in d:
                continue
            d["_filename"] = os.path.basename(p)
            disorders.append(d)
        except Exception as e:
            print(f"[WARN] {p}: {e}", file=sys.stderr)
    return disorders


def mechanism_descriptions(d: dict) -> list[str]:
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
# Structured queries (same logic as compute_ground_truth.py)
# ---------------------------------------------------------------------------

def q1_structured(disorders):
    pattern = re.compile(r"tgf.?beta|tgf-?b|transforming growth factor.?beta", re.IGNORECASE)
    matching = sorted(
        d["name"] for d in disorders
        if any(pattern.search(t) for t in mechanism_descriptions(d))
    )
    return {"count": len(matching), "diseases": matching}


def q2_structured(disorders):
    matching = sorted(d["name"] for d in disorders if d.get("category") == "Mendelian")
    return {"count": len(matching), "diseases": matching}


def q3_structured(disorders):
    pattern = re.compile(r"wnt|beta.?catenin|\u03b2.?catenin", re.IGNORECASE)
    matching = sorted(
        d["name"] for d in disorders
        if any(pattern.search(t) for t in mechanism_descriptions(d))
    )
    return {"count": len(matching), "diseases": matching}


def q4_structured(disorders):
    results = sorted(
        d["name"] for d in disorders
        if d.get("pathophysiology") and not (d.get("treatments") or [])
    )
    return {"count": len(results), "diseases": results}


def q5_structured(disorders):
    results = sorted(d["name"] for d in disorders if not (d.get("genetic") or []))
    return {"count": len(results), "diseases": results}


def _has_mondo(dt) -> bool:
    if not dt or not isinstance(dt, dict):
        return False
    term = dt.get("term") or {}
    if isinstance(term, dict):
        return term.get("id", "").startswith("MONDO:")
    return False


def q6_structured(disorders):
    with_mondo = sorted(d["name"] for d in disorders if _has_mondo(d.get("disease_term")))
    without_mondo = sorted(d["name"] for d in disorders if not _has_mondo(d.get("disease_term")))
    return {
        "count_with_mondo": len(with_mondo),
        "count_without_mondo": len(without_mondo),
        "total": len(disorders),
        "with_mondo_diseases": with_mondo,
        "without_mondo_diseases": without_mondo,
    }


def q7_structured(disorders):
    counts = [(d["name"], len(d.get("pathophysiology") or [])) for d in disorders]
    counts.sort(key=lambda x: (-x[1], x[0]))
    top5 = [{"name": n, "count": c} for n, c in counts[:5]]
    return {"ranking": top5}


def q8_structured(disorders):
    cat_counts = collections.Counter(d.get("category", "(none)") for d in disorders)
    top3 = [{"category": cat, "count": n} for cat, n in cat_counts.most_common(3)]
    return {"top3": top3}


def q9_structured(disorders):
    def count_pmids(d):
        text = yaml.dump(d)
        return len(re.findall(r"PMID:\d+", text))

    counts = [(d["name"], count_pmids(d)) for d in disorders]
    counts.sort(key=lambda x: (-x[1], x[0]))
    top5 = [{"name": n, "total_citations": c} for n, c in counts[:5]]
    return {"ranking": top5}


def q10_structured(disorders):
    cat_counts = collections.Counter(d.get("category", "(none)") for d in disorders)
    distribution = sorted(
        [{"category": cat, "count": n} for cat, n in cat_counts.items()],
        key=lambda x: -x["count"],
    )
    return {"total_diseases": len(disorders), "distribution": distribution}


def q11_structured(_disorders):
    """Q11: TypeDB graph traversal — diseases with FGFR3 in gene annotations."""
    from typedb.driver import TransactionType
    driver = get_typedb_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query('''
                match
                  $d isa disease, has name $dn;
                  (disease: $d, pathophysiology: $p) isa pathophysiology-rel;
                  (pathophysiology: $p, genedescriptor: $gd) isa gene;
                  $gd has preferred-term $pt;
                  $pt == "FGFR3";
                fetch { "disease": $dn };
            ''').resolve())
        diseases = sorted(set(r["disease"] for r in results))
        return {"count": len(diseases), "diseases": diseases}
    finally:
        driver.close()


def q12_structured(_disorders):
    """Q12: TypeDB cross-tier NOT EXISTS — HPO phenotypes but no genetic entries."""
    from typedb.driver import TransactionType
    driver = get_typedb_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            has_hpo = set(
                r["disease"] for r in tx.query('''
                    match
                      $d isa disease, has name $dn;
                      (disease: $d, phenotype: $ph) isa phenotypes;
                      (phenotype: $ph, phenotypedescriptor: $pd) isa phenotype-term;
                    fetch { "disease": $dn };
                ''').resolve()
            )
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            has_genetic = set(
                r["disease"] for r in tx.query('''
                    match
                      $d isa disease, has name $dn;
                      (disease: $d, genetic: $g) isa genetic-rel;
                    fetch { "disease": $dn };
                ''').resolve()
            )
        result = sorted(has_hpo - has_genetic)
        return {"count": len(result), "diseases": result}
    finally:
        driver.close()


def q13_structured(_disorders):
    """Q13: TypeDB phenotype aggregation — top 5 by HPO phenotype count."""
    from collections import Counter
    from typedb.driver import TransactionType
    driver = get_typedb_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query('''
                match
                  $d isa disease, has name $dn;
                  (disease: $d, phenotype: $ph) isa phenotypes;
                  (phenotype: $ph, phenotypedescriptor: $pd) isa phenotype-term;
                fetch { "disease": $dn };
            ''').resolve())
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
                # Truncate long lists for the prompt; the result itself has the full list
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
        description="Run DisMech benchmark under structured condition"
    )
    parser.add_argument(
        "--questions-file",
        default=str(Path(__file__).parent.parent / "questions.json"),
    )
    parser.add_argument("--disorders-dir", default=DEFAULT_DISORDERS_DIR)
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

    print(f"[info] Loading disorders from {args.disorders_dir}...", file=sys.stderr)
    disorders = load_disorders(args.disorders_dir)
    print(f"[info] {len(disorders)} disorders loaded", file=sys.stderr)

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
            print(f"  [query] Running structured query...", file=sys.stderr)
            structured_result = QUERY_FUNCTIONS[qid](disorders)
            result_text = format_result_for_prompt(qid, structured_result)

            # Format answer with Claude (optional — falls back gracefully without API key)
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
        time.sleep(0.3)

    print("\n[done] Structured condition complete", file=sys.stderr)


if __name__ == "__main__":
    main()
