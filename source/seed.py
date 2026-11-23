"""Splits the Online Retail II CSV into one file per month (YYYY-MM.csv).

The slices simulate the monthly export of an external source system and are
served by the data-source container. Standard library only, so it runs in a
plain python image.
"""
import csv
import sys
from pathlib import Path

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/data/online_retail_II.csv")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "/data/slices")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    writers: dict[str, tuple] = {}
    rows = 0

    with SRC.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        date_idx = header.index("InvoiceDate")

        for row in reader:
            month = row[date_idx][:7]  # "2010-01-04 09:24:00" -> "2010-01"
            if month not in writers:
                fh = (OUT / f"{month}.csv").open("w", newline="", encoding="utf-8")
                w = csv.writer(fh)
                w.writerow(header)
                writers[month] = (fh, w)
            writers[month][1].writerow(row)
            rows += 1

    for fh, _ in writers.values():
        fh.close()

    print(f"seed: {rows} rows -> {len(writers)} monthly files in {OUT}")


if __name__ == "__main__":
    main()
