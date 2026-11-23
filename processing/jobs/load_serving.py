"""gold -> serving DB: loads all gold quarters into Postgres (full reload, idempotent)."""
import os

from common import spark_session

spark = spark_session("load_serving")

gold = spark.read.parquet("s3a://gold/customer_features")

(
    gold.write.format("jdbc")
    .option("url", "jdbc:postgresql://serving-db:5432/" + os.environ["SERVING_DB_NAME"])
    .option("dbtable", "customer_features")
    .option("user", os.environ["SERVING_DB_USER"])
    .option("password", os.environ["SERVING_DB_PASSWORD"])
    .option("driver", "org.postgresql.Driver")
    .option("truncate", "true")
    .mode("overwrite")
    .save()
)

print("loaded {} rows into customer_features".format(gold.count()))
spark.stop()
