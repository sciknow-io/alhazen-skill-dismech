#!/usr/bin/env python3
"""
DisMech — Disease Mechanism Knowledge Graph CLI.

Bulk-ingests the dismech knowledge base into TypeDB 3.x and provides
query commands for exploring disease mechanisms, phenotypes, and genes.

Usage:
    python dismech.py ingest --source /path/to/dismech/kb/disorders [--max N]
    python dismech.py show-disease --name "Achondroplasia"
    python dismech.py list-diseases [--category Genetic]
    python dismech.py search --query "FGFR3 growth plate"
    python dismech.py stats
    python dismech.py serve [--port 7777]
    python dismech.py add-evidence --disease "Disease Name" --pmid 12345 --supports SUPPORT --evidence-source HUMAN_CLINICAL

TypeDB must be running with the dismech schema loaded (run alhazen_core.py init first).
"""

import argparse
import http.server
import json
import os
import sys
import threading
import urllib.parse
from pathlib import Path

import yaml
from tqdm import tqdm

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "dismech")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")


# ── TypeDB helpers ────────────────────────────────────────────────────────────


def _get_driver():
    """Return a TypeDB driver connection."""
    from typedb.driver import Credentials, DriverOptions, TypeDB
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


def _escape(s: str) -> str:
    """Escape backslashes and double-quotes for TypeQL string literals."""
    if not isinstance(s, str):
        s = str(s)
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _truncate(s: str, max_len: int = 2000) -> str:
    """Truncate a string to max_len characters."""
    if len(s) > max_len:
        return s[:max_len] + "…"
    return s


def _count_query(driver, query: str) -> int:
    """Run a reduce count query and return the integer result."""
    from typedb.driver import TransactionType
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        results = list(tx.query(query).resolve())
    if not results:
        return 0
    v = results[0].get("c")
    return v.get_integer() if v is not None else 0


# ── Ingestion ─────────────────────────────────────────────────────────────────


def _ingest_disease_file(driver, data: dict) -> dict:
    """Ingest one disorder YAML dict into TypeDB.

    Inserts three tiers per disorder:
      1. Disease entity (name @key, category, parents)
      2. DiseaseTerm descriptor (preferred-term) + disease-term relation
      3. Pathophysiology mechanisms (name, description) + pathophysiology-rel relations

    :param driver: open TypeDB driver
    :param data: parsed YAML dict for one disorder
    :return: dict with counts of inserted entities
    """
    from typedb.driver import TransactionType

    name = data.get("name", "").strip()
    if not name:
        return {"skipped": True, "reason": "no name"}

    counts = {"mechanisms": 0, "errors": []}

    # ── Tier 1: Disease entity ─────────────────────────────────────────────
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        attrs = [f'has name "{_escape(name)}"']
        if data.get("category"):
            attrs.append(f'has category "{_escape(str(data["category"]))}"')
        for parent in (data.get("parents") or []):
            if isinstance(parent, str) and parent.strip():
                attrs.append(f'has parents "{_escape(parent.strip())}"')
        for synonym in (data.get("synonyms") or []):
            if isinstance(synonym, str) and synonym.strip():
                attrs.append(f'has synonyms "{_escape(synonym.strip())}"')

        tx.query(f"insert $d isa disease, {', '.join(attrs)};").resolve()
        tx.commit()

    # ── Tier 2: DiseaseTerm (MONDO binding) ───────────────────────────────
    disease_term = data.get("disease_term")
    if disease_term and isinstance(disease_term, dict):
        preferred = disease_term.get("preferred_term", "")
        term = disease_term.get("term") or {}
        mondo_id = term.get("id", "")
        mondo_label = term.get("label", "")
        if preferred:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                q = (
                    f'match $d isa disease, has name "{_escape(name)}"; '
                    f'insert $dt isa diseasedescriptor, '
                    f'    has preferred-term "{_escape(preferred)}"; '
                    f'(disease: $d, diseasedescriptor: $dt) isa disease-term;'
                )
                if mondo_id:
                    # Insert MONDO term separately so we can link it
                    q = (
                        f'match $d isa disease, has name "{_escape(name)}"; '
                        f'insert $dt isa diseasedescriptor, '
                        f'    has preferred-term "{_escape(preferred)}"; '
                        f'(disease: $d, diseasedescriptor: $dt) isa disease-term;'
                    )
                try:
                    tx.query(q).resolve()
                    tx.commit()
                except Exception as e:
                    counts["errors"].append(f"disease-term: {e}")

    # ── Tier 3: Pathophysiology mechanisms ────────────────────────────────
    for mech in (data.get("pathophysiology") or []):
        if not isinstance(mech, dict):
            continue
        mech_name = (mech.get("name") or "").strip()
        mech_desc = (mech.get("description") or "").strip()
        if not mech_name:
            continue
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            mech_attrs = [f'has name "{_escape(mech_name)}"']
            if mech_desc:
                mech_attrs.append(f'has description "{_escape(_truncate(mech_desc))}"')
            q = (
                f'match $d isa disease, has name "{_escape(name)}"; '
                f'insert $p isa pathophysiology, {", ".join(mech_attrs)}; '
                f'(disease: $d, pathophysiology: $p) isa pathophysiology-rel;'
            )
            try:
                tx.query(q).resolve()
                tx.commit()
                counts["mechanisms"] += 1
            except Exception as e:
                counts["errors"].append(f"pathophysiology '{mech_name}': {e}")

    return counts


