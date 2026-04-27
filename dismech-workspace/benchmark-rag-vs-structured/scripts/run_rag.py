"""
run_rag.py
----------
Run each of the 10 benchmark questions under the RAG condition.

For each question:
  1. Embed the question text using Voyage AI
  2. Retrieve top-20 chunks from Qdrant `dismech_benchmark`
  3. Format context + question as a prompt
  4. Call Claude Sonnet 4.6 via Anthropic API
  5. Save full run record to results/{question_id}/rag_run1.json

Usage:
    python run_rag.py \
        [--questions-file ../questions.json] \
        [--results-dir ../results] \
        [--collection dismech_benchmark] \
        [--top-k 20] \
        [--question-ids Q1,Q2,Q3]   # optional: run subset

Environment:
    VOYAGE_API_KEY     — required for Voyage AI embeddings
    ANTHROPIC_API_KEY  — required for Claude API
    QDRANT_HOST        — Qdrant host (default: localhost)
    QDRANT_PORT        — Qdrant port (default: 6333)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

COLLECTION_NAME = "dismech_benchmark"
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = (
    "You are answering questions about DisMech, a curated database of rare disease "
    "mechanisms maintained by the Monarch Initiative. The database contains entries for "
    "approximately 605 diseases, each with pathophysiology mechanisms, genetic information, "
    "phenotypes, and treatments.\n\n"
    "You will be given relevant passages retrieved from the database. Use ONLY the provided "
    "context to answer the question. If you cannot determine the answer from the context, "
    "say so explicitly. Do not guess or use prior knowledge.\n\n"
    "For counting questions, give the exact number you can determine from the context. "
    "For ranking questions, rank based only on what the context tells you. "
    "For listing questions, list only diseases mentioned in the context."
)


def embed_query(text: str) -> list[float]:
    try:
        import voyageai
    except ImportError:
        raise ImportError("voyageai not installed. Run: uv sync --all-extras")
    api_key = os.getenv("VOYAGE_API_KEY", "")
    if not api_key:
        raise ValueError("VOYAGE_API_KEY not set")
    client = voyageai.Client(api_key=api_key)
    result = client.embed([text], model="voyage-4-large", input_type="query")
    return result.embeddings[0]


def retrieve_chunks(query_vector: list[float], collection: str, top_k: int) -> list[dict]:
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        raise ImportError("qdrant-client not installed. Run: uv sync --all-extras")
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    client = QdrantClient(host=host, port=port)
    results = client.query_points(
        collection_name=collection,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    )
    chunks = []
    for r in results.points:
        payload = r.payload or {}
        chunks.append({
            "score": round(r.score, 4),
            "source_type": payload.get("source_type", ""),
            "pmid": payload.get("pmid", ""),
            "disease": payload.get("disease", ""),
            "mechanism": payload.get("mechanism", ""),
            "text": payload.get("text", ""),
        })
    return chunks


def format_context(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        src = chunk["source_type"]
        header = f"[{i}] ({src})"
        if chunk.get("disease"):
            header += f" Disease: {chunk['disease']}"
        if chunk.get("mechanism"):
            header += f" | Mechanism: {chunk['mechanism']}"
        if chunk.get("pmid"):
            header += f" | PMID:{chunk['pmid']}"
        parts.append(f"{header}\n{chunk['text'].strip()}")
    return "\n\n---\n\n".join(parts)


def call_claude(question: str, context: str) -> dict:
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic not installed. Run: uv sync --all-extras")
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=api_key)
    user_message = (
        f"Context (retrieved passages from DisMech):\n\n{context}\n\n"
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


def run_question(question_meta: dict, collection: str, top_k: int) -> dict:
    qid = question_meta["id"]
    question = question_meta["question"]

    print(f"  [embed]    {qid}: embedding query...", file=sys.stderr)
    query_vector = embed_query(question)

    print(f"  [retrieve] {qid}: top-{top_k} from '{collection}'...", file=sys.stderr)
    chunks = retrieve_chunks(query_vector, collection, top_k)

    print(f"  [claude]   {qid}: calling {MODEL}...", file=sys.stderr)
    context = format_context(chunks)
    result = call_claude(question, context)

    return {
        "question_id": qid,
        "question": question,
        "category": question_meta.get("category"),
        "category_name": question_meta.get("category_name"),
        "condition": "rag",
        "model": MODEL,
        "collection": collection,
        "top_k": top_k,
        "retrieved_chunks": chunks,
        "context_length": len(context),
        "response": result["response"],
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "run_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="Run DisMech benchmark under RAG condition")
    parser.add_argument(
        "--questions-file",
        default=str(Path(__file__).parent.parent / "questions.json"),
    )
    parser.add_argument(
        "--results-dir",
        default=str(Path(__file__).parent.parent / "results"),
    )
    parser.add_argument("--collection", default=COLLECTION_NAME)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument(
        "--question-ids",
        default="",
        help="Comma-separated list of question IDs to run (default: all)",
    )
    args = parser.parse_args()

    with open(args.questions_file) as f:
        questions = json.load(f)

    if args.question_ids:
        target_ids = set(args.question_ids.split(","))
        questions = [q for q in questions if q["id"] in target_ids]

    print(f"[info] Running {len(questions)} questions under RAG condition", file=sys.stderr)

    for q in questions:
        qid = q["id"]
        out_dir = os.path.join(args.results_dir, qid)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "rag_run1.json")

        if os.path.exists(out_path):
            print(f"[skip] {qid}: {out_path} already exists", file=sys.stderr)
            continue

        print(f"\n[{qid}] {q['question'][:80]}...", file=sys.stderr)
        try:
            record = run_question(q, args.collection, args.top_k)
            with open(out_path, "w") as f:
                json.dump(record, f, indent=2)
            print(f"  [saved] {out_path}", file=sys.stderr)
            print(f"  [response preview] {record['response'][:200]}...", file=sys.stderr)
        except Exception as e:
            print(f"  [ERROR] {qid}: {e}", file=sys.stderr)
        time.sleep(0.5)  # avoid rate limit

    print("\n[done] RAG condition complete", file=sys.stderr)


if __name__ == "__main__":
    main()
