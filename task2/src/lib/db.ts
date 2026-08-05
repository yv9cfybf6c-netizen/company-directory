import { Pool, type QueryResult } from "pg";

/**
 * Lazy singleton pool — created on first use so `next build`
 * does not crash when DATABASE_URL is absent at build time.
 */
const globalForPg = globalThis as unknown as { pgPool?: Pool };

function getPool(): Pool {
  if (globalForPg.pgPool) return globalForPg.pgPool;

  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error(
      "DATABASE_URL is not set. Copy .env.example → .env.local and fill it in."
    );
  }

  const pool = new Pool({
    connectionString,
    max: 5,
    idleTimeoutMillis: 10_000,
    connectionTimeoutMillis: 5_000,
  });

  globalForPg.pgPool = pool;
  return pool;
}

export type Company = {
  id: string;
  name: string;
  category: string;
  city: string;
  address: string | null;
  rating: number | null;
  reviews_count: number;
  site: string | null;
  phone: string | null;
};

export type CompanyFilters = {
  /** Search substring for company name (ILIKE) */
  q?: string;
  /** Exact city match */
  city?: string;
  /** Max rows to return (default 150) */
  limit?: number;
};

export type CompaniesResult = {
  rows: Company[];
  total: number;
  cities: string[];
};

/**
 * Fetch companies with optional name search and city filter.
 * All queries are parameterized — no SQL injection risk.
 */
export async function getCompanies(
  filters: CompanyFilters = {}
): Promise<CompaniesResult> {
  const { q, city, limit = 150 } = filters;
  const conditions: string[] = [];
  const params: unknown[] = [];
  let idx = 1;

  if (q?.trim()) {
    conditions.push(`name ILIKE $${idx}`);
    params.push(`%${q.trim()}%`);
    idx += 1;
  }
  if (city?.trim()) {
    conditions.push(`city = $${idx}`);
    params.push(city.trim());
    idx += 1;
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";

  const dataSql = `
    SELECT
      id, name, category, city, address,
      rating, reviews_count, site, phone
    FROM companies
    ${where}
    ORDER BY name ASC
    LIMIT $${idx}
  `;
  const dataParams = [...params, limit];

  const countSql = `SELECT COUNT(*)::int AS total FROM companies ${where}`;
  const countParams = params;

  const citiesSql = `SELECT DISTINCT city FROM companies ORDER BY city ASC`;

  const pool = getPool();

  const [dataRes, countRes, citiesRes]: [
    QueryResult<Company>,
    QueryResult<{ total: number }>,
    QueryResult<{ city: string }>,
  ] = await Promise.all([
    pool.query<Company>(dataSql, dataParams),
    pool.query<{ total: number }>(countSql, countParams),
    pool.query<{ city: string }>(citiesSql),
  ]);

  // pg returns NUMERIC as string — normalize to number | null
  const rows: Company[] = dataRes.rows.map((r) => ({
    ...r,
    rating: r.rating == null ? null : Number(r.rating),
    reviews_count: Number(r.reviews_count) || 0,
  }));

  return {
    rows,
    total: countRes.rows[0]?.total ?? 0,
    cities: citiesRes.rows.map((r) => r.city),
  };
}
