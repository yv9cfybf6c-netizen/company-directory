# Companies App (Next.js App Router)

Мини-фича поверх PostgreSQL из задачи 1.

## Маршруты

| URL | Описание |
|-----|----------|
| `/` | Стартовая страница |
| `/companies` | Таблица + поиск по названию + фильтр по городу |

Данные загружаются **только на сервере** (Server Component).  
Секреты не коммитятся — только `.env.example`.

## Быстрый старт

```bash
# 1. Postgres с таблицей companies (задача 1)
# 2. Env
cp .env.example .env.local
# DATABASE_URL=postgresql://company_loader:loader_pass@localhost:5432/companies

# 3. Зависимости и dev-сервер
npm install
npm run dev
# → http://localhost:3000/companies
```

## Тесты

```bash
# Smoke-тест слоя данных (Python, не требует next)
DATABASE_URL=postgresql://... python3 scripts/test-db.py
```

Ожидаемый вывод:
```
total companies: 994
search 'прайм': ≥3 hits
city=Москва: ≥50
All smoke tests passed.
```

## Что сделано при рефакторинге

- **Lazy pool** — `getPool()` создаётся при первом запросе, `next build` не падает без env
- **Нормализация rating** — `NUMERIC` из PG → `number | null`
- **Обработка ошибок** — страница показывает сообщение вместо 500
- **searchParams** — синхронный объект (Next 14)
- **Параметризованные запросы** — защита от SQL-injection
- **CSS** — добавлен блок `.error`
- **Smoke-тесты** — `scripts/test-db.py` покрывает count / search / city / combined

## Структура

```
src/
  app/
    companies/
      page.tsx              # Server Component
      companies.module.css
    layout.tsx
    page.tsx
  lib/
    db.ts                   # getCompanies()
scripts/
  test-db.py                # smoke-тест данных
  test-db.mjs               # JS-вариант (нужен полный npm install)
.env.example
```
