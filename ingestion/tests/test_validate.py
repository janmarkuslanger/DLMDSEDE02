import os

import pandas as pd

# app.main reads its configuration at import time.
os.environ.setdefault("SOURCE_URL", "http://source")
os.environ.setdefault("S3_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "test")
os.environ.setdefault("S3_SECRET_KEY", "test")

from app.main import COLUMNS, validate  # noqa: E402


def frame(*rows):
    """Build a raw (all-string) frame like the CSV reader does; blanks become NA."""
    return pd.DataFrame(rows, columns=COLUMNS).replace("", pd.NA)


GOOD = ("489434", "85048", "GLASS BALL", "12", "2009-12-01 07:45:00", "6.95", "13085.0", "United Kingdom")


def test_valid_row_passes_with_typed_columns():
    valid, rejected = validate(frame(GOOD))
    assert len(valid) == 1 and rejected.empty
    assert valid.iloc[0]["Quantity"] == 12
    assert valid.iloc[0]["Price"] == 6.95
    assert valid.iloc[0]["InvoiceDate"] == pd.Timestamp("2009-12-01 07:45:00")


def test_missing_customer_id_is_valid():
    row = GOOD[:6] + ("",) + GOOD[7:]
    valid, rejected = validate(frame(row))
    assert len(valid) == 1 and rejected.empty


def test_return_with_negative_quantity_is_valid():
    row = ("C489449", "22087", "PAPER BUNTING", "-12", "2009-12-01 09:06:00", "2.95", "16321.0", "Australia")
    valid, rejected = validate(frame(row))
    assert len(valid) == 1 and rejected.empty


def test_invalid_rows_are_quarantined_with_reason():
    rows = [
        ("1", "85048", "x", "abc", "2009-12-01 07:45:00", "1.0", "1.0", "FR"),        # Quantity
        ("2", "", "x", "1", "2009-12-01 07:45:00", "1.0", "1.0", "FR"),               # StockCode
        ("3", "85048", "x", "1", "not-a-date", "1.0", "1.0", "FR"),                   # InvoiceDate
        ("4", "85048", "x", "1", "2009-12-01 07:45:00", "n/a", "1.0", "FR"),          # Price
        ("5", "85048", "x", "1", "2009-12-01 07:45:00", "1.0", "ABC", "FR"),          # Customer ID
    ]
    valid, rejected = validate(frame(*rows))
    assert valid.empty
    assert list(rejected["reason"]) == [
        "invalid Quantity",
        "missing StockCode",
        "invalid InvoiceDate",
        "invalid Price",
        "invalid Customer ID",
    ]


def test_valid_and_invalid_rows_are_split():
    bad = ("9", "85048", "x", "abc", "2009-12-01 07:45:00", "1.0", "1.0", "FR")
    valid, rejected = validate(frame(GOOD, bad))
    assert len(valid) == 1 and len(rejected) == 1
