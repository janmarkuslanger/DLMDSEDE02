"""Ingestion service: fetches the monthly CSV export, validates the schema,
writes valid rows as Parquet to bronze and invalid rows to quarantine.

Idempotent: the target path is fixed per month and overwritten on re-run.
"""
import io
import os
import re

import boto3
import pandas as pd
import requests
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException

SOURCE_URL = os.environ["SOURCE_URL"]
S3_ENDPOINT = os.environ["S3_ENDPOINT"]
BRONZE = os.environ.get("BRONZE_BUCKET", "bronze")
QUARANTINE = os.environ.get("QUARANTINE_BUCKET", "quarantine")

COLUMNS = [
    "Invoice", "StockCode", "Description", "Quantity",
    "InvoiceDate", "Price", "Customer ID", "Country",
]

app = FastAPI(title="Ingestion Service")
s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=os.environ["S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["S3_SECRET_KEY"],
)


def validate(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Schema validation only; business cleansing happens in silver."""
    df = raw.copy()
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    df["Customer ID"] = pd.to_numeric(df["Customer ID"], errors="coerce")

    reason = pd.Series("", index=df.index)
    reason[raw["Invoice"].isna() | (raw["Invoice"] == "")] = "missing Invoice"
    reason[raw["StockCode"].isna() | (raw["StockCode"] == "")] = "missing StockCode"
    reason[df["Quantity"].isna()] = "invalid Quantity"
    reason[df["Price"].isna()] = "invalid Price"
    reason[df["InvoiceDate"].isna()] = "invalid InvoiceDate"
    # Customer ID may be empty in the source; only a non-numeric value is invalid.
    bad_customer = raw["Customer ID"].notna() & (raw["Customer ID"] != "") & df["Customer ID"].isna()
    reason[bad_customer] = "invalid Customer ID"

    invalid = reason != ""
    quarantined = raw[invalid].assign(reason=reason[invalid])
    return df[~invalid], quarantined


def put_parquet(df: pd.DataFrame, bucket: str, key: str) -> None:
    buf = io.BytesIO()
    # Spark 3.5 cannot read nanosecond timestamps (pandas default), so write microseconds.
    df.to_parquet(buf, index=False, coerce_timestamps="us", allow_truncated_timestamps=True)
    s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ingest/{year}/{month}")
def ingest(year: int, month: int) -> dict:
    if not (2000 <= year <= 2100 and 1 <= month <= 12):
        raise HTTPException(status_code=422, detail="invalid year/month")

    name = f"{year:04d}-{month:02d}.csv"
    resp = requests.get(f"{SOURCE_URL}/{name}", timeout=60)
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"no export for {year}-{month:02d}")
    resp.raise_for_status()

    raw = pd.read_csv(io.StringIO(resp.text), dtype=str, keep_default_na=False)
    missing = [c for c in COLUMNS if c not in raw.columns]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing columns: {missing}")
    raw = raw[COLUMNS].replace("", pd.NA)

    valid, quarantined = validate(raw)

    prefix = f"year={year:04d}/month={month:02d}"
    put_parquet(valid, BRONZE, f"{prefix}/part-0.parquet")

    q_key = f"{prefix}/rejected.parquet"
    if len(quarantined):
        put_parquet(quarantined.astype(str), QUARANTINE, q_key)
    else:
        # Re-run with a now-clean export: remove a stale quarantine file.
        try:
            s3.delete_object(Bucket=QUARANTINE, Key=q_key)
        except ClientError:
            pass

    return {
        "month": f"{year:04d}-{month:02d}",
        "rows_read": len(raw),
        "rows_bronze": len(valid),
        "rows_quarantine": len(quarantined),
    }
