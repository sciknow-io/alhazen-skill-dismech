"""
collect_pmids.py
----------------
Extract all unique PMIDs referenced in DisMech YAML disorder files, fetch
their PubMed abstracts via the NCBI Entrez efetch API, and write them to disk.

Outputs (inside --corpus-dir):
  abstracts/{pmid}.txt      — plain text "Title\\n\\nAbstract" per PMID
  manifest.json             — { pmid: { title, abstract, diseases: [...] } }

Usage:
    python collect_pmids.py \
        --disorders-dir /path/to/dismech/kb/disorders \
        --corpus-dir    ../corpus

The script is idempotent: already-fetched PMIDs are skipped on re-run.

Environment:
    NCBI_API_KEY   (optional) raises rate limit from 3 → 10 req/sec
"""

import argparse
import glob
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
import yaml

# ---------------------------------------------------------------------------
# NCBI configuration (mirrored from scientific_literature.py)
# ---------------------------------------------------------------------------

NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
HEADERS = {"User-Agent": "dismech-benchmark/1.0 (mailto:gully@sciknow.io)"}
EFETCH_BATCH_SIZE = 200
NCBI_RATE_LIMIT = 0.12 if NCBI_API_KEY else 0.34   # sec between requests


# ---------------------------------------------------------------------------
# YAML helpers
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
            d = yaml.safe_load(open(p, encoding="utf-8"))
            if d and "name" in d:
                d["_filename"] = os.path.basename(p)
                disorders.append(d)
        except Exception as e:
            print(f"[WARN] {p}: {e}", file=sys.stderr)
    return disorders


def extract_pmids_from_disorder(d: dict) -> list[str]:
    """Return all raw PMID numbers (no 'PMID:' prefix) found in the YAML."""
    raw = yaml.dump(d)
    return PMID_RE.findall(raw)


# ---------------------------------------------------------------------------
# PubMed fetch (adapted from scientific_literature.py)
# ---------------------------------------------------------------------------

def _parse_pubmed_xml(xml_text: str) -> list[dict]:
    papers = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    for article in root.findall(".//PubmedArticle"):
        medline = article.find(".//MedlineCitation")
        if medline is None:
            continue
        pmid_el = medline.find("PMID")
        pmid = pmid_el.text if pmid_el is not None else None
        art = medline.find("Article")
        if art is None:
            continue
        title_el = art.find("ArticleTitle")
        title = "".join(title_el.itertext()) if title_el is not None else ""
        # Collect all AbstractText sections (structured abstracts have multiple)
        abstract_parts = []
        for ab in art.findall(".//AbstractText"):
            label = ab.get("Label")
            text = "".join(ab.itertext()).strip()
            if label:
                abstract_parts.append(f"{label}: {text}")
            elif text:
                abstract_parts.append(text)
        abstract = "\n".join(abstract_parts)
        papers.append({"pmid": pmid, "title": title.strip(), "abstract": abstract})
    return papers


def efetch_batch(pmids: list[str]) -> list[dict]:
    """Fetch PubMed records for a batch of PMIDs via POST."""
    data = {
        "db": "pubmed",
        "retmode": "xml",
        "rettype": "abstract",
        "id": ",".join(pmids),
    }
    if NCBI_API_KEY:
        data["api_key"] = NCBI_API_KEY
    r = requests.post(
        f"{NCBI_BASE}/efetch.fcgi",
        data=data,
        headers=HEADERS,
        timeout=60,
    )
    r.raise_for_status()
    return _parse_pubmed_xml(r.text)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Collect PubMed abstracts for DisMech PMIDs")
    parser.add_argument(
        "--disorders-dir",
        default=os.getenv("DISMECH_DISORDERS_DIR", ""),
    )
    parser.add_argument(
        "--corpus-dir",
        default=str(Path(__file__).parent.parent / "corpus"),
    )
    parser.add_argument(
        "--max-pmids",
        type=int,
        default=0,
        help="Limit for testing (0 = no limit)",
    )
    args = parser.parse_args()

    abstracts_dir = os.path.join(args.corpus_dir, "abstracts")
    os.makedirs(abstracts_dir, exist_ok=True)
    manifest_path = os.path.join(args.corpus_dir, "manifest.json")

    # Load existing manifest for idempotency
    manifest: dict[str, dict] = {}
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)
    print(f"[info] {len(manifest)} PMIDs already in manifest", file=sys.stderr)

    # Load disorders and build PMID → disease mapping
    print("[info] Loading disorders...", file=sys.stderr)
    disorders = load_disorders(args.disorders_dir)
    print(f"[info] {len(disorders)} disorders loaded", file=sys.stderr)

    pmid_to_diseases: dict[str, list[str]] = {}
    for d in disorders:
        for pmid in set(extract_pmids_from_disorder(d)):
            pmid_to_diseases.setdefault(pmid, []).append(d["name"])

    all_pmids = sorted(pmid_to_diseases.keys())
    print(f"[info] {len(all_pmids)} unique PMIDs found across corpus", file=sys.stderr)

    # Determine which PMIDs need fetching
    to_fetch = [p for p in all_pmids if p not in manifest]
    if args.max_pmids:
        to_fetch = to_fetch[:args.max_pmids]
    print(f"[info] {len(to_fetch)} PMIDs to fetch", file=sys.stderr)

    # Fetch in batches
    fetched = 0
    errors = 0
    for i in range(0, len(to_fetch), EFETCH_BATCH_SIZE):
        batch = to_fetch[i:i + EFETCH_BATCH_SIZE]
        batch_num = i // EFETCH_BATCH_SIZE + 1
        total_batches = (len(to_fetch) + EFETCH_BATCH_SIZE - 1) // EFETCH_BATCH_SIZE
        print(f"[info] Batch {batch_num}/{total_batches} ({len(batch)} PMIDs)...",
              file=sys.stderr, end=" ", flush=True)
        try:
            papers = efetch_batch(batch)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            errors += len(batch)
            time.sleep(1.0)
            continue

        for paper in papers:
            pmid = paper["pmid"]
            if not pmid:
                continue
            # Write abstract text file
            txt_path = os.path.join(abstracts_dir, f"{pmid}.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(f"{paper['title']}\n\n{paper['abstract']}")
            # Update manifest
            manifest[pmid] = {
                "title": paper["title"],
                "abstract": paper["abstract"],
                "diseases": pmid_to_diseases.get(pmid, []),
            }
            fetched += 1

        print(f"got {len(papers)} records", file=sys.stderr)

        # Save manifest after each batch (crash-safe)
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        if i + EFETCH_BATCH_SIZE < len(to_fetch):
            time.sleep(NCBI_RATE_LIMIT)

    # Final stats
    print(f"\n[done] fetched={fetched}, errors={errors}", file=sys.stderr)
    print(f"[done] manifest has {len(manifest)} entries → {manifest_path}", file=sys.stderr)
    print(f"[done] abstracts/ has {len(os.listdir(abstracts_dir))} files", file=sys.stderr)

    # Write disease-level corpus texts for embedding (mechanism descriptions)
    mech_corpus_path = os.path.join(args.corpus_dir, "mechanism_texts.jsonl")
    disease_corpus_path = os.path.join(args.corpus_dir, "disease_descriptions.jsonl")

    with open(mech_corpus_path, "w") as fm, open(disease_corpus_path, "w") as fd:
        for d in disorders:
            name = d.get("name", "")
            # Disease description
            desc = d.get("description", "")
            if desc:
                fd.write(json.dumps({
                    "id": f"desc_{name}",
                    "disease": name,
                    "text": f"{name}: {desc}",
                    "source_type": "disease_description",
                }) + "\n")
            # Each mechanism description
            for mech in (d.get("pathophysiology") or []):
                if not isinstance(mech, dict):
                    continue
                mname = mech.get("name", "")
                mdesc = mech.get("description", "")
                if mdesc:
                    fm.write(json.dumps({
                        "id": f"mech_{name}_{mname}",
                        "disease": name,
                        "mechanism": mname,
                        "text": f"{name} — {mname}: {mdesc}",
                        "source_type": "mechanism_description",
                    }) + "\n")

    print(f"[done] mechanism_texts.jsonl and disease_descriptions.jsonl written", file=sys.stderr)


if __name__ == "__main__":
    main()
