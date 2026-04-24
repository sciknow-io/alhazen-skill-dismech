"""
report.py
---------
Generate figures and a summary report from benchmark scores.

Outputs:
  results/figures/accuracy_by_question.png   — bar chart: 10 questions × 2 conditions
  results/figures/accuracy_by_category.png   — grouped bars by category
  results/report.md                          — markdown summary table

Usage:
    python report.py \
        [--scores-file ../results/scores.json] \
        [--questions-file ../questions.json] \
        [--ground-truth-file ../ground_truth.json] \
        [--output-dir ../results]

Requirements:
    matplotlib (uv add matplotlib)
"""

import argparse
import json
import os
import sys
from pathlib import Path


CATEGORY_COLORS = {
    "pathway_aggregation": ("#4878D0", "#EE854A"),   # (rag_blue, structured_orange)
    "negative_space":      ("#6ACC65", "#D65F5F"),
    "ranking":             ("#956CB4", "#8C613C"),
}

CATEGORY_LABELS = {
    "pathway_aggregation": "Cat 3: Pathway Aggregation",
    "negative_space":      "Cat 5: Negative Space",
    "ranking":             "Cat 6: Ranking",
}

CAT_NAMES = {
    "Q1": "pathway_aggregation", "Q2": "pathway_aggregation", "Q3": "pathway_aggregation",
    "Q4": "negative_space",      "Q5": "negative_space",      "Q6": "negative_space",
    "Q7": "ranking",             "Q8": "ranking",
    "Q9": "ranking",             "Q10": "ranking",
    "Q11": "pathway_aggregation", "Q12": "negative_space",    "Q13": "ranking",
}

QUESTION_ORDER = ["Q1","Q2","Q3","Q4","Q5","Q6","Q7","Q8","Q9","Q10","Q11","Q12","Q13"]


def load_json(path: str) -> dict | list:
    with open(path) as f:
        return json.load(f)


def make_accuracy_by_question(scores: dict, out_path: str) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import numpy as np
    except ImportError:
        print("[warn] matplotlib not installed — skipping figure generation", file=sys.stderr)
        return

    qids = [q for q in QUESTION_ORDER if q in scores]
    rag_vals = [scores[q].get("rag", {}).get("score") or 0.0 for q in qids]
    str_vals = [scores[q].get("structured", {}).get("score") or 0.0 for q in qids]

    x = np.arange(len(qids))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 5))

    # Color bars by category
    for i, qid in enumerate(qids):
        cat = CAT_NAMES.get(qid, "ranking")
        rag_color, str_color = CATEGORY_COLORS.get(cat, ("#4878D0", "#EE854A"))
        ax.bar(x[i] - width/2, rag_vals[i], width, color=rag_color, alpha=0.85)
        ax.bar(x[i] + width/2, str_vals[i], width, color=str_color, alpha=0.85)

    ax.set_xlabel("Question", fontsize=12)
    ax.set_ylabel("Accuracy Score (0–1)", fontsize=12)
    ax.set_title(
        "RAG vs. Structured Knowledge: Accuracy by Question\n(DisMech Benchmark — 10 questions × 2 conditions)",
        fontsize=13,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(qids)
    ax.set_ylim(0, 1.12)
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=0.8, alpha=0.5)

    # Legend: conditions
    rag_patch = mpatches.Patch(color="#4878D0", alpha=0.85, label="RAG (Voyage AI + Qdrant)")
    str_patch = mpatches.Patch(color="#EE854A", alpha=0.85, label="Structured (Python YAML query)")
    ax.legend(handles=[rag_patch, str_patch], loc="upper left")

    # Category dividers
    for x_div in [2.5, 5.5]:
        ax.axvline(x_div, color="black", linewidth=0.6, linestyle=":", alpha=0.4)

    # Category labels above bars
    ax.text(1.0, 1.07, "Cat 3\nAggregation", ha="center", fontsize=8, color="gray")
    ax.text(4.0, 1.07, "Cat 5\nNegative Space", ha="center", fontsize=8, color="gray")
    ax.text(8.0, 1.07, "Cat 6\nRanking", ha="center", fontsize=8, color="gray")

    plt.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[done] {out_path}", file=sys.stderr)


def make_accuracy_by_category(scores: dict, out_path: str) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return

    cat_groups = {
        "pathway_aggregation": ["Q1","Q2","Q3","Q11"],
        "negative_space":      ["Q4","Q5","Q6","Q12"],
        "ranking":             ["Q7","Q8","Q9","Q10","Q13"],
    }

    cats = list(cat_groups.keys())
    rag_means, str_means = [], []
    for cat in cats:
        qids = cat_groups[cat]
        rs = [scores[q].get("rag", {}).get("score") for q in qids if scores.get(q, {}).get("rag", {}).get("score") is not None]
        ss = [scores[q].get("structured", {}).get("score") for q in qids if scores.get(q, {}).get("structured", {}).get("score") is not None]
        rag_means.append(sum(rs)/len(rs) if rs else 0.0)
        str_means.append(sum(ss)/len(ss) if ss else 0.0)

    x = np.arange(len(cats))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x - width/2, rag_means, width, color="#4878D0", alpha=0.85, label="RAG")
    ax.bar(x + width/2, str_means, width, color="#EE854A", alpha=0.85, label="Structured")

    ax.set_ylabel("Mean Accuracy (0–1)", fontsize=12)
    ax.set_title("Mean Accuracy by Query Category", fontsize=13)
    ax.set_xticks(x)
    ax.set_xticklabels([CATEGORY_LABELS[c] for c in cats], fontsize=10)
    ax.set_ylim(0, 1.15)
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.legend()

    # Annotate gap
    for i in range(len(cats)):
        gap = str_means[i] - rag_means[i]
        ax.text(i, max(str_means[i], rag_means[i]) + 0.03,
                f"+{gap:.2f}", ha="center", fontsize=9, color="black")

    plt.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[done] {out_path}", file=sys.stderr)


