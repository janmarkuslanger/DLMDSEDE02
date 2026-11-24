import csv
import subprocess
import sys
from pathlib import Path

SEED = Path(__file__).resolve().parents[1] / "seed.py"
HEADER = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]


def test_seed_splits_rows_by_invoice_month(tmp_path):
    src = tmp_path / "in.csv"
    rows = [
        ["1", "A", "d", "1", "2009-12-01 07:45:00", "1.0", "1.0", "UK"],
        ["2", "B", "d", "1", "2009-12-31 23:59:59", "1.0", "1.0", "UK"],
        ["3", "C", "d", "1", "2010-01-01 00:00:00", "1.0", "1.0", "UK"],
    ]
    with src.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)

    out = tmp_path / "slices"
    subprocess.run([sys.executable, str(SEED), str(src), str(out)], check=True)

    assert sorted(p.name for p in out.iterdir()) == ["2009-12.csv", "2010-01.csv"]
    dec = list(csv.reader((out / "2009-12.csv").open()))
    assert dec[0] == HEADER and len(dec) == 3  # header + 2 rows
    jan = list(csv.reader((out / "2010-01.csv").open()))
    assert len(jan) == 2
