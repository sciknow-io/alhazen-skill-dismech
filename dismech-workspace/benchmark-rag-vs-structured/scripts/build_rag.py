"""
build_rag.py
------------
Embed the DisMech benchmark corpus into Qdrant collection `dismech_benchmark`.

Three layers are embedded:
  1. PubMed abstracts — from corpus/manifest.json (title + abstract text)
  2. Mechanism descriptions — from corpus/mechanism_texts.jsonl
  3. Disease descriptions — from corpus/disease_descriptions.jsonl

The script is idempotent: existing points are not re-embedded.

Usage:
    python build_rag.py \
        --corpus-dir ../corpus \
        [--collection dismech_benchmark] \
        [--batch-size 64]

Environment:
    VOYAGE_API_KEY   — required for Voyage AI embeddings
    QDRANT_HOST      — Qdrant server host (default: localhost)
    QDRANT_PORT      — Qdrant server port (default: 6333)
"""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COLLECTION_NAME = "dismech_benchmark"
VECTOR_DIM = 1024          # voyage-4-large
VOYAGE_BATCH_SIZE = 64     # conservative batch size for large texts
QDRANT_UPSERT_BATCH = 256  # points per upsert call
UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def stable_id(logical_id: str) -> str:
    """Derive a stable UUID from a logical ID string."""
    return str(uuid.uuid5(UUID_NAMESPACE, logical_id))


def get_qdrant_client():
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        raise ImportError("qdrant-client not installed. Run: uv sync --all-extras")
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    return QdrantClient(host=host, port=port)


def ensure_collection(client, collection: str) -> None:
    from qdrant_client.models import Distance, VectorParams
    existing = {c.name for c in client.get_collections().collections}
    if collection not in existing:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        print(f"[info] Created Qdrant collection '{collection}'", file=sys.stderr)
    else:
        print(f"[info] Collection '{collection}' already exists", file=sys.stderr)


def get_existing_ids(client, collection: str, logical_ids: list[str]) -> set[str]:
    """Return the subset of logical_ids that already have points in Qdrant."""
    point_ids = [stable_id(lid) for lid in logical_ids]
    # Qdrant retrieve only supports up to 1000 IDs at a time
    existing = set()
    for i in range(0, len(point_ids), 1000):
        chunk_pids = point_ids[i:i+1000]
        chunk_lids = logical_ids[i:i+1000]
        results = client.retrieve(
            collection_name=collection,
            ids=chunk_pids,
            with_payload=False,
        )
        found_point_ids = {r.id for r in results}
        for pid, lid in zip(chunk_pids, chunk_lids):
            if pid in found_point_ids:
                existing.add(lid)
    return existing


def embed_batch(texts: list[str], input_type: str = "document") -> list[list[float]]:
    try:
        import voyageai
    except ImportError:
        raise ImportError("voyageai not installed. Run: uv sync --all-extras")
    api_key = os.getenv("VOYAGE_API_KEY", "")
    if not api_key:
        raise ValueError("VOYAGE_API_KEY environment variable not set")
    client = voyageai.Client(api_key=api_key)
    result = client.embed(texts, model="voyage-4-large", input_type=input_type)
    return result.embeddings