def cmd_ingest(args):
    """Bulk-ingest disorder YAML files from the given directory."""
    source = Path(args.source)
    if not source.is_dir():
        print(json.dumps({"success": False, "error": f"Not a directory: {source}"}))
        sys.exit(1)

    # Collect non-history YAML files
    files = sorted(p for p in source.glob("*.yaml") if not p.name.endswith(".history.yaml"))
    if args.max:
        files = files[: args.max]

    total = len(files)
    inserted = 0
    skipped = 0
    total_mechanisms = 0
    all_errors = []

    with _get_driver() as driver:
        for yaml_path in tqdm(files, desc="Ingesting", unit="disease", disable=args.quiet):
            try:
                data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    skipped += 1
                    continue
                result = _ingest_disease_file(driver, data)
                if result.get("skipped"):
                    skipped += 1
                else:
                    inserted += 1
                    total_mechanisms += result.get("mechanisms", 0)
                    if result.get("errors"):
                        all_errors.extend(result["errors"])
            except Exception as e:
                all_errors.append(f"{yaml_path.name}: {e}")
                skipped += 1

    out = {
        "success": True,
        "total_files": total,
        "inserted": inserted,
        "skipped": skipped,
        "mechanisms": total_mechanisms,
        "error_count": len(all_errors),
    }
    if all_errors and not args.quiet:
        out["errors"] = all_errors[:20]  # cap error list in output
    print(json.dumps(out))


# ── Querying ──────────────────────────────────────────────────────────────────


def _fetch_disease_names(driver) -> list[str]:
    """Return all disease names in the database."""
    from typedb.driver import TransactionType
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        results = list(tx.query('match $d isa disease, has name $n; fetch {"n": $n};').resolve())
    return sorted(r["n"] for r in results)


def _fetch_disease_detail(driver, name: str) -> dict | None:
    """Return full detail dict for a disease by name, or None if not found."""
    from typedb.driver import TransactionType

    escaped = _escape(name)

    # Verify existence
    if _count_query(driver, f'match $d isa disease, has name "{escaped}"; reduce $c = count;') == 0:
        return None

    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        cat_results = list(tx.query(
            f'match $d isa disease, has name "{escaped}", has category $cat; '
            f'fetch {{"cat": $cat}};'
        ).resolve())

    detail: dict = {
        "name": name,
        "category": cat_results[0]["cat"] if cat_results else None,
        "mechanisms": [],
    }

    # Parents (multivalued)
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        p_results = list(tx.query(
            f'match $d isa disease, has name "{escaped}", has parents $p; fetch {{"p": $p}};'
        ).resolve())
    detail["parents"] = [r["p"] for r in p_results]

    # Disease term
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        dt_results = list(tx.query(
            f'match $d isa disease, has name "{escaped}"; '
            f'(disease: $d, diseasedescriptor: $dt) isa disease-term; '
            f'$dt has preferred-term $pt; '
            f'fetch {{"pt": $pt}};'
        ).resolve())
    if dt_results:
        detail["disease_term"] = dt_results[0]["pt"]

    # Pathophysiology mechanisms
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        m_results = list(tx.query(
            f'match $d isa disease, has name "{escaped}"; '
            f'(disease: $d, pathophysiology: $p) isa pathophysiology-rel; '
            f'$p has name $mn; '
            f'fetch {{"mn": $mn}};'
        ).resolve())
    # Get descriptions separately (optional attribute)
    mechanism_names = [r["mn"] for r in m_results]
    mechanisms = []
    for mname in mechanism_names:
        escaped_mname = _escape(mname)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            desc_results = list(tx.query(
                f'match $p isa pathophysiology, has name "{escaped_mname}", has description $desc; '
                f'fetch {{"desc": $desc}};'
            ).resolve())
        mechanisms.append({
            "name": mname,
            "description": desc_results[0]["desc"] if desc_results else None,
        })
    detail["mechanisms"] = mechanisms

    return detail


