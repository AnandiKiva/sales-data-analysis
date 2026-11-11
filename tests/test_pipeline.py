# Tests for the cleaning rules, the SQL queries and the full pipeline.

import sqlite3

import pandas as pd

from sales_analysis import clean, database, generate_data, pipeline

STORES = pd.DataFrame([("ST01", "Store A", "Gauteng"), ("ST02", "Store B", "Western Cape")],
                      columns=["store_id", "store_name", "region"])
PRODUCTS = pd.DataFrame([("P001", "Laptop", "Laptops", 10000.0), ("P002", "Mouse", "Accessories", 300.0)],
                        columns=["product_id", "product_name", "category", "list_price"])


def raw_frame(rows):
    base = {"transaction_id": "TX1", "sale_date": "2025-07-15", "store_id": "ST01", "region": "Gauteng",
            "product_id": "P001", "product_name": "Laptop", "category": "Laptops", "quantity": "1",
            "unit_price": "10000.00"}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_mixed_date_formats_are_parsed():
    parsed = clean.parse_dates(pd.Series(["2025-07-15", "2025/07/15", "15-07-2025", "2026-02-30", "N/A"]))
    assert list(parsed[:3].dt.strftime("%Y-%m-%d")) == ["2025-07-15"] * 3
    assert parsed[3:].isna().all()


def test_price_text_is_converted():
    assert list(clean.parse_price(pd.Series(["1299.00", "R1 299.00", "R 1299.00"]))) == [1299.0] * 3


def test_region_variants_are_standardised():
    out = clean.standardise_region(pd.Series(["GP", " gauteng ", "W. Cape", "KZN", "Nowhere"]))
    assert list(out[:4]) == ["Gauteng", "Gauteng", "Western Cape", "KwaZulu-Natal"]
    assert pd.isna(out[4])


def test_each_bad_row_is_rejected_with_a_reason():
    raw = raw_frame([
        {"transaction_id": "GOOD"},
        {"transaction_id": "GOOD"},
        {"transaction_id": "BADDATE", "sale_date": "N/A"},
        {"transaction_id": "BADSTORE", "store_id": "ST99"},
        {"transaction_id": "NOQTY", "quantity": ""},
        {"transaction_id": "NEGQTY", "quantity": "-2"},
    ])
    sales, rejected, log = clean.clean(raw, STORES, PRODUCTS)
    assert list(sales["transaction_id"]) == ["GOOD"]
    reasons = dict(zip(rejected["transaction_id"], rejected["reject_reason"]))
    assert reasons == {"GOOD": "Exact duplicate", "BADDATE": "Invalid sale_date", "BADSTORE": "Unknown store or product",
                       "NOQTY": "Missing quantity", "NEGQTY": "Zero or negative quantity"}
    # Every row received is either loaded or rejected, none disappear
    received = log.loc[log["rule_id"] == "DQ-00", "rows_affected"].item()
    assert received == len(sales) + len(rejected)


def test_store_master_overrides_typed_region():
    raw = raw_frame([{"transaction_id": "T1", "store_id": "ST02", "region": "GP"}])
    sales, _, log = clean.clean(raw, STORES, PRODUCTS)
    assert sales.iloc[0]["region"] == "Western Cape"
    assert log.loc[log["rule_id"] == "DQ-10", "rows_affected"].item() == 1


def test_revenue_is_quantity_times_price():
    raw = raw_frame([{"transaction_id": "T1", "product_id": "P002", "quantity": "3", "unit_price": "R 299.50"}])
    sales, _, _ = clean.clean(raw, STORES, PRODUCTS)
    assert sales.iloc[0]["revenue"] == 898.50


def test_sql_queries_return_expected_numbers():
    raw = raw_frame([
        {"transaction_id": "T1", "sale_date": "2025-07-10", "quantity": "1", "unit_price": "1000"},
        {"transaction_id": "T2", "sale_date": "2025-08-10", "quantity": "1", "unit_price": "1500"},
        {"transaction_id": "T3", "sale_date": "2025-08-11", "store_id": "ST02", "product_id": "P002",
         "quantity": "2", "unit_price": "250"},
    ])
    sales, _, _ = clean.clean(raw, STORES, PRODUCTS)
    conn = sqlite3.connect(":memory:")
    database.load(conn, sales, STORES, PRODUCTS)
    results = database.run_queries(conn)

    assert results["kpi_totals"].iloc[0]["total_revenue"] == 3000.0
    monthly = results["monthly_revenue"].set_index("month")
    assert monthly.loc["2025-08", "revenue"] == 2000.0
    assert monthly.loc["2025-08", "mom_growth_pct"] == 100.0
    regions = results["revenue_by_region"].set_index("region")
    assert regions.loc["Gauteng", "revenue_share_pct"] == 83.3
    assert database.reconcile(conn, sales)["revenue_match"]


def test_full_pipeline_rejects_exactly_what_was_planted(tmp_path):
    raw, _, _, planted = generate_data.write(tmp_path / "data", transactions=3000, seed=7)
    out = pipeline.run(tmp_path / "data", tmp_path / "out")
    log = out["dq_log"].set_index("rule_id")["rows_affected"]

    assert log["DQ-01"] == planted["duplicate_rows"]
    assert log["DQ-03"] == planted["bad_dates"]
    assert log["DQ-04"] == planted["unknown_store_or_product"]
    assert log["DQ-05"] == planted["missing_quantity"]
    assert log["DQ-06"] == planted["invalid_quantity"]
    assert len(out["sales"]) == len(raw) - sum(planted.values())
    assert out["load_check"]["rows_match"] and out["load_check"]["revenue_match"]
    assert (tmp_path / "out" / "sales_report.xlsx").exists()