def embed_all(texts: list[str], batch_size: int = VOYAGE_BATCH_SIZE) -> list[list[float]]:
    all_vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        vectors = embed_batch(batch)
        all_vectors.extend(vectors)
        if (i // batch_size + 1) % 5 == 0 or i + batch_size >= len(texts):
            done = min(i + batch_size, len(texts))
            print(f"    embedded {done}/{len(texts)}", file=sys.stderr)
    return all_vectors


def upsert_points(client, collection: str, points: list[dict]) -> int:
    """Upsert a list of {id, vector, payload} dicts in batches."""
    from qdrant_client.models import PointStruct
    total = 0
    for i in range(0, len(points), QDRANT_UPSERT_BATCH):
        batch = points[i:i+QDRANT_UPSERT_BATCH]
        structs = [
            PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"])
            for p in batch
        ]
        client.upsert(collection_name=collection, points=structs)
        total += len(structs)
    return total


# ---------------------------------------------------------------------------
# Layer loaders
# ---------------------------------------------------------------------------

def load_abstracts(corpus_dir: str) -> list[dict]:
    """Load PubMed abstracts from manifest.json. Returns list of {id, text, payload}."""
    manifest_path = os.path.join(corpus_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        print(f"[warn] manifest.json not found at {manifest_path}", file=sys.stderr)
        return []
    with open(manifest_path) as f:
        manifest = json.load(f)
    items = []
    for pmid, meta in manifest.items():
        title = meta.get("title", "")
        abstract = meta.get("abstract", "")
        if not title and not abstract:
            continue
        text = f"{title}\n\n{abstract}" if abstract else title
        diseases = meta.get("diseases", [])
        items.append({
            "logical_id": f"abstract_{pmid}",
            "text": text,
            "payload": {
                "source_type": "abstract",
                "pmid": pmid,
                "title": title,
                "disease": ", ".join(diseases),
                "diseases": diseases,
                "text": text,
            },
        })
    return items


def load_jsonl(path: str) -> list[dict]:
    """Load items from a JSONL file. Returns list of {id, text, payload}."""
    if not os.path.exists(path):
        print(f"[warn] not found: {path}", file=sys.stderr)
        return []
    items = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            logical_id = obj.get("id") or obj.get("logical_id")
            text = obj["text"]
            # Handle both flat and nested payload formats
            # extract_enriched_texts.py writes {"payload": {...}}, older files are flat
            if "payload" in obj and isinstance(obj["payload"], dict):
                payload = dict(obj["payload"])
            else:
                payload = {k: v for k, v in obj.items()
                           if k not in ("text", "id", "logical_id")}
            payload["text"] = text  # Always include text in Qdrant payload
            items.append({
                "logical_id": logical_id,
                "text": text,
                "payload": payload,
            })
    return items


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build DisMech RAG index in Qdrant")
    parser.add_argument(
        "--corpus-dir",
        default=str(Path(__file__).parent.parent / "corpus"),
    )
    parser.add_argument("--collection", default=COLLECTION_NAME)
    parser.add_argument("--batch-size", type=int, default=VOYAGE_BATCH_SIZE)
    parser.add_argument(
        "--layer",
        choices=["abstracts", "mechanisms", "descriptions", "phenotypes", "treatments", "genetic", "all"],
        default="all",
        help="Which corpus layer to embed (default: all)",
    )
    args = parser.parse_args()

    def load_jsonl_if_exists(path):
        if os.path.exists(path):
            return load_jsonl(path)
        print(f"  [skip] {path} not found — run extract_enriched_texts.py first", file=sys.stderr)
        return []

    # Load corpus layers
    layers = {
        "abstracts": lambda: load_abstracts(args.corpus_dir),
        "mechanisms": lambda: load_jsonl(
            os.path.join(args.corpus_dir, "mechanism_texts.jsonl")
        ),
        "descriptions": lambda: load_jsonl(
            os.path.join(args.corpus_dir, "disease_descriptions.jsonl")
        ),
        "phenotypes": lambda: load_jsonl_if_exists(
            os.path.join(args.corpus_dir, "phenotype_texts.jsonl")
        ),
        "treatments": lambda: load_jsonl_if_exists(
            os.path.join(args.corpus_dir, "treatment_texts.jsonl")
        ),
        "genetic": lambda: load_jsonl_if_exists(
            os.path.join(args.corpus_dir, "genetic_texts.jsonl")
        ),
    }

    selected = list(layers.keys()) if args.layer == "all" else [args.layer]

    # Connect to Qdrant
    print("[info] Connecting to Qdrant...", file=sys.stderr)
    client = get_qdrant_client()
    ensure_collection(client, args.collection)

    total_upserted = 0
    total_skipped = 0

    for layer_name in selected:
        print(f"\n[{layer_name}] Loading items...", file=sys.stderr)
        items = layers[layer_name]()
        print(f"[{layer_name}] {len(items)} items loaded", file=sys.stderr)
        if not items:
            continue

        # Check which already exist
        logical_ids = [it["logical_id"] for it in items]
        print(f"[{layer_name}] Checking {len(logical_ids)} IDs against Qdrant...", file=sys.stderr)
        existing = get_existing_ids(client, args.collection, logical_ids)
        to_embed = [it for it in items if it["logical_id"] not in existing]
        skipped = len(items) - len(to_embed)
        total_skipped += skipped
        print(f"[{layer_name}] {skipped} already indexed, {len(to_embed)} to embed",
              file=sys.stderr)

        if not to_embed:
            continue

        # Embed texts
        print(f"[{layer_name}] Embedding {len(to_embed)} texts...", file=sys.stderr)
        texts = [it["text"] for it in to_embed]
        vectors = embed_all(texts, batch_size=args.batch_size)

        # Build point structs and upsert
        points = [
            {
                "id": stable_id(it["logical_id"]),
                "vector": vec,
                "payload": it["payload"],
            }
            for it, vec in zip(to_embed, vectors)
        ]
        print(f"[{layer_name}] Upserting {len(points)} points...", file=sys.stderr)
        n = upsert_points(client, args.collection, points)
        total_upserted += n
        print(f"[{layer_name}] Upserted {n} points", file=sys.stderr)

    # Final stats
    info = client.get_collection(args.collection)
    total_points = info.points_count
    print(f"\n[done] upserted={total_upserted}, skipped={total_skipped}", file=sys.stderr)
    print(f"[done] '{args.collection}' now has {total_points} total points", file=sys.stderr)


if __name__ == "__main__":
    main()
