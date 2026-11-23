"""bronze -> silver: cleansing and pseudonymization for one quarter."""
import os

from pyspark.sql import functions as F

from common import parse_quarter, spark_session

year, quarter, months = parse_quarter()
spark = spark_session("bronze_to_silver")

paths = ["s3a://bronze/year={:04d}/month={:02d}".format(year, m) for m in months]
bronze = spark.read.option("basePath", "s3a://bronze/").parquet(*paths)

salt = F.lit(os.environ["PSEUDONYM_SALT"])

silver = (
    bronze.select(
        F.col("Invoice").alias("invoice"),
        F.col("StockCode").alias("stock_code"),
        F.col("Description").alias("description"),
        F.col("Quantity").cast("int").alias("quantity"),
        F.col("InvoiceDate").alias("invoice_ts"),
        F.col("Price").cast("double").alias("price"),
        F.col("Customer ID").cast("long").alias("customer_id"),
        F.col("Country").alias("country"),
    )
    # Keep products only: drops POST, M, D, BANK CHARGES, ADJUST, ... and free items.
    .filter(F.col("stock_code").rlike("^[0-9]{5}"))
    .filter(F.col("price") > 0)
    .dropDuplicates()
    .withColumn("is_return", F.col("invoice").startswith("C"))
    .withColumn("revenue", F.round(F.col("quantity") * F.col("price"), 2))
    # Pseudonymize: salted SHA-256, the raw customer id does not leave this job.
    .withColumn(
        "customer_key",
        F.when(
            F.col("customer_id").isNotNull(),
            F.sha2(F.concat(salt, F.col("customer_id").cast("string")), 256),
        ),
    )
    .drop("customer_id")
    .withColumn("year", F.year("invoice_ts"))
    .withColumn("month", F.month("invoice_ts"))
)

silver.write.mode("overwrite").partitionBy("year", "month").parquet("s3a://silver/transactions")

print("bronze rows: {}  silver rows: {}".format(bronze.count(), silver.count()))
spark.stop()
