# Generates a year of mock sales transactions for a South African tech retailer.
# The raw file is deliberately messy, the way real exports usually are, so the cleaning step has work to do.
# Reference data for stores and products is clean and acts as the source of truth.

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

FY_START = date(2025, 7, 1)
FY_END = date(2026, 6, 30)

STORES = [
    ("ST01", "Sandton City", "Gauteng"),
    ("ST02", "Menlyn Park", "Gauteng"),
    ("ST03", "Mall of Africa", "Gauteng"),
    ("ST04", "Canal Walk", "Western Cape"),
    ("ST05", "V&A Waterfront", "Western Cape"),
    ("ST06", "Gateway", "KwaZulu-Natal"),
    ("ST07", "Pavilion", "KwaZulu-Natal"),
    ("ST08", "Baywest", "Eastern Cape"),
    ("ST09", "Hemingways", "Eastern Cape"),
    ("ST10", "Eastgate", "Gauteng"),
]

PRODUCTS = [
    ("P001", "Laptop 14in Core i5", "Laptops", 12_999.00),
    ("P002", "Laptop 15in Core i7", "Laptops", 18_499.00),
    ("P003", "Gaming Laptop RTX", "Laptops", 27_999.00),
    ("P004", "Chromebook 11in", "Laptops", 4_999.00),
    ("P005", "Smartphone A15", "Phones", 3_299.00),
    ("P006", "Smartphone Pro Max", "Phones", 22_999.00),
    ("P007", "Smartphone Mid 5G", "Phones", 7_499.00),
    ("P008", "Tablet 10in", "Tablets", 5_999.00),
    ("P009", "Tablet Pro 12in", "Tablets", 16_999.00),
    ("P010", "Wireless Earbuds", "Audio", 1_299.00),
    ("P011", "Noise Cancelling Headphones", "Audio", 5_499.00),
    ("P012", "Bluetooth Speaker", "Audio", 1_799.00),
    ("P013", "Smartwatch", "Wearables", 4_299.00),
    ("P014", "Fitness Band", "Wearables", 899.00),
    ("P015", "27in Monitor", "Accessories", 3_999.00),
    ("P016", "Wireless Mouse", "Accessories", 349.00),
    ("P017", "Mechanical Keyboard", "Accessories", 1_199.00),
    ("P018", "USB-C Hub", "Accessories", 599.00),
    ("P019", "1TB External SSD", "Storage", 1_899.00),
    ("P020", "128GB Flash Drive", "Storage", 249.00),
    ("P021", "Wi-Fi 6 Router", "Networking", 2_199.00),
    ("P022", "Mesh Wi-Fi Kit", "Networking", 4_999.00),
    ("P023", "Gaming Console", "Gaming", 11_999.00),
    ("P024", "Game Controller", "Gaming", 1_299.00),
    ("P025", "Power Bank 20000mAh", "Accessories", 699.00),
]

# How busy each month is relative to normal (Black Friday in November, festive season in December)
MONTH_WEIGHT = {7: 0.9, 8: 0.85, 9: 0.9, 10: 1.0, 11: 1.8, 12: 1.6, 1: 0.8, 2: 0.85, 3: 0.95, 4: 1.0, 5: 1.0, 6: 1.1}

# How the same region tends to be typed by different branches
REGION_VARIANTS = {
    "Gauteng": ["Gauteng", "gauteng", "GAUTENG", "GP", " Gauteng "],
    "Western Cape": ["Western Cape", "western cape", "WC", "W. Cape"],
    "KwaZulu-Natal": ["KwaZulu-Natal", "KZN", "Kwazulu Natal", "kwazulu-natal"],
    "Eastern Cape": ["Eastern Cape", "EC", "eastern cape", "E. Cape"],
}


def _dates_weighted(rng, count):
    days = [FY_START + timedelta(days=d) for d in range((FY_END - FY_START).days + 1)]
    weights = [MONTH_WEIGHT[d.month] * (1.4 if d.weekday() >= 5 else 1.0) for d in days]
    return rng.choices(days, weights=weights, k=count)


