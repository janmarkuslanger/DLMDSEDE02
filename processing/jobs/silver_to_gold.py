"""silver -> gold: per-customer ML features for one quarter."""
import datetime

from pyspark.sql import functions as F

from common import parse_quarter, spark_session

year, quarter, months = parse_quarter()
spark = spark_session("silver_to_gold")

quarter_label = "{}Q{}".format(year, quarter)
# Last day of the quarter: first day of the next quarter minus one day.
if quarter == 4:
    quarter_end = datetime.date(year, 12, 31)
else:
    quarter_end = datetime.date(year, quarter * 3 + 1, 1) - datetime.timedelta(days=1)

silver = (
    spark.read.parquet("s3a://silver/transactions")
    .filter((F.col("year") == year) & F.col("month").isin(months))
    .filter(F.col("customer_key").isNotNull())
)

sale = ~F.col("is_return")

gold = (
    silver.groupBy("customer_key")
    .agg(
        F.countDistinct(F.when(sale, F.col("invoice"))).alias("n_orders"),
        F.countDistinct(F.when(F.col("is_return"), F.col("invoice"))).alias("n_return_invoices"),
        F.sum(F.when(sale, F.col("quantity"))).alias("n_items"),
        F.round(F.sum(F.when(sale, F.col("revenue"))), 2).alias("gross_revenue"),
        F.round(F.sum("revenue"), 2).alias("net_revenue"),
        F.countDistinct("stock_code").alias("n_distinct_products"),
        F.max(F.to_date("invoice_ts")).alias("last_purchase"),
        F.max("country").alias("country"),
    )
    .withColumn(
        "avg_order_value",
        F.when(F.col("n_orders") > 0, F.round(F.col("gross_revenue") / F.col("n_orders"), 2)),
    )
    .withColumn(
        "return_rate",
        F.round(F.col("n_return_invoices") / (F.col("n_orders") + F.col("n_return_invoices")), 4),
    )
    .withColumn("recency_days", F.datediff(F.lit(quarter_end), F.col("last_purchase")))
    .withColumn("quarter", F.lit(quarter_label))
)

gold.write.mode("overwrite").partitionBy("quarter").parquet("s3a://gold/customer_features")

print("gold rows for {}: {}".format(quarter_label, gold.count()))
spark.stop()