def make_markdown_report(scores: dict, questions: list, ground_truth: dict, out_path: str) -> None:
    lines = [
        "# DisMech Benchmark: RAG vs. Structured Knowledge",
        "",
        "**Scope:** 13 questions × 2 conditions (RAG, Structured) — Categories 3, 5, 6",
        "",
        "## Results by Question",
        "",
        "| # | Category | Question | RAG Score | Structured Score | Gap |",
        "|---|----------|----------|-----------|-----------------|-----|",
    ]

    q_map = {q["id"]: q for q in questions}

    for qid in QUESTION_ORDER:
        q = q_map.get(qid, {})
        cat = q.get("category_name", "")
        question = q.get("question", "")[:60] + "..."
        rag_s = scores.get(qid, {}).get("rag", {}).get("score")
        str_s = scores.get(qid, {}).get("structured", {}).get("score")
        rag_str = f"{rag_s:.3f}" if rag_s is not None else "N/A"
        str_str = f"{str_s:.3f}" if str_s is not None else "N/A"
        gap_str = f"+{str_s - rag_s:.3f}" if rag_s is not None and str_s is not None else "N/A"
        lines.append(f"| {qid} | {cat} | {question} | {rag_str} | {str_str} | {gap_str} |")

    # Category summary
    lines += [
        "",
        "## Category Summary",
        "",
        "| Category | RAG Mean | Structured Mean | Gap |",
        "|----------|----------|-----------------|-----|",
    ]
    cat_groups = {
        "pathway_aggregation": ["Q1","Q2","Q3","Q11"],
        "negative_space":      ["Q4","Q5","Q6","Q12"],
        "ranking":             ["Q7","Q8","Q9","Q10","Q13"],
    }
    for cat, qids in cat_groups.items():
        rs = [scores[q].get("rag", {}).get("score") for q in qids if scores.get(q, {}).get("rag", {}).get("score") is not None]
        ss = [scores[q].get("structured", {}).get("score") for q in qids if scores.get(q, {}).get("structured", {}).get("score") is not None]
        rm = sum(rs)/len(rs) if rs else None
        sm = sum(ss)/len(ss) if ss else None
        gap = sm - rm if rm is not None and sm is not None else None
        rm_str = f"{rm:.3f}" if rm is not None else "N/A"
        sm_str = f"{sm:.3f}" if sm is not None else "N/A"
        gap_str = f"+{gap:.3f}" if gap is not None else "N/A"
        lines.append(f"| {CATEGORY_LABELS[cat]} | {rm_str} | {sm_str} | {gap_str} |")

    lines += [
        "",
        "## Ground Truth Summary",
        "",
        "| Question | Answer |",
        "|----------|--------|",
    ]
    for qid in QUESTION_ORDER:
        ans = ground_truth.get(qid, {}).get("answer", {})
        if "count" in ans:
            summary = f"count = {ans['count']}"
        elif "count_with_mondo" in ans:
            summary = f"with_mondo = {ans['count_with_mondo']}, without = {ans['count_without_mondo']}"
        elif "ranking" in ans:
            top = ans["ranking"][0] if ans["ranking"] else {}
            name = top.get("name", "?")
            cnt = top.get("count") or top.get("total_citations", "?")
            summary = f"top: {name} ({cnt})"
        elif "top3" in ans:
            summary = ", ".join(f"{x['category']} ({x['count']})" for x in ans["top3"][:3])
        elif "distribution" in ans:
            summary = f"{ans['total_diseases']} diseases, {ans['category_count']} categories"
        else:
            summary = "see ground_truth.json"
        lines.append(f"| {qid} | {summary} |")

    lines += [
        "",
        "---",
        "*Generated by report.py — DisMech benchmark harness (Apache-2.0, SciKnow.io)*",
    ]

    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[done] {out_path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Generate DisMech benchmark report")
    parser.add_argument(
        "--scores-file",
        default=str(Path(__file__).parent.parent / "results" / "scores.json"),
    )
    parser.add_argument(
        "--questions-file",
        default=str(Path(__file__).parent.parent / "questions.json"),
    )
    parser.add_argument(
        "--ground-truth-file",
        default=str(Path(__file__).parent.parent / "ground_truth.json"),
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent.parent / "results"),
    )
    args = parser.parse_args()

    scores = load_json(args.scores_file)
    questions = load_json(args.questions_file)
    ground_truth = load_json(args.ground_truth_file)

    figures_dir = os.path.join(args.output_dir, "figures")
    os.makedirs(figures_dir, exist_ok=True)

    make_accuracy_by_question(
        scores,
        os.path.join(figures_dir, "accuracy_by_question.png"),
    )
    make_accuracy_by_category(
        scores,
        os.path.join(figures_dir, "accuracy_by_category.png"),
    )
    make_markdown_report(
        scores, questions, ground_truth,
        os.path.join(args.output_dir, "report.md"),
    )

    print("\n[done] Report generated:", file=sys.stderr)
    print(f"  figures/accuracy_by_question.png", file=sys.stderr)
    print(f"  figures/accuracy_by_category.png", file=sys.stderr)
    print(f"  report.md", file=sys.stderr)


if __name__ == "__main__":
    main()
