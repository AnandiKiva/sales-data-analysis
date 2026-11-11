# Loads clean data into SQLite and runs the named KPI queries.

import re
import sqlite3
from pathlib import Path

import pandas as pd

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn):
    conn.executescript((SQL_DIR / "schema.sql").read_text())


def load(conn, sales, stores, products):
    create_schema(conn)
    stores[["store_id", "store_name", "region"]].to_sql("dim_store", conn, if_exists="append", index=False)
    products[["product_id", "product_name", "category", "list_price"]].to_sql(
        "dim_product", conn, if_exists="append", index=False)
    fact = sales[["transaction_id", "sale_date", "store_id", "product_id", "quantity", "unit_price", "revenue"]].copy()
    fact["sale_date"] = pd.to_datetime(fact["sale_date"]).dt.strftime("%Y-%m-%d")
    fact.to_sql("fact_sales", conn, if_exists="append", index=False)
    conn.commit()


def load_queries(path=None):
    # Splits the SQL file on "-- name: x" markers and returns {name: sql}
    text = Path(path or SQL_DIR / "kpi_queries.sql").read_text()
    parts = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.MULTILINE)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def run_queries(conn):
    return {name: pd.read_sql_query(sql, conn) for name, sql in load_queries().items()}


def reconcile(conn, sales):
    # Checks the database holds exactly what the cleaning step produced
    db_rows, db_revenue = conn.execute("SELECT COUNT(*), ROUND(SUM(revenue), 2) FROM fact_sales").fetchone()
    return {
        "rows_match": db_rows == len(sales),
        "revenue_match": abs(db_revenue - round(sales["revenue"].sum(), 2)) < 0.01,
        "db_rows": db_rows,
        "db_revenue": db_revenue,
    }
