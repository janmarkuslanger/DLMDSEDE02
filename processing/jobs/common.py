"""Shared helpers for the PySpark jobs (runs on Python 3.8 in the spark image)."""
import argparse
import os
import re

from pyspark.sql import SparkSession


def parse_quarter(argv=None):
    """--quarter 2010Q1 -> (2010, 1, [1, 2, 3])"""
    p = argparse.ArgumentParser()
    p.add_argument("--quarter", required=True, help="e.g. 2010Q1")
    q = p.parse_args(argv).quarter
    m = re.fullmatch(r"(\d{4})Q([1-4])", q)
    if not m:
        raise SystemExit("invalid --quarter, expected e.g. 2010Q1")
    year, quarter = int(m.group(1)), int(m.group(2))
    months = [(quarter - 1) * 3 + i for i in (1, 2, 3)]
    return year, quarter, months


def spark_session(name):
    spark = (
        SparkSession.builder.appName(name)
        .config("spark.hadoop.fs.s3a.endpoint", os.environ["S3_ENDPOINT"])
        .config("spark.hadoop.fs.s3a.access.key", os.environ["S3_ACCESS_KEY"])
        .config("spark.hadoop.fs.s3a.secret.key", os.environ["S3_SECRET_KEY"])
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        # Re-running a quarter replaces only its partitions (idempotent).
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark
