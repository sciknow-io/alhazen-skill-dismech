"""
extract_enriched_texts.py
--------------------------
Query the TypeDB dismech database to extract phenotype, treatment, and genetic
description texts into JSONL corpus files for RAG indexing.

Produces three files in the corpus directory:
  corpus/phenotype_texts.jsonl   -- one entry per phenotype entity
  corpus/treatment_texts.jsonl   -- one entry per treatment entity
  corpus/genetic_texts.jsonl     -- one entry per genetic entry entity

Each line is a JSON object:
  {
    "logical_id": "<unique stable id>",
    "text":       "<name>: <description>",
    "payload":    {source_type, disease, name, ...}
  }

Usage:
    python extract_enriched_texts.py \
        [--corpus-dir ../corpus] \
        [--typedb-host localhost] \
        [--typedb-port 1729] \
        [--typedb-database dismech]
"""

import argparse
import json
import os
import sys
from pathlib import Path

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "dismech")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")


def get_driver():
    from typedb.driver import Credentials, DriverOptions, TypeDB
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


def slug(s: str, max_len: int = 60) -> str:
    """Make a safe slug for use in logical IDs."""
    return s[:max_len].replace(" ", "_").replace("/", "_").replace(":", "_")


def extract_phenotype_texts(driver) -> list[dict]:
    from typedb.driver import TransactionType
    items = []
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        # Fetch phenotypes that have a phenotype-term link (i.e. have HPO annotation)
        results = list(tx.query('''
            match
              $d isa disease, has name $dn;
              (disease: $d, phenotype: $ph) isa phenotypes;
              $ph has name $pn;
            fetch { "disease": $dn, "name": $pn };
        ''').resolve())

    # Also try to get descriptions and HPO IDs separately
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        desc_results = list(tx.query('''
            match
              $d isa disease, has name $dn;
              (disease: $d, phenotype: $ph) isa phenotypes;
              $ph has name $pn;
              $ph has description $pd;
            fetch { "disease": $dn, "name": $pn, "description": $pd };
        ''').resolve())
    desc_map = {(r["disease"], r["name"]): r["description"] for r in desc_results}

    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        hpo_results = list(tx.query('''
            match
              $d isa disease, has name $dn;
              (disease: $d, phenotype: $ph) isa phenotypes;
              $ph has name $pn;
              (phenotype: $ph, phenotypedescriptor: $pd) isa phenotype-term;
              (descriptor: $pd, term: $t) isa term-rel;
              $t has id $tid;
            fetch { "disease": $dn, "name": $pn, "hpo_id": $tid };
        ''').resolve())
    hpo_map = {(r["disease"], r["name"]): r["hpo_id"] for r in hpo_results}

    seen = set()
    for r in results:
        disease = r["disease"]
        name = r["name"]
        key = (disease, name)
        if key in seen:
            continue
        seen.add(key)
        desc = desc_map.get(key, "")
        hpo_id = hpo_map.get(key, "")
        text = name
        if desc:
            text = f"{name}: {desc.strip()}"
        logical_id = f"ph_{slug(disease)}_{slug(name)}"
        items.append({
            "logical_id": logical_id,
            "text": text,
            "payload": {
                "source_type": "phenotype_description",
                "disease": disease,
                "phenotype_name": name,
                "hpo_id": hpo_id,
            },
        })
    return items


def extract_treatment_texts(driver) -> list[dict]:
    from typedb.driver import TransactionType
    items = []
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        results = list(tx.query('''
            match
              $d isa disease, has name $dn;
              (disease: $d, treatment: $t) isa treatments;
              $t has name $tn;
            fetch { "disease": $dn, "name": $tn };
        ''').resolve())

    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        desc_results = list(tx.query('''
            match
              $d isa disease, has name $dn;
              (disease: $d, treatment: $t) isa treatments;
              $t has name $tn;
              $t has description $td;
            fetch { "disease": $dn, "name": $tn, "description": $td };
        ''').resolve())
    desc_map = {(r["disease"], r["name"]): r["description"] for r in desc_results}

    seen = set()
    for r in results:
        disease = r["disease"]
        name = r["name"]
        key = (disease, name)
        if key in seen:
            continue
        seen.add(key)
        desc = desc_map.get(key, "")
        text = name
        if desc:
            text = f"{name}: {desc.strip()}"
        logical_id = f"tx_{slug(disease)}_{slug(name)}"
        items.append({
            "logical_id": logical_id,
            "text": text,
            "payload": {
                "source_type": "treatment_description",
                "disease": disease,
                "treatment_name": name,
            },
        })
    return items