def cmd_show_disease(args):
    """Show full details for a single disease by name."""
    with _get_driver() as driver:
        detail = _fetch_disease_detail(driver, args.name)
    if detail is None:
        print(json.dumps({"success": False, "error": f"Disease not found: {args.name}"}))
        sys.exit(1)
    print(json.dumps({"success": True, "disease": detail}, indent=2))


def cmd_list_diseases(args):
    """List all diseases, optionally filtered by category."""
    from typedb.driver import TransactionType
    with _get_driver() as driver:
        if args.category:
            cat = _escape(args.category)
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                results = list(tx.query(
                    f'match $d isa disease, has name $n, has category "{cat}"; '
                    f'fetch {{"n": $n}};'
                ).resolve())
        else:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                results = list(tx.query(
                    'match $d isa disease, has name $n; fetch {"n": $n};'
                ).resolve())
    names = sorted(r["n"] for r in results)
    print(json.dumps({"success": True, "count": len(names), "diseases": names}))


def cmd_search(args):
    """Full-text search over disease names and mechanism descriptions."""
    from typedb.driver import TransactionType
    query_lower = args.query.lower()
    escaped_q = _escape(args.query)

    hits = []
    with _get_driver() as driver:
        # Search by disease name (contains)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query('match $d isa disease, has name $n; fetch {"n": $n};').resolve())
        for r in results:
            n = r["n"]
            if query_lower in n.lower():
                hits.append({"disease": n, "match_type": "name"})

        # Search by mechanism description/name
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            m_results = list(tx.query(
                'match $d isa disease, has name $dn; '
                '(disease: $d, pathophysiology: $p) isa pathophysiology-rel; '
                '$p has name $mn; '
                'fetch {"dn": $dn, "mn": $mn};'
            ).resolve())
        seen_diseases: set[str] = {h["disease"] for h in hits}
        for r in m_results:
            dn = r["dn"]
            mn = r["mn"]
            if query_lower in mn.lower() and dn not in seen_diseases:
                hits.append({"disease": dn, "match_type": "mechanism", "mechanism": mn})
                seen_diseases.add(dn)

    # Limit results
    hits = hits[:args.limit]
    print(json.dumps({"success": True, "query": args.query, "count": len(hits), "results": hits}))


def cmd_stats(args):
    """Print database statistics: counts of diseases, mechanisms, terms."""
    from typedb.driver import TransactionType

    entity_attr = {"disease": "name", "pathophysiology": "name", "diseasedescriptor": "preferred-term"}
    with _get_driver() as driver:
        counts = {
            et: _count_query(driver, f'match $e isa {et}, has {attr} $a; reduce $c = count;')
            for et, attr in entity_attr.items()
        }

    print(json.dumps({
        "success": True,
        "diseases": counts.get("disease", 0),
        "mechanisms": counts.get("pathophysiology", 0),
        "disease_terms": counts.get("diseasedescriptor", 0),
    }))


