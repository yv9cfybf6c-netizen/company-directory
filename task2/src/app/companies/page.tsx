import { getCompanies } from "@/lib/db";
import styles from "./companies.module.css";

type Props = {
  searchParams: { q?: string; city?: string };
};

export const metadata = {
  title: "Компании — справочник",
  description: "Список компаний из PostgreSQL с поиском и фильтром",
};

export default async function CompaniesPage({ searchParams }: Props) {
  const q = (searchParams.q ?? "").trim();
  const city = (searchParams.city ?? "").trim();

  let rows: Awaited<ReturnType<typeof getCompanies>>["rows"] = [];
  let total = 0;
  let cities: string[] = [];
  let error: string | null = null;

  try {
    const result = await getCompanies({ q, city, limit: 150 });
    rows = result.rows;
    total = result.total;
    cities = result.cities;
  } catch (e) {
    console.error("[companies] DB error:", e);
    error =
      e instanceof Error
        ? e.message
        : "Не удалось загрузить данные. Проверьте DATABASE_URL и доступность Postgres.";
  }

  return (
    <main className={styles.main}>
      <header className={styles.header}>
        <h1>Справочник компаний</h1>
        <p className={styles.subtitle}>
          Данные из PostgreSQL (задача 1) · серверный рендер · поиск и фильтр
        </p>
      </header>

      <form className={styles.filters} method="GET" action="/companies">
        <div className={styles.field}>
          <label htmlFor="q">Поиск по названию</label>
          <input
            id="q"
            name="q"
            type="search"
            placeholder="например, Прайм или IT…"
            defaultValue={q}
            autoComplete="off"
          />
        </div>

        <div className={styles.field}>
          <label htmlFor="city">Город</label>
          <select id="city" name="city" defaultValue={city}>
            <option value="">Все города</option>
            {cities.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <button type="submit" className={styles.btn}>
          Найти
        </button>
        {(q || city) && (
          <a href="/companies" className={styles.reset}>
            Сбросить
          </a>
        )}
      </form>

      {error ? (
        <div className={styles.error} role="alert">
          <strong>Ошибка:</strong> {error}
        </div>
      ) : (
        <>
          <p className={styles.meta}>
            Найдено: <strong>{total}</strong>
            {rows.length < total && ` (показано ${rows.length})`}
          </p>

          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Название</th>
                  <th>Категория</th>
                  <th>Город</th>
                  <th>Рейтинг</th>
                  <th>Отзывы</th>
                  <th>Сайт</th>
                  <th>Телефон</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={7} className={styles.empty}>
                      Ничего не найдено. Измените фильтры.
                    </td>
                  </tr>
                ) : (
                  rows.map((c) => (
                    <tr key={c.id}>
                      <td className={styles.name}>{c.name}</td>
                      <td>{c.category}</td>
                      <td>{c.city}</td>
                      <td className={styles.num}>
                        {c.rating != null ? c.rating.toFixed(1) : "—"}
                      </td>
                      <td className={styles.num}>{c.reviews_count}</td>
                      <td>
                        {c.site ? (
                          <a
                            href={
                              c.site.startsWith("http")
                                ? c.site
                                : `https://${c.site}`
                            }
                            target="_blank"
                            rel="noopener noreferrer"
                            className={styles.link}
                          >
                            сайт
                          </a>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className={styles.phone}>{c.phone ?? "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}
