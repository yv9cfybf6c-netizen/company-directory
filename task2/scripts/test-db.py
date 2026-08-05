#!/usr/bin/env python3
"""Smoke-test for the companies data layer (mirrors getCompanies filters)."""
import os
import sys
import psycopg2

url = os.environ.get("DATABASE_URL", "postgresql://company_loader:loader_pass@localhost:5432/companies")

def main():
    conn = psycopg2.connect(url)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM companies")
    total = cur.fetchone()[0]
    print(f"total companies: {total}")
    assert total == 994, f"expected 994, got {total}"

    cur.execute("SELECT id, name, city FROM companies WHERE name ILIKE %s ORDER BY name LIMIT 10", ("%прайм%",))
    rows = cur.fetchall()
    print(f"search 'прайм': {len(rows)} hits")
    assert len(rows) >= 3
    print(f"  sample: {rows[0][1]}")

    cur.execute("SELECT COUNT(*) FROM companies WHERE city = %s", ("Москва",))
    msk = cur.fetchone()[0]
    print(f"city=Москва: {msk}")
    assert msk >= 50

    cur.execute(
        "SELECT name, city FROM companies WHERE name ILIKE %s AND city = %s ORDER BY name LIMIT 5",
        ("%сервис%", "Москва"),
    )
    combined = cur.fetchall()
    print(f"combined filter rows: {len(combined)}")

    cur.execute("SELECT DISTINCT city FROM companies ORDER BY city")
    cities = cur.fetchall()
    print(f"distinct cities: {len(cities)}")
    assert len(cities) >= 15

    print("\nAll smoke tests passed.")
    cur.close()
    conn.close()
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)
