"""Splits the Online Retail II dataset into one CSV per month (YYYY-MM.csv).

The input is the CSV or the ZIP archive from Kaggle (the repo ships the ZIP). The slices simulate the monthly export of an external source system and are
served by the data-source container. Standard library only, so it runs in a
plain python image.
"""
import csv
import io
import sys
import zipfile
from contextlib import contextmanager
from pathlib import Path

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/data/online_retail_II.zip")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "/data/slices")


@contextmanager
def open_source(path: Path):
    """Yield a text stream for the CSV, either plain or inside a ZIP archive."""
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
            with zf.open(name) as raw, io.TextIOWrapper(raw, encoding="utf-8", newline="") as f:
                yield f
    else:
        with path.open(newline="", encoding="utf-8") as f:
            yield f


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    writers: dict[str, tuple] = {}
    rows = 0

    with open_source(SRC) as f:
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