def cmd_add_evidence(args):
    """Add a new evidence item linked to a disease and/or mechanism."""
    from typedb.driver import TransactionType
    
    # Validate required arguments
    if not args.pmid:
        print(json.dumps({"success": False, "error": "PMID is required"}))
        sys.exit(1)
    
    if not args.disease and not args.mechanism:
        print(json.dumps({"success": False, "error": "Either --disease or --mechanism is required"}))
        sys.exit(1)
    
    # Build reference string from PMID
    reference = f"PMID:{args.pmid}"
    
    errors = []
    with _get_driver() as driver:
        # Validate that disease exists if specified
        if args.disease:
            disease_count = _count_query(driver, f'match $d isa disease, has name "{_escape(args.disease)}"; reduce $c = count;')
            if disease_count == 0:
                errors.append(f"Disease not found: {args.disease}")
        
        # Validate that mechanism exists if specified
        if args.mechanism:
            mech_count = _count_query(driver, f'match $p isa pathophysiology, has name "{_escape(args.mechanism)}"; reduce $c = count;')
            if mech_count == 0:
                errors.append(f"Mechanism not found: {args.mechanism}")
        
        if errors:
            print(json.dumps({"success": False, "errors": errors}))
            sys.exit(1)
        
        # Insert evidence item
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            evidence_attrs = [
                f'has reference "{_escape(reference)}"',
                f'has supports "{_escape(args.supports)}"',
                f'has evidence-source "{_escape(args.evidence_source)}"'
            ]
            
            if args.reference_title:
                evidence_attrs.append(f'has reference-title "{_escape(args.reference_title)}"')
            
            if args.snippet:
                evidence_attrs.append(f'has snippet "{_escape(_truncate(args.snippet))}"')
            
            if args.explanation:
                evidence_attrs.append(f'has explanation "{_escape(_truncate(args.explanation))}"')
            
            # Insert evidenceitem entity
            q = f"insert $ev isa evidenceitem, {', '.join(evidence_attrs)};"
            try:
                tx.query(q).resolve()
                tx.commit()
            except Exception as e:
                errors.append(f"Failed to insert evidence item: {e}")
        
        if errors:
            print(json.dumps({"success": False, "errors": errors}))
            sys.exit(1)
        
        # Create evidence relations
        evidence_relations = []
        
        if args.disease:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                q = (
                    f'match $d isa disease, has name "{_escape(args.disease)}"; '
                    f'$ev isa evidenceitem, has reference "{_escape(reference)}"; '
                    f'insert (disease: $d, evidenceitem: $ev) isa evidence;'
                )
                try:
                    tx.query(q).resolve()
                    tx.commit()
                    evidence_relations.append(f"disease: {args.disease}")
                except Exception as e:
                    errors.append(f"Failed to link evidence to disease: {e}")
        
        if args.mechanism:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                q = (
                    f'match $p isa pathophysiology, has name "{_escape(args.mechanism)}"; '
                    f'$ev isa evidenceitem, has reference "{_escape(reference)}"; '
                    f'insert (pathophysiology: $p, evidenceitem: $ev) isa evidence;'
                )
                try:
                    tx.query(q).resolve()
                    tx.commit()
                    evidence_relations.append(f"mechanism: {args.mechanism}")
                except Exception as e:
                    errors.append(f"Failed to link evidence to mechanism: {e}")
        
        if errors:
            print(json.dumps({"success": False, "errors": errors}))
            sys.exit(1)
        
        print(json.dumps({
            "success": True,
            "reference": reference,
            "linked_to": evidence_relations
        }))


# ── Dashboard server ──────────────────────────────────────────────────────────


def cmd_serve(args):
    """Serve the dashboard at http://localhost:<port>."""
    skill_dir = Path(__file__).parent
    dashboard_dir = skill_dir / "dashboard"

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(skill_dir), **kw)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path.startswith("/api/"):
                self._handle_api(parsed)
            else:
                # Serve dashboard/index.html for /
                if parsed.path in ("/", ""):
                    self.path = "/dashboard/index.html"
                super().do_GET()

        def _handle_api(self, parsed):
            params = dict(urllib.parse.parse_qsl(parsed.query))
            try:
                result = self._dispatch_api(parsed.path, params)
                body = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

        def _dispatch_api(self, path, params):
            with _get_driver() as driver:
                if path == "/api/stats":
                    return _api_stats(driver)
                elif path == "/api/diseases":
                    return _api_diseases(driver, params)
                elif path == "/api/disease":
                    return _fetch_disease_detail(driver, params.get("name", "")) or {}
                elif path == "/api/search":
                    return _api_search(driver, params.get("q", ""), int(params.get("limit", "50")))
                else:
                    return {"error": f"Unknown API endpoint: {path}"}

        def log_message(self, fmt, *a):
            pass  # Suppress request logs

    port = args.port
    print(json.dumps({"message": f"DisMech dashboard at http://localhost:{port}", "port": port}))
    with http.server.HTTPServer(("", port), Handler) as srv:
        srv.serve_forever()


def _api_stats(driver) -> dict:
    entity_attr = {"disease": "name", "pathophysiology": "name", "diseasedescriptor": "preferred-term"}
    counts = {
        et: _count_query(driver, f'match $e isa {et}, has {attr} $a; reduce $c = count;')
        for et, attr in entity_attr.items()
    }
    return {
        "diseases": counts.get("disease", 0),
        "mechanisms": counts.get("pathophysiology", 0),
        "disease_terms": counts.get("diseasedescriptor", 0),
    }


