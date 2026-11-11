-- KPI queries used by the report.
-- Each query starts with a "-- name:" line so the Python code can load it by name.

-- name: kpi_totals
SELECT
    ROUND(SUM(revenue), 2)                           AS total_revenue,
    SUM(quantity)                                    AS units_sold,
    COUNT(*)                                         AS transactions,
    ROUND(SUM(revenue) / COUNT(*), 2)                AS avg_transaction_value,
    MIN(sale_date)                                   AS first_sale,
    MAX(sale_date)                                   AS last_sale
FROM fact_sales;

-- name: monthly_revenue
-- Month on month growth uses the LAG window function to compare each month with the one before it
WITH monthly AS (
    SELECT
        strftime('%Y-%m', sale_date) AS month,
        ROUND(SUM(revenue), 2)       AS revenue,
        SUM(quantity)                AS units,
        COUNT(*)                     AS transactions
    FROM fact_sales
    GROUP BY month
)
SELECT
    month,
    revenue,
    units,
    transactions,
    ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month)) / LAG(revenue) OVER (ORDER BY month), 1)
        AS mom_growth_pct
FROM monthly
ORDER BY month;

-- name: revenue_by_region
SELECT
    s.region,
    ROUND(SUM(f.revenue), 2)                                         AS revenue,
    SUM(f.quantity)                                                  AS units,
    ROUND(100.0 * SUM(f.revenue) / (SELECT SUM(revenue) FROM fact_sales), 1) AS revenue_share_pct
FROM fact_sales f
JOIN dim_store s ON s.store_id = f.store_id
GROUP BY s.region
ORDER BY revenue DESC;

-- name: store_ranking
-- Ranks each store nationally and within its own region
SELECT
    s.store_id,
    s.store_name,
    s.region,
    ROUND(SUM(f.revenue), 2)                                              AS revenue,
    RANK() OVER (ORDER BY SUM(f.revenue) DESC)                            AS national_rank,
    RANK() OVER (PARTITION BY s.region ORDER BY SUM(f.revenue) DESC)      AS region_rank
FROM fact_sales f
JOIN dim_store s ON s.store_id = f.store_id
GROUP BY s.store_id, s.store_name, s.region
ORDER BY national_rank;

-- name: top_products
SELECT
    p.product_id,
    p.product_name,
    p.category,
    SUM(f.quantity)                                  AS units,
    ROUND(SUM(f.revenue), 2)                         AS revenue,
    ROUND(AVG(f.unit_price), 2)                      AS avg_selling_price,
    ROUND(100.0 * (1 - AVG(f.unit_price) / p.list_price), 1) AS avg_discount_pct
FROM fact_sales f
JOIN dim_product p ON p.product_id = f.product_id
GROUP BY p.product_id, p.product_name, p.category, p.list_price
ORDER BY revenue DESC
LIMIT 10;

-- name: category_by_quarter
-- Financial year runs July to June, so July to September is Q1
SELECT
    p.category,
    ROUND(SUM(CASE WHEN CAST(strftime('%m', f.sale_date) AS INTEGER) BETWEEN 7 AND 9   THEN f.revenue ELSE 0 END), 2) AS q1_jul_sep,
    ROUND(SUM(CASE WHEN CAST(strftime('%m', f.sale_date) AS INTEGER) BETWEEN 10 AND 12 THEN f.revenue ELSE 0 END), 2) AS q2_oct_dec,
    ROUND(SUM(CASE WHEN CAST(strftime('%m', f.sale_date) AS INTEGER) BETWEEN 1 AND 3   THEN f.revenue ELSE 0 END), 2) AS q3_jan_mar,
    ROUND(SUM(CASE WHEN CAST(strftime('%m', f.sale_date) AS INTEGER) BETWEEN 4 AND 6   THEN f.revenue ELSE 0 END), 2) AS q4_apr_jun,
    ROUND(SUM(f.revenue), 2) AS total
FROM fact_sales f
JOIN dim_product p ON p.product_id = f.product_id
GROUP BY p.category
ORDER BY total DESC;
