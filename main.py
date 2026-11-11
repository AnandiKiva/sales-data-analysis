# Command line entry point.
#   python main.py generate     create mock raw data in data/
#   python main.py report       clean, load to SQLite, run KPI queries, build the Excel report
#   python main.py all          both of the above

import argparse
import time

from sales_analysis import generate_data, pipeline
from sales_analysis.report import insights


def cmd_generate(args):
    raw, _, _, planted = generate_data.write(args.data_dir, args.transactions, args.seed)
    print(f"Wrote {len(raw):,} raw sales rows to {args.data_dir}/")
    print("Dirty data planted:")
    for name, count in planted.items():
        print(f"  {name}: {count}")


def cmd_report(args):
    started = time.perf_counter()
    out = pipeline.run(args.data_dir, args.out_dir)
    elapsed = time.perf_counter() - started

    print("Data quality log:")
    for r in out["dq_log"].itertuples(index=False):
        print(f"  {r.rule_id}  {r.rule:<44} {r.rows_affected:>6}  {r.action}")

    check = out["load_check"]
    status = "OK" if check["rows_match"] and check["revenue_match"] else "MISMATCH"
    print(f"\nDatabase load check: {status} ({check['db_rows']:,} rows, R{check['db_revenue']:,.2f})")

    print("\nKey insights:")
    for line in insights(out["results"]):
        print(f"  - {line}")
    print(f"\nReport written to {args.out_dir}/sales_report.xlsx in {elapsed:.1f} seconds")


def main():
    parser = argparse.ArgumentParser(description="Sales data analysis and automated reporting")
    parser.add_argument("command", choices=["generate", "report", "all"])
    parser.add_argument("--transactions", type=int, default=6000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--out-dir", default="output")
    args = parser.parse_args()

    if args.command in ("generate", "all"):
        cmd_generate(args)
    if args.command in ("report", "all"):
        if args.command == "all":
            print()
        cmd_report(args)


if __name__ == "__main__":
    main()
