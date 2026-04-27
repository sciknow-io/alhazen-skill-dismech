"""
score.py
--------
Score benchmark results against ground truth for both conditions.

Scoring rules by question:
  Q1-Q3 (exact_count):       1.0 if exact, 0.5 if within 15%, 0.0 otherwise
  Q4 (partial_list):         |names in response ∩ ground truth| / |ground truth| (Jaccard recall)
                             Hallucination penalty: names_in_response_not_in_dismech / names_in_response
  Q5 (exact_count):          Same as Q1-Q3
  Q6 (exact_count):          Checks count_with_mondo and count_without_mondo — average of both
  Q7 (exact_ranked_list):    Correct if top-5 names + counts match exactly; partial by overlap
  Q8 (exact_ranked_list):    Correct if top-3 categories + counts match exactly; partial by overlap
  Q9 (exact_ranked_list):    Correct if top-5 names + citation counts match exactly; partial by overlap
  Q10 (exact_distribution):  Checks if all category counts match; partial by fraction correct

Outputs:
  results/scores.json

Usage:
    python score.py \
        [--ground-truth-file ../ground_truth.json] \
        [--results-dir ../results] \
        [--disorders-dir /path/to/dismech/kb/disorders]
"""

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_DISORDERS_DIR = os.getenv("DISMECH_DISORDERS_DIR", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_number(text: str) -> int | None:
    """Extract the first integer from a text response."""
    # Look for explicit digit sequences, ignoring ordinals (1st, 2nd)
    matches = re.findall(r"\b(\d{1,6})\b", text.replace(",", ""))
    for m in matches:
        n = int(m)
        if n > 0:
            return n
    return None


def load_dismech_names(disorders_dir: str) -> set[str]:
    """Load all disease names from DisMech YAML files for hallucination detection."""
    import yaml
    names = set()
    for p in glob.glob(os.path.join(disorders_dir, "*.yaml")):
        if ".history." in os.path.basename(p):
            continue
        try:
            with open(p) as f:
                d = yaml.safe_load(f)
            if d and "name" in d:
                names.add(d["name"].lower().strip())
        except Exception:
            pass
    return names


def normalize_name(name: str) -> str:
    return name.lower().strip().rstrip(".")


def extract_names_from_response(text: str, known_names: set[str]) -> list[str]:
    """
    Extract disease names mentioned in a text response.
    We match against the known DisMech name set (case-insensitive).
    """
    text_lower = text.lower()
    found = []
    for name in known_names:
        if name in text_lower:
            found.append(name)
    return found


def score_exact_count(response: str, gt_count: int) -> float:
    """Score 1.0 exact, 0.5 within 15%, 0.0 otherwise."""
    predicted = extract_number(response)
    if predicted is None:
        return 0.0
    if predicted == gt_count:
        return 1.0
    if gt_count > 0 and abs(predicted - gt_count) / gt_count <= 0.15:
        return 0.5
    return 0.0


def score_partial_list(response: str, gt_diseases: list[str], all_names: set[str]) -> dict:
    """Jaccard recall of disease names, plus hallucination rate."""
    gt_set = {normalize_name(n) for n in gt_diseases}
    found = extract_names_from_response(response, all_names)
    found_set = {normalize_name(n) for n in found}

    recall = len(gt_set & found_set) / len(gt_set) if gt_set else 0.0
    precision = len(gt_set & found_set) / len(found_set) if found_set else 1.0
    hallucination_rate = len(found_set - gt_set) / len(found_set) if found_set else 0.0

    return {
        "score": round(recall, 4),
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "hallucination_rate": round(hallucination_rate, 4),
        "gt_count": len(gt_set),
        "found_count": len(found_set),
        "correct_count": len(gt_set & found_set),
    }


def score_ranked_list_names(response: str, gt_ranking: list[dict], name_key: str,
                             count_key: str | None, all_names: set[str]) -> dict:
    """
    Score a ranked-list question.
    - 1.0 if all top-N names match exactly (order ignored for partial credit)
    - Partial: fraction of ground-truth names present in response
    - Count bonus: for each correct name, +0.5 if count also matches
    """
    gt_names = [normalize_name(item[name_key]) for item in gt_ranking]
    gt_counts = {normalize_name(item[name_key]): item.get(count_key) for item in gt_ranking} if count_key else {}

    found = extract_names_from_response(response, all_names)
    found_set = {normalize_name(n) for n in found}

    gt_set = set(gt_names)
    name_overlap = gt_set & found_set
    name_recall = len(name_overlap) / len(gt_set) if gt_set else 0.0

    # Check count accuracy for found names
    count_score = 0.0
    if count_key:
        for name in name_overlap:
            expected_count = gt_counts.get(name)
            if expected_count is not None:
                # Extract number near the name in the response
                # Simple heuristic: look for the number within 50 chars of the name
                pattern = re.compile(
                    re.escape(name) + r".{0,60}?(\d+)|(\d+).{0,20}?" + re.escape(name),
                    re.IGNORECASE
                )
                m = pattern.search(response.lower())
                found_count = None
                if m:
                    found_count = int(m.group(1) or m.group(2))
                if found_count == expected_count:
                    count_score += 1.0
        count_score = count_score / len(name_overlap) if name_overlap else 0.0
    else:
        count_score = 1.0  # no counts to check

    # Composite: name recall weighted 70%, count accuracy 30%
    composite = 0.7 * name_recall + 0.3 * count_score

    return {
        "score": round(composite, 4),
        "name_recall": round(name_recall, 4),
        "count_accuracy": round(count_score, 4),
        "gt_count": len(gt_set),
        "found_count": len(found_set),
        "correct_names": sorted(name_overlap),
    }


def score_category_distribution(response: str, gt_distribution: list[dict]) -> dict:
    """
    Score Q10 (full category distribution).
    Fraction of categories whose count Claude correctly stated.
    """
    correct = 0
    total = len(gt_distribution)
    for item in gt_distribution:
        cat = item["category"]
        count = item["count"]
        # Look for both the category name and its count near each other
        pattern = re.compile(
            re.escape(cat.lower()) + r".{0,60}?(\d+)|(\d+).{0,30}?" + re.escape(cat.lower()),
            re.IGNORECASE
        )
        m = pattern.search(response.lower())
        if m:
            found_count = int(m.group(1) or m.group(2))
            if found_count == count:
                correct += 1

    return {
        "score": round(correct / total, 4) if total > 0 else 0.0,
        "correct_categories": correct,
        "total_categories": total,
    }


# ---------------------------------------------------------------------------
# Per-question scoring — structured condition (direct JSON comparison)
# ---------------------------------------------------------------------------

def score_exact_count_direct(result_count: int, gt_count: int) -> float:
    if result_count == gt_count:
        return 1.0
    if gt_count > 0 and abs(result_count - gt_count) / gt_count <= 0.15:
        return 0.5
    return 0.0


def score_structured_question(qid: str, structured_result: dict, gt: dict, all_names: set[str]) -> dict:
    """Score the structured condition by comparing JSON dicts directly — no regex."""
    answer = gt.get("answer", {})

    if qid in ("Q1", "Q2", "Q3", "Q5", "Q11", "Q12"):
        gt_count = answer["count"]
        result_count = structured_result.get("count", -1)
        s = score_exact_count_direct(result_count, gt_count)
        return {"score": s, "gt_count": gt_count, "result_count": result_count, "method": "exact_count_direct"}

    elif qid == "Q4":
        gt_diseases = {normalize_name(n) for n in answer.get("diseases", [])}
        result_diseases = {normalize_name(n) for n in structured_result.get("diseases", [])}
        recall = len(gt_diseases & result_diseases) / len(gt_diseases) if gt_diseases else 0.0
        precision = len(gt_diseases & result_diseases) / len(result_diseases) if result_diseases else 1.0
        hallucination_rate = len(result_diseases - gt_diseases) / len(result_diseases) if result_diseases else 0.0
        return {
            "score": round(recall, 4),
            "recall": round(recall, 4),
            "precision": round(precision, 4),
            "hallucination_rate": round(hallucination_rate, 4),
            "gt_count": len(gt_diseases),
            "found_count": len(result_diseases),
            "correct_count": len(gt_diseases & result_diseases),
            "method": "partial_list_direct",
        }

    elif qid == "Q6":
        gt_with = answer["count_with_mondo"]
        gt_without = answer["count_without_mondo"]
        result_with = structured_result.get("count_with_mondo", -1)
        result_without = structured_result.get("count_without_mondo", -1)
        s_with = score_exact_count_direct(result_with, gt_with)
        s_without = score_exact_count_direct(result_without, gt_without)
        avg = (s_with + s_without) / 2
        return {
            "score": round(avg, 4),
            "gt_with_mondo": gt_with, "result_with_mondo": result_with,
            "gt_without_mondo": gt_without, "result_without_mondo": result_without,
            "method": "dual_exact_count_direct",
        }

    elif qid in ("Q7", "Q9", "Q13"):
        count_key = "total_citations" if qid == "Q9" else "count"
        gt_ranking = answer.get("ranking", [])
        result_ranking = structured_result.get("ranking", [])
        gt_names = {normalize_name(item["name"]) for item in gt_ranking}
        gt_counts = {normalize_name(item["name"]): item.get(count_key) for item in gt_ranking}
        result_names = {normalize_name(item["name"]) for item in result_ranking}
        result_counts = {normalize_name(item["name"]): item.get(count_key) for item in result_ranking}
        overlap = gt_names & result_names
        name_recall = len(overlap) / len(gt_names) if gt_names else 0.0
        count_correct = sum(1 for n in overlap if gt_counts.get(n) == result_counts.get(n))
        count_score = count_correct / len(overlap) if overlap else 0.0
        composite = 0.7 * name_recall + 0.3 * count_score
        return {
            "score": round(composite, 4),
            "name_recall": round(name_recall, 4),
            "count_accuracy": round(count_score, 4),
            "gt_count": len(gt_names),
            "found_count": len(result_names),
            "correct_names": sorted(overlap),
            "method": "ranked_list_direct",
        }

    elif qid == "Q8":
        gt_dist = answer.get("top3", [])
        result_dist = structured_result.get("top3", [])
        result_map = {item["category"]: item["count"] for item in result_dist}
        correct = sum(1 for item in gt_dist if result_map.get(item["category"]) == item["count"])
        return {
            "score": round(correct / len(gt_dist), 4) if gt_dist else 0.0,
            "correct_categories": correct,
            "total_categories": len(gt_dist),
            "method": "ranked_categories_direct",
        }

    elif qid == "Q10":
        gt_dist = answer.get("distribution", [])
        result_dist = structured_result.get("distribution", [])
        result_map = {item["category"]: item["count"] for item in result_dist}
        correct = sum(1 for item in gt_dist if result_map.get(item["category"]) == item["count"])
        return {
            "score": round(correct / len(gt_dist), 4) if gt_dist else 0.0,
            "correct_categories": correct,
            "total_categories": len(gt_dist),
            "method": "full_distribution_direct",
        }

    return {"score": 0.0, "method": "unknown_direct"}


# ---------------------------------------------------------------------------
# Per-question scoring — RAG condition (text response parsing)
# ---------------------------------------------------------------------------

def score_question(qid: str, response: str, gt: dict, all_names: set[str]) -> dict:
    answer = gt.get("answer", {})

    if qid == "Q1":
        s = score_exact_count(response, answer["count"])
        return {"score": s, "gt_count": answer["count"], "method": "exact_count"}

    elif qid == "Q2":
        s = score_exact_count(response, answer["count"])
        return {"score": s, "gt_count": answer["count"], "method": "exact_count"}

    elif qid == "Q3":
        s = score_exact_count(response, answer["count"])
        return {"score": s, "gt_count": answer["count"], "method": "exact_count"}

    elif qid == "Q4":
        result = score_partial_list(response, answer["diseases"], all_names)
        result["method"] = "partial_list"
        return result

    elif qid == "Q5":
        s = score_exact_count(response, answer["count"])
        return {"score": s, "gt_count": answer["count"], "method": "exact_count"}

    elif qid == "Q6":
        s_with = score_exact_count(response, answer["count_with_mondo"])
        s_without = score_exact_count(response, answer["count_without_mondo"])
        avg = (s_with + s_without) / 2
        return {
            "score": round(avg, 4),
            "gt_with_mondo": answer["count_with_mondo"],
            "gt_without_mondo": answer["count_without_mondo"],
            "method": "dual_exact_count",
        }

    elif qid == "Q7":
        result = score_ranked_list_names(
            response, answer["ranking"], "name", "count", all_names
        )
        result["method"] = "ranked_list_with_counts"
        return result

    elif qid == "Q8":
        # Categories are not disease names — check counts by category keyword
        gt_dist = answer["top3"]
        return score_category_distribution(response, gt_dist) | {"method": "ranked_categories"}

    elif qid == "Q9":
        result = score_ranked_list_names(
            response, answer["ranking"], "name", "total_citations", all_names
        )
        result["method"] = "ranked_list_with_counts"
        return result

    elif qid == "Q10":
        result = score_category_distribution(response, answer["distribution"])
        result["method"] = "full_distribution"
        return result

    elif qid == "Q11":
        s = score_exact_count(response, answer["count"])
        return {"score": s, "gt_count": answer["count"], "method": "exact_count"}

    elif qid == "Q12":
        s = score_exact_count(response, answer["count"])
        return {"score": s, "gt_count": answer["count"], "method": "exact_count"}

    elif qid == "Q13":
        result = score_ranked_list_names(
            response, answer["ranking"], "name", "count", all_names
        )
        result["method"] = "ranked_list_with_counts"
        return result

    return {"score": 0.0, "method": "unknown"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Score DisMech benchmark results")
    parser.add_argument(
        "--ground-truth-file",
        default=str(Path(__file__).parent.parent / "ground_truth.json"),
    )
    parser.add_argument(
        "--results-dir",
        default=str(Path(__file__).parent.parent / "results"),
    )
    parser.add_argument("--disorders-dir", default=DEFAULT_DISORDERS_DIR)
    args = parser.parse_args()

    with open(args.ground_truth_file) as f:
        ground_truth = json.load(f)

    print(f"[info] Loading DisMech disease names for hallucination detection...", file=sys.stderr)
    all_names = load_dismech_names(args.disorders_dir)
    print(f"[info] {len(all_names)} disease names loaded", file=sys.stderr)

    scores = {}

    for qid in ["Q1","Q2","Q3","Q4","Q5","Q6","Q7","Q8","Q9","Q10","Q11","Q12","Q13"]:
        gt = ground_truth.get(qid, {})
        qdir = os.path.join(args.results_dir, qid)
        scores[qid] = {}

        for condition in ["rag", "structured"]:
            run_path = os.path.join(qdir, f"{condition}_run1.json")
            if not os.path.exists(run_path):
                print(f"[skip] {qid} {condition}: no run file", file=sys.stderr)
                scores[qid][condition] = {"score": None, "method": "missing"}
                continue

            with open(run_path) as f:
                run_data = json.load(f)

            structured_result = run_data.get("structured_result")
            if condition == "structured" and structured_result is not None:
                result = score_structured_question(qid, structured_result, gt, all_names)
            else:
                response = run_data.get("response", "")
                result = score_question(qid, response, gt, all_names)
            scores[qid][condition] = result

            s = result.get("score")
            s_str = f"{s:.3f}" if s is not None else "N/A"
            print(
                f"  {qid} [{condition:10s}] score={s_str}"
                f"  method={result.get('method','')}",
                file=sys.stderr,
            )

    # Save scores
    out_path = os.path.join(args.results_dir, "scores.json")
    with open(out_path, "w") as f:
        json.dump(scores, f, indent=2)
    print(f"\n[done] scores → {out_path}", file=sys.stderr)

    # Print summary table
    print("\n=== Summary ===", file=sys.stderr)
    print(f"{'QID':5} {'Category':22} {'RAG':8} {'Structured':12}", file=sys.stderr)
    print("-" * 55, file=sys.stderr)

    cat_names = {
        "Q1": "pathway_aggregation", "Q2": "pathway_aggregation", "Q3": "pathway_aggregation",
        "Q4": "negative_space", "Q5": "negative_space", "Q6": "negative_space",
        "Q7": "ranking", "Q8": "ranking", "Q9": "ranking", "Q10": "ranking",
        "Q11": "pathway_aggregation", "Q12": "negative_space", "Q13": "ranking",
    }
    for qid in ["Q1","Q2","Q3","Q4","Q5","Q6","Q7","Q8","Q9","Q10","Q11","Q12","Q13"]:
        rag_score = scores[qid].get("rag", {}).get("score")
        str_score = scores[qid].get("structured", {}).get("score")
        rag_str = f"{rag_score:.3f}" if rag_score is not None else "N/A"
        str_str = f"{str_score:.3f}" if str_score is not None else "N/A"
        print(f"  {qid:4} {cat_names[qid]:22} {rag_str:8} {str_str:12}", file=sys.stderr)

    # Category means
    cat_groups = {
        "pathway_aggregation": ["Q1","Q2","Q3","Q11"],
        "negative_space": ["Q4","Q5","Q6","Q12"],
        "ranking": ["Q7","Q8","Q9","Q10","Q13"],
    }
    print("\n=== Category Means ===", file=sys.stderr)
    for cat, qids in cat_groups.items():
        rag_scores = [scores[q].get("rag", {}).get("score") for q in qids if scores[q].get("rag", {}).get("score") is not None]
        str_scores = [scores[q].get("structured", {}).get("score") for q in qids if scores[q].get("structured", {}).get("score") is not None]
        rag_mean = sum(rag_scores)/len(rag_scores) if rag_scores else None
        str_mean = sum(str_scores)/len(str_scores) if str_scores else None
        rag_str = f"{rag_mean:.3f}" if rag_mean is not None else "N/A"
        str_str = f"{str_mean:.3f}" if str_mean is not None else "N/A"
        print(f"  {cat:22} RAG={rag_str:8} Structured={str_str:12}", file=sys.stderr)


if __name__ == "__main__":
    main()
