# Builds the Excel performance report from the query results.
# The whole workbook is regenerated on every run, so there is no manual copying of numbers into spreadsheets.

from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(color="FFFFFF", bold=True)
TITLE_FONT = Font(size=14, bold=True, color="1F4E79")
MONEY = "#,##0.00"
INTEGER = "#,##0"

MONEY_COLUMNS = {"revenue", "total_revenue", "avg_transaction_value", "avg_selling_price", "unit_price",
                 "q1_jul_sep", "q2_oct_dec", "q3_jan_mar", "q4_apr_jun", "total"}
INT_COLUMNS = {"units", "units_sold", "transactions", "quantity", "rows_affected"}


def insights(results):
    # Plain-language findings worked out from the numbers, not typed in by hand
    monthly = results["monthly_revenue"]
    regions = results["revenue_by_region"]
    stores = results["store_ranking"]
    products = results["top_products"]
    best_month = monthly.loc[monthly["revenue"].idxmax()]
    worst_month = monthly.loc[monthly["revenue"].idxmin()]
    growth = monthly.dropna(subset=["mom_growth_pct"])
    biggest_jump = growth.loc[growth["mom_growth_pct"].idxmax()]
    top_region = regions.iloc[0]
    return [
        f"Best month was {best_month['month']} at R{best_month['revenue']:,.2f}; "
        f"weakest was {worst_month['month']} at R{worst_month['revenue']:,.2f}.",
        f"Largest month on month increase was {biggest_jump['mom_growth_pct']:.1f}% in {biggest_jump['month']}.",
        f"{top_region['region']} contributed {top_region['revenue_share_pct']:.1f}% of total revenue.",
        f"Top store was {stores.iloc[0]['store_name']} ({stores.iloc[0]['region']}); "
        f"lowest was {stores.iloc[-1]['store_name']} ({stores.iloc[-1]['region']}).",
        f"{products.iloc[0]['product_name']} was the highest revenue product at R{products.iloc[0]['revenue']:,.2f}.",
    ]


def _format_table(ws, df, start_row=1):
    for cell in ws[start_row]:
        if cell.value is not None:
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
    for idx, col in enumerate(df.columns, start=1):
        letter = get_column_letter(idx)
        fmt = MONEY if col in MONEY_COLUMNS else INTEGER if col in INT_COLUMNS else None
        if fmt:
            for row in range(start_row + 1, start_row + len(df) + 1):
                ws[f"{letter}{row}"].number_format = fmt
        longest = max([len(str(col))] + [len(f"{v:,.2f}") if isinstance(v, float) else len(str(v))
                                         for v in df[col].head(200)])
        ws.column_dimensions[letter].width = max(ws.column_dimensions[letter].width or 0, min(longest + 3, 45))
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)


def _sheet(xw, name, df, start_row=0):
    df.to_excel(xw, sheet_name=name, index=False, startrow=start_row)
    ws = xw.book[name]
    _format_table(ws, df, start_row + 1)
    return ws


def write_excel(path, results, dq_log, rejected, load_check):
    path = Path(path)
    totals = results["kpi_totals"].iloc[0]

    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        kpis = pd.DataFrame([
            ("Total revenue (R)", totals["total_revenue"]),
            ("Units sold", totals["units_sold"]),
            ("Transactions", totals["transactions"]),
            ("Average transaction value (R)", totals["avg_transaction_value"]),
            ("Period covered", f"{totals['first_sale']} to {totals['last_sale']}"),
            ("Report generated", datetime.now().strftime("%Y-%m-%d %H:%M")),
            ("Database reconciles to cleaned data",
             "Yes" if load_check["rows_match"] and load_check["revenue_match"] else "NO, investigate"),
        ], columns=["Metric", "Value"])
        kpis.to_excel(xw, sheet_name="Summary", index=False, startrow=2)
        ws = xw.book["Summary"]
        ws["A1"] = "Sales Performance Report"
        ws["A1"].font = TITLE_FONT
        for cell in ws[3]:
            if cell.value is not None:
                cell.fill = HEADER_FILL
                cell.font = HEADER_FONT
        ws["B4"].number_format = MONEY
        ws["B5"].number_format = INTEGER
        ws["B6"].number_format = INTEGER
        ws["B7"].number_format = MONEY
        ws.column_dimensions["A"].width = 38
        ws.column_dimensions["B"].width = 30
        ws["A12"] = "Key insights"
        ws["A12"].font = Font(bold=True, size=12, color="1F4E79")
        for i, line in enumerate(insights(results)):
            ws[f"A{13 + i}"] = f"{i + 1}. {line}"

        monthly = results["monthly_revenue"]
        ws = _sheet(xw, "Monthly Trend", monthly)
        line = LineChart()
        line.title = "Monthly revenue (R)"
        line.legend = None
        line.add_data(Reference(ws, min_col=2, min_row=1, max_row=len(monthly) + 1), titles_from_data=True)
        line.set_categories(Reference(ws, min_col=1, min_row=2, max_row=len(monthly) + 1))
        # Straight segments show the real monthly values; smoothing would invent peaks that never happened
        for series in line.series:
            series.smooth = False
        line.y_axis.numFmt = "#,##0"
        line.height, line.width = 9, 20
        ws.add_chart(line, "H2")

        regions = results["revenue_by_region"]
        ws = _sheet(xw, "Regions", regions)
        bar = BarChart()
        bar.title = "Revenue by region (R)"
        bar.legend = None
        bar.add_data(Reference(ws, min_col=2, min_row=1, max_row=len(regions) + 1), titles_from_data=True)
        bar.set_categories(Reference(ws, min_col=1, min_row=2, max_row=len(regions) + 1))
        bar.y_axis.numFmt = "#,##0"
        bar.height, bar.width = 8, 16
        ws.add_chart(bar, "G2")

        _sheet(xw, "Store Ranking", results["store_ranking"])
        _sheet(xw, "Top Products", results["top_products"])
        _sheet(xw, "Category by Quarter", results["category_by_quarter"])
        _sheet(xw, "Data Quality", dq_log)
        if len(rejected):
            _sheet(xw, "Rejected Rows", rejected)