def extract_genetic_texts(driver) -> list[dict]:
    from typedb.driver import TransactionType
    items = []
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        results = list(tx.query('''
            match
              $d isa disease, has name $dn;
              (disease: $d, genetic: $g) isa genetic-rel;
              $g has name $gn;
            fetch { "disease": $dn, "name": $gn };
        ''').resolve())

    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        desc_results = list(tx.query('''
            match
              $d isa disease, has name $dn;
              (disease: $d, genetic: $g) isa genetic-rel;
              $g has name $gn;
              $g has features $gd;
            fetch { "disease": $dn, "name": $gn, "description": $gd };
        ''').resolve())
    desc_map = {(r["disease"], r["name"]): r["description"] for r in desc_results}

    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        assoc_results = list(tx.query('''
            match
              $d isa disease, has name $dn;
              (disease: $d, genetic: $g) isa genetic-rel;
              $g has name $gn;
              $g has association $ga;
            fetch { "disease": $dn, "name": $gn, "association": $ga };
        ''').resolve())
    assoc_map = {(r["disease"], r["name"]): r["association"] for r in assoc_results}

    seen = set()
    for r in results:
        disease = r["disease"]
        name = r["name"]
        key = (disease, name)
        if key in seen:
            continue
        seen.add(key)
        desc = desc_map.get(key, "")
        assoc = assoc_map.get(key, "")
        parts = [name]
        if assoc:
            parts.append(f"({assoc})")
        if desc:
            parts.append(desc.strip())
        text = " ".join(parts)
        logical_id = f"ge_{slug(disease)}_{slug(name)}"
        items.append({
            "logical_id": logical_id,
            "text": text,
            "payload": {
                "source_type": "genetic_description",
                "disease": disease,
                "genetic_name": name,
                "association": assoc,
            },
        })
    return items


def write_jsonl(path: str, items: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"  wrote {len(items)} items → {path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Extract enriched texts from TypeDB dismech DB into JSONL corpus files"
    )
    parser.add_argument(
        "--corpus-dir",
        default=str(Path(__file__).parent.parent / "corpus"),
    )
    parser.add_argument("--typedb-host", default=TYPEDB_HOST)
    parser.add_argument("--typedb-port", type=int, default=TYPEDB_PORT)
    parser.add_argument("--typedb-database", default=TYPEDB_DATABASE)
    args = parser.parse_args()

    os.environ["TYPEDB_HOST"] = args.typedb_host
    os.environ["TYPEDB_PORT"] = str(args.typedb_port)
    os.environ["TYPEDB_DATABASE"] = args.typedb_database

    os.makedirs(args.corpus_dir, exist_ok=True)

    print("[info] Connecting to TypeDB...", file=sys.stderr)
    driver = get_driver()

    print("[phenotypes] Extracting...", file=sys.stderr)
    phenotype_items = extract_phenotype_texts(driver)
    write_jsonl(os.path.join(args.corpus_dir, "phenotype_texts.jsonl"), phenotype_items)

    print("[treatments] Extracting...", file=sys.stderr)
    treatment_items = extract_treatment_texts(driver)
    write_jsonl(os.path.join(args.corpus_dir, "treatment_texts.jsonl"), treatment_items)

    print("[genetic] Extracting...", file=sys.stderr)
    genetic_items = extract_genetic_texts(driver)
    write_jsonl(os.path.join(args.corpus_dir, "genetic_texts.jsonl"), genetic_items)

    total = len(phenotype_items) + len(treatment_items) + len(genetic_items)
    print(f"\n[done] {total} total items across 3 corpus layers", file=sys.stderr)
    print(json.dumps({
        "success": True,
        "phenotype_texts": len(phenotype_items),
        "treatment_texts": len(treatment_items),
        "genetic_texts": len(genetic_items),
        "total": total,
    }))


if __name__ == "__main__":
    main()
