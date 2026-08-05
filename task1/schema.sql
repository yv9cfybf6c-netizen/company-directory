-- schema.sql
-- PostgreSQL schema for company directory data
-- Source: internal API pages (page_001.json … page_020.json)

DROP TABLE IF EXISTS companies CASCADE;

CREATE TABLE companies (
    id              VARCHAR(20) PRIMARY KEY,
    name            TEXT        NOT NULL,
    category        TEXT        NOT NULL,
    city            TEXT        NOT NULL,
    address         TEXT,
    rating          NUMERIC(2,1) CHECK (rating IS NULL OR (rating >= 0 AND rating <= 5)),
    reviews_count   INTEGER     NOT NULL DEFAULT 0 CHECK (reviews_count >= 0),
    site            TEXT,
    phone           TEXT,
    loaded_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes tuned for the three analytical queries
CREATE INDEX idx_companies_category        ON companies (category);
CREATE INDEX idx_companies_city            ON companies (city);
CREATE INDEX idx_companies_rating          ON companies (rating) WHERE rating IS NOT NULL;
CREATE INDEX idx_companies_reviews_count   ON companies (reviews_count);
CREATE INDEX idx_companies_site_not_null   ON companies (id) WHERE site IS NOT NULL;
CREATE INDEX idx_companies_city_reviews    ON companies (city, rating)
    WHERE reviews_count >= 10 AND rating IS NOT NULL;

COMMENT ON TABLE  companies               IS 'Business directory entries from internal API (pages 1-20)';
COMMENT ON COLUMN companies.id            IS 'Stable external identifier from source system';
COMMENT ON COLUMN companies.rating        IS 'Average rating 0-5; NULL when no reviews';
COMMENT ON COLUMN companies.reviews_count IS 'Number of reviews; 0 when rating is NULL';
COMMENT ON COLUMN companies.loaded_at     IS 'Timestamp when the row was inserted by the loader';
