# Company PG Loader

Загрузка выгрузки внутреннего API (`page_001.json` … `page_020.json`) в PostgreSQL  
с нормализацией, дедупликацией по `id` и индексами под аналитические запросы.

## Структура

```
company-pg-loader/
├── data/                       # исходные page_*.json (20 файлов)
├── scripts/
│   └── load_companies.py       # загрузчик
├── tests/
│   ├── test_normalize.py       # unit-тесты (без БД)
│   └── test_integration.py     # интеграционный тест (нужен Postgres)
├── schema.sql                  # DDL + индексы
├── queries.sql                 # 3 аналитических запроса
├── requirements.txt
└── README.md
```

## Требования

- Python 3.9+
- PostgreSQL 12+
- `pip install -r requirements.txt`  (psycopg2-binary, pytest)

## Быстрый старт

### 1. Поднять Postgres

**Docker (предпочтительно):**
```bash
docker run -d --name company-pg \
  -e POSTGRES_USER=company_loader \
  -e POSTGRES_PASSWORD=loader_pass \
  -e POSTGRES_DB=companies \
  -p 5432:5432 \
  postgres:16-alpine
```

**Локально:**
```bash
sudo -u postgres psql -c "CREATE USER company_loader WITH PASSWORD 'loader_pass' SUPERUSER;"
sudo -u postgres psql -c "CREATE DATABASE companies OWNER company_loader;"
```

### 2. Загрузить данные

```bash
export PGHOST=localhost PGPORT=5432 \
       PGDATABASE=companies \
       PGUSER=company_loader PGPASSWORD=loader_pass

python scripts/load_companies.py --apply-schema
```

Флаг `--apply-schema` пересоздаёт таблицу (DROP + CREATE).  
Повторный запуск без флага просто пропускает уже существующие `id`.

### 3. Аналитика

```bash
psql -h localhost -U company_loader -d companies -f queries.sql
```

## Тесты

```bash
# unit-тесты (не требуют БД)
pytest tests/test_normalize.py -v

# полный прогон (нужен запущенный Postgres + переменные окружения)
pytest tests/ -v
```

Ожидаемый результат unit-тестов: **13 passed**.

## Что делает загрузчик

1. Находит все `page_*.json`.
2. Нормализует поля:
   - `rating` → `float 0–5` или `NULL`
   - `reviews_count` → `int ≥ 0`
   - пустые / `"None"` / `"нет сайта"` → `NULL` для site/phone
3. Дедуплицирует по `id` (первое вхождение побеждает).
4. Вставляет через `INSERT … ON CONFLICT (id) DO NOTHING`.
5. Пишет статистику в лог.

## Схема

| Колонка         | Тип              | Описание                     |
|-----------------|------------------|------------------------------|
| id              | VARCHAR(20) PK   | Внешний идентификатор        |
| name            | TEXT NOT NULL    | Название                     |
| category        | TEXT NOT NULL    | Категория                    |
| city            | TEXT NOT NULL    | Город                        |
| address         | TEXT             | Адрес                        |
| rating          | NUMERIC(2,1)     | 0–5 или NULL                 |
| reviews_count   | INTEGER ≥ 0      | Число отзывов                |
| site            | TEXT             | Сайт или NULL                |
| phone           | TEXT             | Телефон или NULL             |
| loaded_at       | TIMESTAMPTZ      | Время вставки                |

Индексы заточены под три запроса из `queries.sql`.

## Запросы (`queries.sql`)

1. **Топ-5 категорий** по числу компаний.  
2. **Средний рейтинг по городам** только среди компаний с ≥ 10 отзывами.  
3. **Доля компаний с сайтом** (%) по категориям.

## CLI

| Аргумент / env        | Описание                              |
|-----------------------|---------------------------------------|
| `--data-dir`          | Каталог с page_*.json (default `./data`) |
| `--dsn`               | Полная connection string              |
| `--apply-schema`      | Выполнить schema.sql перед загрузкой  |
| `-v / --verbose`      | Debug-логи                            |
| `PGHOST`…`PGPASSWORD` | Стандартные libpq-переменные          |

## Результат загрузки (эталон)

```
After normalize + dedup: 994 unique companies
Inserted 994 new rows
with_site   = 756
with_rating = 915
```

## Task 3: review.csv

```bash
# dry-run (clean + stats, no DB)
python scripts/load_review.py --dry-run

# load into Postgres
python scripts/load_review.py --apply

# unit tests for cleaners
pytest tests/test_review_clean.py -v
```

See `ANOMALIES.md` and `REPORT_REVIEW.md`.