def _api_diseases(driver, params: dict) -> dict:
    from typedb.driver import TransactionType
    category = params.get("category")
    limit = int(params.get("limit", "100"))
    offset = int(params.get("offset", "0"))

    if category:
        cat = _escape(category)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                f'match $d isa disease, has name $n, has category "{cat}"; '
                f'fetch {{"n": $n}};'
            ).resolve())
    else:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query('match $d isa disease, has name $n; fetch {"n": $n};').resolve())

    names = sorted(r["n"] for r in results)
    page = names[offset: offset + limit]
    return {"total": len(names), "offset": offset, "limit": limit, "diseases": page}


def _api_search(driver, query: str, limit: int = 50) -> dict:
    from typedb.driver import TransactionType
    if not query:
        return {"results": []}
    query_lower = query.lower()
    hits = []

    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        results = list(tx.query('match $d isa disease, has name $n; fetch {"n": $n};').resolve())
    for r in results:
        n = r["n"]
        if query_lower in n.lower():
            hits.append({"disease": n, "match_type": "name"})

    seen: set[str] = {h["disease"] for h in hits}
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        m_results = list(tx.query(
            'match $d isa disease, has name $dn; '
            '(disease: $d, pathophysiology: $p) isa pathophysiology-rel; '
            '$p has name $mn; '
            'fetch {"dn": $dn, "mn": $mn};'
        ).resolve())
    for r in m_results:
        dn = r["dn"]
        mn = r["mn"]
        if query_lower in mn.lower() and dn not in seen:
            hits.append({"disease": dn, "match_type": "mechanism", "mechanism": mn})
            seen.add(dn)

    return {"query": query, "count": len(hits[:limit]), "results": hits[:limit]}


# ── CLI entry point ───────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="DisMech — Disease Mechanism Knowledge Graph CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ingest
    ingest_p = sub.add_parser("ingest", help="Bulk-ingest disorder YAML files")
    ingest_p.add_argument("--source", required=True, help="Path to kb/disorders directory")
    ingest_p.add_argument("--max", type=int, default=None, help="Maximum files to ingest (for testing)")
    ingest_p.add_argument("--quiet", action="store_true", help="Suppress progress bar")

    # show-disease
    show_p = sub.add_parser("show-disease", help="Show full details for a disease")
    show_p.add_argument("--name", required=True, help="Disease name (exact match)")

    # list-diseases
    list_p = sub.add_parser("list-diseases", help="List all diseases")
    list_p.add_argument("--category", default=None, help="Filter by category (e.g., Genetic, Infectious)")

    # search
    search_p = sub.add_parser("search", help="Full-text search over names and mechanism descriptions")
    search_p.add_argument("--query", required=True, help="Search query text")
    search_p.add_argument("--limit", type=int, default=50, help="Maximum results (default: 50)")

    # stats
    sub.add_parser("stats", help="Show database statistics")

    # serve
    serve_p = sub.add_parser("serve", help="Start the dashboard web server")
    serve_p.add_argument("--port", type=int, default=7777, help="Port to serve on (default: 7777)")

    # add-evidence
    evidence_p = sub.add_parser("add-evidence", help="Add a new evidence item")
    evidence_p.add_argument("--disease", default=None, help="Disease name to link evidence to")
    evidence_p.add_argument("--mechanism", default=None, help="Mechanism name to link evidence to")
    evidence_p.add_argument("--pmid", required=True, help="PubMed ID (e.g., 38234567)")
    evidence_p.add_argument("--supports", required=True, choices=["SUPPORT", "REFUTE", "NO_EVIDENCE", "PARTIAL", "WRONG_STATEMENT"], help="Evidence support level")
    evidence_p.add_argument("--evidence-source", required=True, choices=["HUMAN_CLINICAL", "ANIMAL_MODEL", "IN_VITRO", "COMPUTATIONAL"], help="Evidence source type")
    evidence_p.add_argument("--snippet", default=None, help="Key quote from abstract or paper")
    evidence_p.add_argument("--reference-title", default=None, help="Paper title (optional)")
    evidence_p.add_argument("--explanation", default=None, help="Explanation of evidence relevance")

    args = parser.parse_args()
    dispatch = {
        "ingest": cmd_ingest,
        "show-disease": cmd_show_disease,
        "list-diseases": cmd_list_diseases,
        "search": cmd_search,
        "stats": cmd_stats,
        "serve": cmd_serve,
        "add-evidence": cmd_add_evidence,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
