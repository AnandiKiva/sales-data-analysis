# Sales Data Analysis and Automated Reporting

A Python and SQL pipeline that takes a messy sales export, cleans it with documented data quality rules, loads it into a SQLite database, runs KPI queries, and generates a formatted Excel performance report with charts.

The whole report rebuilds from raw data in under a second, so no one has to copy numbers into a spreadsheet by hand.

All data is generated mock data for a fictional South African tech retailer with 10 stores across four provinces, covering a July to June financial year.

## Pipeline

```
raw_sales.csv  ──>  clean  ──>  SQLite (star schema)  ──>  KPI queries  ──>  sales_report.xlsx
stores.csv          │                    │
products.csv        └─ data quality log  └─ load reconciliation check
```

1. **Extract.** Reads the raw export as text, so nothing is guessed or converted before the cleaning rules run.
2. **Clean.** Applies ten data quality rules. Every rule records how many rows it affected and what it did. Rejected rows are kept with a reason, never silently dropped.
3. **Load.** Writes to a star schema in SQLite: `fact_sales` plus `dim_store` and `dim_product`, with primary keys, foreign keys and `CHECK` constraints.
4. **Reconcile.** Confirms the database row count and total revenue match the cleaned data exactly.
5. **Query.** Runs the KPI queries in `sql/kpi_queries.sql`.
6. **Report.** Builds the Excel workbook and works out key insights from the numbers.

## Data quality rules

| Rule | Issue | Action |
|---|---|---|
| DQ-01 | Exact duplicate rows (batch exported twice) | Removed, first copy kept |
| DQ-02 | Dates in mixed formats (`2025/07/15`, `15-07-2025`) | Converted to `YYYY-MM-DD` |
| DQ-03 | Missing or impossible dates (`N/A`, `2026-02-30`) | Rejected |
| DQ-04 | Store or product ID not in the master data | Rejected |
| DQ-05 | Missing quantity | Rejected, cannot be estimated |
| DQ-06 | Zero or negative quantity | Rejected, returns belong in a separate process |
| DQ-07 | Prices stored as text (`R1 299.00`) | Converted to numeric |
| DQ-08 | Unreadable or non-positive price | Rejected |
| DQ-09 | Region typed inconsistently (`GP`, `gauteng`, `KZN`) | Replaced with region from the store master |
| DQ-10 | Typed region contradicts the store master | Store master used, count reported |

Sample run:

```
DQ-00  Rows received in raw export                    6060
DQ-01  Exact duplicate rows                             60
DQ-02  Dates in non-standard formats                  1172
DQ-03  Missing or impossible dates                      15
DQ-04  Unknown store_id or product_id                   20
DQ-05  Missing quantity                                 40
DQ-06  Zero or negative quantity                        30
DQ-07  Prices with currency symbols or spaces          918
DQ-09  Region spelled inconsistently                  4047
DQ-99  Clean rows loaded                              5895  (97.3% of rows received)

Database load check: OK (5,895 rows, R29,449,228.60)
```

The generator records how many bad rows it planted, and a test confirms the cleaning step rejects exactly that number, no more and no fewer.

## SQL highlights

All queries are in [`sql/kpi_queries.sql`](sql/kpi_queries.sql).

| Query | Technique |
|---|---|
| `monthly_revenue` | CTE plus `LAG()` window function for month on month growth |
| `store_ranking` | `RANK()` nationally and `RANK() OVER (PARTITION BY region)` within each province |
| `revenue_by_region` | Revenue share using a scalar subquery |
| `top_products` | Average discount against list price, joined to the product dimension |
| `category_by_quarter` | Conditional aggregation (`SUM(CASE ...)`) to pivot revenue into financial quarters |

## The report

`output/sales_report.xlsx` contains:

| Sheet | Contents |
|---|---|
| Summary | Headline KPIs, load reconciliation result, and five key insights generated from the data |
| Monthly Trend | Revenue, units, transactions and growth per month, with a line chart |
| Regions | Revenue and share per province, with a bar chart |
| Store Ranking | National and in-region rank for each store |
| Top Products | Top 10 products by revenue with average discount |
| Category by Quarter | Revenue per category per financial quarter |
| Data Quality | The full data quality log |
| Rejected Rows | Every rejected row and the reason |

Insights from the sample data:

- Best month was December 2025; the largest increase was 51.1% in November (Black Friday).
- Gauteng contributed 43.9% of total revenue.
- Top store was Mall of Africa; lowest was Baywest.

## How to run

Requires Python 3.10 or newer.

```bash
pip install -r requirements.txt

python main.py all          # generate data, clean, load, query, report
python main.py generate     # only create mock data
python main.py report       # only rebuild the report from data/

python -m pytest            # run the tests
```

## Design decisions

- **Reject rather than guess.** A missing quantity could be filled with 1, but that would invent sales. Rows that cannot be trusted are rejected and listed with a reason, so the numbers in the report are defensible.
- **Master data is the source of truth.** Region, product name and category come from the reference tables, not from what was typed on the transaction, so every report groups consistently.
- **Prove the load.** The row count and revenue in the database are reconciled to the cleaned data on every run, and the result is shown on the Summary sheet.
- **SQL lives in `.sql` files.** Queries can be reviewed, reused or run directly in any SQLite tool without reading the Python.
- **Database constraints as a second line of defence.** `CHECK (quantity > 0)` and foreign keys mean bad data would fail the load even if a cleaning rule were removed.

## Limitations and next steps

- Ambiguous dates such as `05-03-2026` are read as day first (South African convention). A real export would need the source format confirmed with each branch.
- Returns are excluded. A full solution would load them into their own table and report net sales.
- The pipeline could be scheduled to run nightly and email the report.

## Project structure

```
sales_analysis/
  generate_data.py   mock raw sales plus store and product masters
  clean.py           data quality rules and log
  database.py        SQLite load, named query runner, load reconciliation
  report.py          Excel report, charts and insights
  pipeline.py        runs the full process
sql/
  schema.sql         star schema with constraints
  kpi_queries.sql    named KPI queries
tests/
  test_pipeline.py   cleaning rules, SQL results and end-to-end checks
main.py              command line entry point
```