def _messy_date(rng, d):
    # Different branches export dates in different formats
    fmt = rng.choices(["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"], weights=[0.8, 0.12, 0.08])[0]
    return d.strftime(fmt)


def _messy_price(rng, price):
    style = rng.random()
    if style < 0.85:
        return f"{price:.2f}"
    if style < 0.95:
        return f"R{price:,.2f}".replace(",", " ")
    return f"R {price:.2f}"


def generate(transactions=6000, seed=42):
    # Returns (raw_sales, stores, products, planted) where planted counts the dirty data introduced
    rng = random.Random(seed)
    store_weights = [1.4, 1.2, 1.3, 1.1, 1.2, 1.0, 0.9, 0.7, 0.6, 1.0]
    product_weights = [1.0, 0.7, 0.3, 0.8, 1.6, 0.5, 1.2, 0.9, 0.4, 2.5, 1.1, 1.5,
                       0.9, 1.4, 0.8, 2.2, 1.0, 1.6, 1.0, 2.0, 0.8, 0.5, 0.5, 1.1, 1.8]

    rows = []
    for i, d in enumerate(_dates_weighted(rng, transactions)):
        store = rng.choices(STORES, weights=store_weights)[0]
        product = rng.choices(PRODUCTS, weights=product_weights)[0]
        cheap = product[3] < 1_500
        quantity = rng.choices([1, 2, 3, 4, 5], weights=[50, 25, 12, 8, 5] if cheap else [85, 12, 3, 0, 0])[0]
        # Prices drift slightly with promotions, heavier discounts during Black Friday
        discount = rng.choice([0, 0, 0, 0.05, 0.1]) if d.month != 11 else rng.choice([0.1, 0.15, 0.2])
        price = round(product[3] * (1 - discount), 2)
        rows.append({
            "transaction_id": f"TX{i + 1:06d}",
            "sale_date": _messy_date(rng, d),
            "store_id": store[0],
            "region": rng.choice(REGION_VARIANTS[store[2]]),
            "product_id": product[0],
            "product_name": product[1],
            "category": product[2],
            "quantity": str(quantity),
            "unit_price": _messy_price(rng, price),
        })

    raw = pd.DataFrame(rows)
    planted = {}
    pool = list(range(len(raw)))
    rng.shuffle(pool)

    def take(n):
        picked = pool[:n]
        del pool[:n]
        return picked

    for idx in take(40):
        raw.at[idx, "quantity"] = ""
    planted["missing_quantity"] = 40

    for idx in take(25):
        raw.at[idx, "quantity"] = str(-int(raw.at[idx, "quantity"]))
    for idx in take(5):
        raw.at[idx, "quantity"] = "0"
    planted["invalid_quantity"] = 30

    for idx in take(15):
        raw.at[idx, "sale_date"] = rng.choice(["", "N/A", "2026-02-30", "31/31/2025"])
    planted["bad_dates"] = 15

    for idx in take(12):
        raw.at[idx, "store_id"] = rng.choice(["ST99", "", "ST00"])
    for idx in take(8):
        raw.at[idx, "product_id"] = rng.choice(["P999", "", "P000"])
    planted["unknown_store_or_product"] = 20

    # Exact duplicate rows, as if a batch was exported twice
    dup_idx = rng.sample(pool, 60)
    raw = pd.concat([raw, raw.loc[dup_idx]], ignore_index=True)
    planted["duplicate_rows"] = 60

    raw = raw.sample(frac=1, random_state=seed).reset_index(drop=True)
    stores = pd.DataFrame(STORES, columns=["store_id", "store_name", "region"])
    products = pd.DataFrame(PRODUCTS, columns=["product_id", "product_name", "category", "list_price"])
    return raw, stores, products, planted


def write(out_dir="data", transactions=6000, seed=42):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    raw, stores, products, planted = generate(transactions, seed)
    raw.to_csv(out / "raw_sales.csv", index=False)
    stores.to_csv(out / "stores.csv", index=False)
    products.to_csv(out / "products.csv", index=False)
    return raw, stores, products, planted
