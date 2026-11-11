-- Star schema: one fact table of sales lines, two dimension tables.

DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_store;
DROP TABLE IF EXISTS dim_product;

CREATE TABLE dim_store (
    store_id    TEXT PRIMARY KEY,
    store_name  TEXT NOT NULL,
    region      TEXT NOT NULL
);

CREATE TABLE dim_product (
    product_id    TEXT PRIMARY KEY,
    product_name  TEXT NOT NULL,
    category      TEXT NOT NULL,
    list_price    REAL NOT NULL CHECK (list_price > 0)
);

CREATE TABLE fact_sales (
    transaction_id  TEXT PRIMARY KEY,
    sale_date       TEXT NOT NULL,
    store_id        TEXT NOT NULL REFERENCES dim_store (store_id),
    product_id      TEXT NOT NULL REFERENCES dim_product (product_id),
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    unit_price      REAL NOT NULL CHECK (unit_price > 0),
    revenue         REAL NOT NULL
);

CREATE INDEX idx_sales_date ON fact_sales (sale_date);
CREATE INDEX idx_sales_store ON fact_sales (store_id);
CREATE INDEX idx_sales_product ON fact_sales (product_id);
