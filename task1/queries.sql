-- queries.sql
-- Analytical queries for the companies table

-- 1. Топ-5 категорий по числу компаний
SELECT
    category,
    COUNT(*) AS companies_count
FROM companies
GROUP BY category
ORDER BY companies_count DESC
LIMIT 5;


-- 2. Средний рейтинг по городам среди компаний с 10+ отзывами
SELECT
    city,
    ROUND(AVG(rating)::numeric, 2) AS avg_rating,
    COUNT(*) AS companies_with_10plus_reviews
FROM companies
WHERE reviews_count >= 10
  AND rating IS NOT NULL
GROUP BY city
ORDER BY avg_rating DESC, companies_with_10plus_reviews DESC;


-- 3. Доля компаний с сайтом по категориям
SELECT
    category,
    COUNT(*) AS total_companies,
    COUNT(site) AS with_site,
    ROUND(100.0 * COUNT(site) / COUNT(*), 1) AS site_share_pct
FROM companies
GROUP BY category
ORDER BY site_share_pct DESC, total_companies DESC;
