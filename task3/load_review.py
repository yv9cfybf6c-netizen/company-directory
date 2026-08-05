#!/usr/bin/env python3
"""
Load review.csv into PostgreSQL companies table.

Cleans known anomalies (see ANOMALIES.md), deduplicates by id,
inserts with ON CONFLICT DO NOTHING.

Usage:
    python scripts/load_review.py --dry-run
    python scripts/load_review.py --apply
    python scripts/load_review.py --csv /path/to/review.csv --apply
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger("load_review")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "review.csv"

# ---------------------------------------------------------------------------
# Pure cleaners (unit-tested in tests/test_review_clean.py)
# ---------------------------------------------------------------------------

CITY_MAP = {
    "Moscow": "Москва",
    "москва": "Москва",
    "Москва ": "Москва",
    "Санкат-Петербург": "Санкт-Петербург",
}

KNOWN_CITY_NAMES = set(CITY_MAP.values()) | {
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань",
    "Нижний Новгород", "Челябинск", "Самара", "Омск", "Ростов-на-Дону",
    "Уфа", "Краснодар", "Пермь", "Воронеж", "Волгоград", "Тюмень",
    "Ярославль", "Калуга", "Тула", "Сочи",
}


def fix_mojibake(s: str) -> str:
    """Recover text that was UTF-8 bytes misread as cp1251."""
    try:
        return s.encode("cp1251").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def looks_like_mojibake(s: str) -> bool:
    # Typical double-encoded Cyrillic starts with these sequences
    return "Рћ" in s or "Р—" in s or "Рў" in s or "Рњ" in s or "РЎ" in s


def clean_rating(raw: Any) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if s.lower() in ("", "nan", "n/a", "none"):
        return None
    s = s.replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    if 0.0 <= v <= 5.0:
        return round(v, 1)
    return None


def clean_reviews(raw: Any) -> int:
    if raw is None:
        return 0
    s = str(raw).strip().lower()
    if s in ("", "nan", "n/a", "none", "много"):
        return 0
    try:
        v = int(float(s))
        return max(v, 0)
    except ValueError:
        return 0


def clean_site(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if s.lower() in ("", "none", "null", "нет сайта", "https://", "http://"):
        return None
    if s.startswith("htp://"):
        s = "http://" + s[6:]
    if "shared-site" in s:
        return None
    return s or None


def clean_phone(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or "abc" in s.lower() or len(re.sub(r"\D", "", s)) < 5:
        return None
    return s


def clean_city(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if looks_like_mojibake(s):
        s = fix_mojibake(s)
    s = CITY_MAP.get(s, s).strip()
    # address leaked into city field
    if s.startswith("ул.") or ("д." in s and "офис" in s):
        return None
    return s or None


def clean_name(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if looks_like_mojibake(s):
        s = fix_mojibake(s)
    return s or None


def normalize_row(raw: dict[str, Any], row_num: int) -> dict[str, Any] | None:
    """
    Clean one CSV row. Returns None if the row is unusable.
    Handles the known column-shift case for c_001015.
    """
    cid = (raw.get("id") or "").strip()
    if not cid:
        return None

    name = clean_name(raw.get("name"))
    category = (raw.get("category") or "").strip()
    city = clean_city(raw.get("city"))
    address = (raw.get("address") or "").strip() or None

    # Column shift: category holds a city name, city holds an address
    if category in KNOWN_CITY_NAMES and city is None:
        address = (raw.get("city") or "").strip() or address
        city = category
        category = "Неизвестно"

    if not name or not category or not city:
        return None

    return {
        "id": cid,
        "name": name,
        "category": category,
        "city": city,
        "address": address,
        "rating": clean_rating(raw.get("rating")),
        "reviews_count": clean_reviews(raw.get("reviews_count")),
        "site": clean_site(raw.get("site")),
        "phone": clean_phone(raw.get("phone")),
        "_source_row": row_num,
    }


def load_rows(path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    Read CSV → clean → dedup by id (first wins).
    Returns (rows, stats).
    """
    stats = {
        "raw": 0,
        "empty_id": 0,
        "unusable": 0,
        "dup_id": 0,
        "kept": 0,
    }
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, raw in enumerate(reader, start=2):  # 1-based + header
            stats["raw"] += 1
            if not (raw.get("id") or "").strip():
                stats["empty_id"] += 1
                continue
            item = normalize_row(raw, i)
            if item is None:
                stats["unusable"] += 1
                continue
            if item["id"] in seen:
                stats["dup_id"] += 1
                continue
            seen.add(item["id"])
            rows.append(item)
            stats["kept"] += 1

    return rows, stats


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

def get_connection():
    try:
        import psycopg2
    except ImportError:
        log.error("psycopg2 not installed: pip install psycopg2-binary")
        sys.exit(1)

    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return psycopg2.connect(dsn)
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "companies"),
        user=os.getenv("PGUSER", "company_loader"),
        password=os.getenv("PGPASSWORD", "loader_pass"),
    )


def insert_rows(conn, rows: list[dict[str, Any]]) -> int:
    from psycopg2.extras import execute_batch

    payload = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM companies")
        before = cur.fetchone()[0]
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
        execute_batch(cur, sql, payload, page_size=100)
        cur.execute("SELECT COUNT(*) FROM companies")
        after = cur.fetchone()[0]
    return after - before


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load cleaned review.csv into Postgres")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--dry-run", action="store_true", help="Only clean & report, no DB")
    parser.add_argument("--apply", action="store_true", help="Insert into DB")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s  %(message)s",
    )

    if not args.csv.exists():
        log.error("CSV not found: %s", args.csv)
        return 1

    rows, stats = load_rows(args.csv)
    log.info(
        "raw=%d  empty_id=%d  unusable=%d  dup_id=%d  kept=%d",
        stats["raw"], stats["empty_id"], stats["unusable"],
        stats["dup_id"], stats["kept"],
    )

    if args.dry_run or not args.apply:
        log.info("Dry-run. Sample of cleaned rows:")
        for r in rows[:5]:
            log.info("  %s | %s | %s | rating=%s", r["id"], r["name"], r["city"], r["rating"])
        if not args.apply:
            log.info("Pass --apply to insert into Postgres.")
        return 0

    conn = get_connection()
    try:
        inserted = insert_rows(conn, rows)
        conn.commit()
        log.info("Inserted %d new rows", inserted)
    except Exception as exc:
        conn.rollback()
        log.error("%s", exc)
        return 1
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
