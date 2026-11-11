# Extract, clean, load, query, report.

from pathlib import Path

import pandas as pd

from sales_analysis import clean, database, report


def extract(data_dir):
    data = Path(data_dir)
    # Raw sales are read as text so nothing is guessed or converted before the cleaning rules run
    raw = pd.read_csv(data / "raw_sales.csv", dtype=str, keep_default_na=False)
    stores = pd.read_csv(data / "stores.csv")
    products = pd.read_csv(data / "products.csv")
    return raw, stores, products


def run(data_dir="data", out_dir="output"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    raw, stores, products = extract(data_dir)
    sales, rejected, dq_log = clean.clean(raw, stores, products)

    db_path = out / "sales.db"
    if db_path.exists():
        db_path.unlink()
    conn = database.connect(db_path)
    try:
        database.load(conn, sales, stores, products)
        load_check = database.reconcile(conn, sales)
        results = database.run_queries(conn)
    finally:
        conn.close()

    dq_log.to_csv(out / "data_quality_log.csv", index=False)
    report.write_excel(out / "sales_report.xlsx", results, dq_log, rejected, load_check)
    return {"sales": sales, "rejected": rejected, "dq_log": dq_log, "results": results, "load_check": load_check}
