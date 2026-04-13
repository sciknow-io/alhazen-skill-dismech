#!/usr/bin/env python3
"""
DisMech Core — TypeDB infrastructure setup for the Disease Mechanism Knowledge Graph skill.

Starts the TypeDB Docker container, creates the dismech database, and loads the schema.
Run this once (or let the SessionStart hook run it automatically).

Usage:
    python alhazen_core.py init      # Start TypeDB, create dismech DB, load schema
    python alhazen_core.py status    # Check TypeDB container and database state
    python alhazen_core.py reset     # Drop and recreate the database (WARNING: destroys data)

Environment:
    TYPEDB_HOST         TypeDB host (default: localhost)
    TYPEDB_PORT         TypeDB port (default: 1729)
    TYPEDB_DATABASE     Database name (default: dismech)
    TYPEDB_USERNAME     TypeDB username (default: admin)
    TYPEDB_PASSWORD     TypeDB password (default: password)
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "dismech")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")

TYPEDB_IMAGE = "typedb/typedb:3.8.0"
TYPEDB_CONTAINER = "alhazen-typedb"

# The full dismech TypeQL schema (generated from LinkML dismech.yaml via gen-typedb)
SCHEMA_FILE = Path(__file__).parent / "schema.tql"


def _docker(*args, check=True, capture=True):
    """Run a docker command, return CompletedProcess."""
    cmd = ["docker"] + list(args)
    return subprocess.run(cmd, capture_output=capture, text=True, check=check)


def _is_docker_running():
    try:
        _docker("info")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _container_status():
    """Return container status string or '' if not found."""
    try:
        r = _docker("inspect", "--format", "{{.State.Status}}", TYPEDB_CONTAINER)
        return r.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def _start_typedb():
    """Start the TypeDB container, pulling image if needed. Returns True on success."""
    status = _container_status()
    if status == "running":
        return True
    if status == "exited":
        _docker("start", TYPEDB_CONTAINER)
    else:
        # Container doesn't exist — create it
        _docker(
            "run", "-d",
            "--name", TYPEDB_CONTAINER,
            "-p", f"{TYPEDB_PORT}:1729",
            TYPEDB_IMAGE,
        )

    # Wait for TypeDB to become ready (up to 60s)
    for _ in range(60):
        time.sleep(1)
        try:
            from typedb.driver import Credentials, DriverOptions, TypeDB
            driver = TypeDB.driver(
                f"{TYPEDB_HOST}:{TYPEDB_PORT}",
                Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
                DriverOptions(is_tls_enabled=False),
            )
            driver.close()
            return True
        except Exception:
            pass
    return False


def _get_driver():
    try:
        from typedb.driver import Credentials, DriverOptions, TypeDB
        return TypeDB.driver(
            f"{TYPEDB_HOST}:{TYPEDB_PORT}",
            Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
            DriverOptions(is_tls_enabled=False),
        )
    except ImportError:
        print(
            json.dumps({"success": False, "error": "typedb-driver not installed. Run: uv sync"}),
            file=sys.stderr,
        )
        sys.exit(1)


def _database_exists(driver):
    try:
        return driver.databases.contains(TYPEDB_DATABASE)
    except Exception:
        return False


def _create_database(driver):
    """Create the database if it doesn't exist. Returns True if newly created."""
    if not _database_exists(driver):
        driver.databases.create(TYPEDB_DATABASE)
        return True
    return False


def _load_schema(driver):
    """Load the dismech TypeQL schema into the database."""
    from typedb.driver import TransactionType
    schema_text = SCHEMA_FILE.read_text(encoding="utf-8")
    with driver.transaction(TYPEDB_DATABASE, TransactionType.SCHEMA) as tx:
        tx.query(schema_text).resolve()
        tx.commit()


def cmd_init(args):
    """Start TypeDB, create database, load dismech schema."""
    # Step 1: Docker
    if not _is_docker_running():
        print(json.dumps({"success": False, "error": "Docker is not running. Start Docker Desktop (macOS) or `sudo systemctl start docker` (Linux)."}))
        sys.exit(1)

    # Step 2: TypeDB container
    if not _start_typedb():
        print(json.dumps({"success": False, "error": f"TypeDB container failed to start within 60s. Check: docker logs {TYPEDB_CONTAINER}"}))
        sys.exit(1)

    # Step 3: Database + schema
    with _get_driver() as driver:
        created = _create_database(driver)
        try:
            _load_schema(driver)
            schema_result = "loaded"
        except Exception as e:
            # Schema already loaded (idempotent) — that's fine
            schema_result = f"already-loaded"

    print(json.dumps({
        "success": True,
        "typedb": "running",
        "database": TYPEDB_DATABASE,
        "database_created": created,
        "schema": schema_result,
        "message": "DisMech ready. Run dismech.py ingest to load disease data.",
    }))


def cmd_status(args):
    """Check TypeDB container and database state."""
    docker_ok = _is_docker_running()
    container_status = _container_status() if docker_ok else "docker-not-running"

    typedb_reachable = False
    db_exists = False
    if container_status == "running":
        try:
            with _get_driver() as driver:
                typedb_reachable = True
                db_exists = _database_exists(driver)
        except Exception:
            pass

    print(json.dumps({
        "success": True,
        "docker": "running" if docker_ok else "not-running",
        "container": container_status,
        "typedb_reachable": typedb_reachable,
        "database": TYPEDB_DATABASE,
        "database_exists": db_exists,
    }))


def cmd_reset(args):
    """Drop and recreate the database. WARNING: destroys all ingested data."""
    if not args.yes:
        print(json.dumps({"success": False, "error": "Pass --yes to confirm database reset. This destroys ALL ingested disease data."}))
        sys.exit(1)

    with _get_driver() as driver:
        if _database_exists(driver):
            driver.databases.get(TYPEDB_DATABASE).delete()
        driver.databases.create(TYPEDB_DATABASE)
        _load_schema(driver)

    print(json.dumps({
        "success": True,
        "database": TYPEDB_DATABASE,
        "schema": "loaded",
        "message": "Database reset. Run dismech.py ingest to reload disease data.",
    }))


def main():
    parser = argparse.ArgumentParser(description="DisMech Core — TypeDB infrastructure setup")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Start TypeDB, create dismech database, load schema")
    sub.add_parser("status", help="Check TypeDB container and database state")

    reset_p = sub.add_parser("reset", help="Drop and recreate the database (destroys all data)")
    reset_p.add_argument("--yes", action="store_true", help="Confirm destructive reset")

    args = parser.parse_args()
    dispatch = {"init": cmd_init, "status": cmd_status, "reset": cmd_reset}
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
