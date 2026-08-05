# Как проверял (задача 2) — обязательно

Скриншоты: папка `screenshots/`
- `01_search_prime_moscow.jpg` — поиск «Прайм» + фильтр город «Москва»
- `02_all_companies.jpg` — полный список без фильтров (Найдено: 994)
- `03_ui_variant.jpg` — общий вид UI

## Что делал и что ломалось

1. Поднял Postgres, прогнал `load_companies.py --apply-schema` → в таблице `companies` 994 строки. Без живой БД страница сразу падала с «DATABASE_URL is not set» / connection refused — ожидаемо, пока не скопирован `.env.example` → `.env.local`.

2. Написал smoke-тест `scripts/test-db.py`: count=994, поиск «прайм» ≥3 hits, city=Москва ≥50, combined filter. Все проверки зелёные — слой `getCompanies()` и SQL корректны.

3. Собрал `/companies` как Server Component: форма GET с `q` и `city`, таблица, empty state. Сначала pool создавался при импорте модуля и `next build` падал без env — переделал на lazy `getPool()`. Rating из PG приходил как string (NUMERIC) — нормализовал в `number | null`.

4. Проверил сценарии: пустой поиск → все; `?q=Прайм` → подстрока ILIKE; `?city=Москва` → exact; оба вместе; сброс. Пустой результат — «Ничего не найдено».

5. Секреты: в репозитории только `.env.example`, реального `.env.local` нет. Запросы параметризованные.

Итог: данные с сервера, поиск и фильтр работают, ошибки БД показывают сообщение вместо 500.
