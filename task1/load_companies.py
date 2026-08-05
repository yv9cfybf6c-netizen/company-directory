#!/usr/bin/env python3
"""
Load company data from page_*.json into PostgreSQL.

Usage:
    python scripts/load_companies.py [--data-dir DIR] [--dsn DSN] [--apply-schema]

Environment variables (fallback when --dsn is omitted):
    PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Iterator

import psycopg2
from psycopg2.extras import execute_batch

log = logging.getLogger("load_companies")

# ---------------------------------------------------------------------------
# Pure data helpers (easy to unit-test)
# ---------------------------------------------------------------------------

def find_page_files(data_dir: Path) -> list[Path]:
    """Return sorted list of page_*.json files. Raises if none found."""
    files = sorted(data_dir.glob("page_*.json"))
    if not files:
        raise FileNotFoundError(f"No page_*.json found in {data_dir}")
    return files


def iter_raw_items(files: list[Path]) -> Iterator[dict[str, Any]]:
    """Yield every item from every page file."""
    for path in files:
        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
        page_items = payload.get("items")
        if not isinstance(page_items, list):
            raise ValueError(f"{path}: 'items' must be a list, got {type(page_items)}")
        log.info("%s: page=%s items=%d", path.name, payload.get("page"), len(page_items))
        yield from page_items


def normalize_item(raw: dict[str, Any]) -> dict[str, Any] | None:
    """
    Clean and validate a single company record.
    Returns None when the record is unusable (missing required fields).
    """
    cid = raw.get("id")
    if not isinstance(cid, str) or not cid.strip():
        return None

    name = (raw.get("name") or "").strip()
    category = (raw.get("category") or "").strip()
    city = (raw.get("city") or "").strip()
    if not (name and category and city):
        return None

    address = raw.get("address")
    if address is not None:
        address = str(address).strip() or None

    rating = _safe_rating(raw.get("rating"))
    reviews_count = _safe_reviews(raw.get("reviews_count", 0))
    site = _safe_text(raw.get("site"), extra_nulls=("нет сайта",))
    phone = _safe_text(raw.get("phone"))

    return {
        "id": cid.strip(),
        "name": name,
        "category": category,
        "city": city,
        "address": address,
        "rating": rating,
        "reviews_count": reviews_count,
        "site": site,
        "phone": phone,
    }


def _safe_rating(value: Any) -> float | None:
    if value is None:
        return None
    try:
        r = float(value)
        return r if 0.0 <= r <= 5.0 else None
    except (TypeError, ValueError):
        return None


def _safe_reviews(value: Any) -> int:
    try:
        n = int(value)
        return max(n, 0)
    except (TypeError, ValueError):
        return 0


def _safe_text(value: Any, extra_nulls: tuple[str, ...] = ()) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("none", "null") or s in extra_nulls:
        return None
    return s


def collect_unique_rows(files: list[Path]) -> list[dict[str, Any]]:
    """Load → normalize → deduplicate by id (first occurrence wins)."""
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    skipped = 0
    for raw in iter_raw_items(files):
        item = normalize_item(raw)
        if item is None:
            skipped += 1
            continue
        if item["id"] in seen:
            skipped += 1
            continue
        seen.add(item["id"])
        rows.append(item)
    log.info("Normalized unique rows: %d (skipped/invalid/dup: %d)", len(rows), skipped)
    return rows


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_connection(dsn: str | None = None):
    if dsn:
        return psycopg2.connect(dsn)
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "companies"),
        user=os.getenv("PGUSER", "company_loader"),
        password=os.getenv("PGPASSWORD", "loader_pass"),
    )


def apply_schema(conn, schema_path: Path) -> None:
    sql = schema_path.read_text(encoding="utf-8")
    # Execute the whole script; Postgres handles multiple statements
    with conn.cursor() as cur:
        cur.execute(sql)
    log.info("Schema applied from %s", schema_path)


def insert_rows(conn, rows: list[dict[str, Any]]) -> int:
    """Insert rows with ON CONFLICT DO NOTHING. Returns number of newly inserted rows."""
    if not rows:
        return 0

    sql = """
        INSERT INTO companies (
            id, name, category, city, address,
            rating, reviews_count, site, phone
        ) VALUES (
            %(id)s, %(name)s, %(category)s, %(city)s, %(address)s,
            %(rating)s, %(reviews_count)s, %(site)s, %(phone)s
        )
        ON CONFLICT (id) DO NOTHING
    """
    with conn.cursor() as cur:
        # Count before
        cur.execute("SELECT COUNT(*) FROM companies")
        before = cur.fetchone()[0]

        execute_batch(cur, sql, rows, page_size=200)

        cur.execute("SELECT COUNT(*) FROM companies")
        after = cur.fetchone()[0]

    inserted = after - before
    log.info("Inserted %d new rows (table total now %d)", inserted, after)
    return inserted


def print_stats(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM companies")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM companies WHERE site IS NOT NULL")
        with_site = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM companies WHERE rating IS NOT NULL")
        with_rating = cur.fetchone()[0]
    log.info("Final stats → total=%d  with_site=%d  with_rating=%d", total, with_site, with_rating)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load companies from page_*.json into PostgreSQL",
    )
    root = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=root / "data",
        help="Directory containing page_*.json (default: ./data)",
    )
    parser.add_argument("--dsn", default=None, help="Full Postgres connection string")
    parser.add_argument(
        "--schema",
        type=Path,
        default=root / "schema.sql",
        help="Path to schema.sql",
    )
    parser.add_argument(
        "--apply-schema",
        action="store_true",
        help="Execute schema.sql before loading (drops & recreates table)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Debug logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s  %(message)s",
    )

    try:
        files = find_page_files(args.data_dir)
        log.info("Found %d page files in %s", len(files), args.data_dir)
        rows = collect_unique_rows(files)

        conn = get_connection(args.dsn)
        conn.autocommit = False
        try:
            if args.apply_schema:
                apply_schema(conn, args.schema)
            insert_rows(conn, rows)
            conn.commit()
            print_stats(conn)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    except Exception as exc:
        log.error("%s", exc)
        return 1

    log.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
