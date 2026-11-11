# Cleans the raw sales export.
# Every rule records how many rows it touched and what it did, so the cleaning is transparent and auditable.
# Nothing is dropped silently.

import re

import pandas as pd

DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"]

REGION_MAP = {
    "gauteng": "Gauteng", "gp": "Gauteng",
    "western cape": "Western Cape", "wc": "Western Cape", "w. cape": "Western Cape",
    "kwazulu-natal": "KwaZulu-Natal", "kwazulu natal": "KwaZulu-Natal", "kzn": "KwaZulu-Natal",
    "eastern cape": "Eastern Cape", "ec": "Eastern Cape", "e. cape": "Eastern Cape",
}


class DataQualityLog:
    def __init__(self):
        self.entries = []

    def add(self, rule_id, rule, rows_affected, action):
        self.entries.append({"rule_id": rule_id, "rule": rule, "rows_affected": int(rows_affected), "action": action})

    def to_frame(self):
        return pd.DataFrame(self.entries, columns=["rule_id", "rule", "rows_affected", "action"])


def parse_dates(series):
    # Try each known format in turn; anything left over is genuinely unreadable
    result = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    for fmt in DATE_FORMATS:
        missing = result.isna()
        result[missing] = pd.to_datetime(series[missing], format=fmt, errors="coerce")
    return result


def parse_price(series):
    # Handles "1299.00", "R1 299.00" and "R 1299.00"
    cleaned = series.astype(str).str.replace(r"[R\s,]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


def standardise_region(series):
    key = series.astype(str).str.strip().str.lower()
    return key.map(REGION_MAP)


def clean(raw, stores, products):
    # Returns (clean_sales, rejected_rows, dq_log)
    log = DataQualityLog()
    df = raw.copy().astype(str).replace("nan", "")
    df = df.apply(lambda col: col.str.strip())
    rejected = []
    start_rows = len(df)
    log.add("DQ-00", "Rows received in raw export", start_rows, "Baseline count")

    def reject(mask, reason):
        if mask.any():
            bad = df[mask].copy()
            bad["reject_reason"] = reason
            rejected.append(bad)
        return df[~mask].copy()

    # DQ-01 exact duplicate rows
    dup_mask = df.duplicated(keep="first")
    log.add("DQ-01", "Exact duplicate rows", dup_mask.sum(), "Removed, first copy kept")
    df = reject(dup_mask, "Exact duplicate")

    # DQ-02 dates in mixed formats
    parsed = parse_dates(df["sale_date"])
    non_iso = (~df["sale_date"].str.match(r"^\d{4}-\d{2}-\d{2}$")) & parsed.notna()
    log.add("DQ-02", "Dates in non-standard formats", non_iso.sum(), "Converted to YYYY-MM-DD")
    df["sale_date"] = parsed
    bad_date = df["sale_date"].isna()
    log.add("DQ-03", "Missing or impossible dates", bad_date.sum(), "Rejected")
    df = reject(bad_date, "Invalid sale_date")

    # DQ-04 referential integrity against the store and product masters
    unknown = ~df["store_id"].isin(stores["store_id"]) | ~df["product_id"].isin(products["product_id"])
    log.add("DQ-04", "Unknown store_id or product_id", unknown.sum(), "Rejected")
    df = reject(unknown, "Unknown store or product")

    # DQ-05 quantity missing, non-numeric, zero or negative
    qty = pd.to_numeric(df["quantity"], errors="coerce")
    missing_qty = qty.isna()
    log.add("DQ-05", "Missing quantity", missing_qty.sum(), "Rejected, cannot be estimated")
    df = reject(missing_qty, "Missing quantity")
    qty = pd.to_numeric(df["quantity"], errors="coerce")
    bad_qty = qty <= 0
    log.add("DQ-06", "Zero or negative quantity", bad_qty.sum(), "Rejected, returns belong in a separate process")
    df = reject(bad_qty, "Zero or negative quantity")
    df["quantity"] = pd.to_numeric(df["quantity"]).astype(int)

    # DQ-07 prices stored as text with currency symbols
    text_price = df["unit_price"].str.contains(r"[R\s]", regex=True)
    log.add("DQ-07", "Prices with currency symbols or spaces", text_price.sum(), "Converted to numeric")
    df["unit_price"] = parse_price(df["unit_price"])
    bad_price = df["unit_price"].isna() | (df["unit_price"] <= 0)
    log.add("DQ-08", "Unreadable or non-positive price", bad_price.sum(), "Rejected")
    df = reject(bad_price, "Invalid unit_price")

    # DQ-09 region typed inconsistently; the store master is the source of truth
    typed = standardise_region(df["region"])
    master = df["store_id"].map(stores.set_index("store_id")["region"])
    inconsistent = df["region"] != master
    log.add("DQ-09", "Region spelled inconsistently", inconsistent.sum(), "Replaced with region from store master")
    conflicting = typed.notna() & (typed != master)
    log.add("DQ-10", "Typed region conflicts with store master", conflicting.sum(), "Store master used")
    df["region"] = master

    # Product name and category also come from the master, so reports group correctly
    prod = products.set_index("product_id")
    df["product_name"] = df["product_id"].map(prod["product_name"])
    df["category"] = df["product_id"].map(prod["category"])

    df["revenue"] = (df["quantity"] * df["unit_price"]).round(2)
    log.add("DQ-99", "Clean rows loaded", len(df), f"{len(df) / start_rows:.1%} of rows received")

    rejected_df = pd.concat(rejected, ignore_index=True) if rejected else pd.DataFrame()
    cols = ["transaction_id", "sale_date", "store_id", "region", "product_id", "product_name",
            "category", "quantity", "unit_price", "revenue"]
    return df[cols].reset_index(drop=True), rejected_df, log.to_frame()
