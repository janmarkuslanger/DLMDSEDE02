"""Quarterly processing: bronze -> silver -> gold -> serving DB for the quarter that just ended.

Waits until all three months of the quarter have been ingested into bronze, then submits
the PySpark jobs to the Spark cluster. All jobs are idempotent, so a failed run can simply
be retried or cleared.
"""
import os
from datetime import timedelta

import boto3
import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag, task
from airflow.timetables.interval import CronDataIntervalTimetable

S3_ENDPOINT = os.environ["S3_ENDPOINT"]
SPARK_MASTER = os.environ["SPARK_MASTER"]

# Quarter label for a run, e.g. data_interval_start = 2010-01-01 -> 2010Q1
QUARTER = "{{ data_interval_start.year }}Q{{ ((data_interval_start.month - 1) // 3) + 1 }}"

SPARK_SUBMIT = (
    "spark-submit --master " + SPARK_MASTER + " "
    "--conf spark.driver.host=$(hostname -i) "
    "/opt/airflow/jobs/{job}.py {args}"
)

# Spark jobs use the least-privilege "spark" user, not the orchestration user.
SPARK_ENV = {
    "S3_ACCESS_KEY": "spark",
    "S3_SECRET_KEY": os.environ["SPARK_S3_SECRET"],
}


@dag(
    dag_id="quarterly_processing",
    # Interval timetable: the run for [Jan 1, Apr 1) starts on Apr 1 and processes Q1.
    schedule=CronDataIntervalTimetable("0 0 1 1,4,7,10 *", timezone="UTC"),
    start_date=pendulum.datetime(2010, 1, 1, tz="UTC"),
    end_date=pendulum.datetime(2011, 10, 1, tz="UTC"),  # last (partial) quarter in the dataset
    catchup=True,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=1),
    },
    tags=["processing"],
)
def quarterly_processing():
    @task.sensor(poke_interval=30, timeout=60 * 60, mode="reschedule")
    def wait_for_bronze(data_interval_start=None):
        """All three months of the quarter must be present in bronze."""
        s3 = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id="orchestration",
            aws_secret_access_key=os.environ["ORCHESTRATION_S3_SECRET"],
        )
        first = data_interval_start.month
        for month in (first, first + 1, first + 2):
            prefix = f"year={data_interval_start.year:04d}/month={month:02d}/"
            resp = s3.list_objects_v2(Bucket="bronze", Prefix=prefix, MaxKeys=1)
            if resp.get("KeyCount", 0) == 0:
                print(f"bronze missing {prefix}")
                return False
        return True

    bronze_to_silver = BashOperator(
        task_id="bronze_to_silver",
        bash_command=SPARK_SUBMIT.format(job="bronze_to_silver", args="--quarter " + QUARTER),
        env=SPARK_ENV,
        append_env=True,
    )
    silver_to_gold = BashOperator(
        task_id="silver_to_gold",
        bash_command=SPARK_SUBMIT.format(job="silver_to_gold", args="--quarter " + QUARTER),
        env=SPARK_ENV,
        append_env=True,
    )
    load_serving = BashOperator(
        task_id="load_serving",
        bash_command=SPARK_SUBMIT.format(job="load_serving", args=""),
        env=SPARK_ENV,
        append_env=True,
    )

    wait_for_bronze() >> bronze_to_silver >> silver_to_gold >> load_serving


quarterly_processing()
