"""Monthly ingestion: triggers the ingestion service for the month that just ended.

Catchup is on, so unpausing the DAG backfills every missing month. Re-running a month
is safe because the ingestion service overwrites a fixed partition (idempotent).
"""
import os
from datetime import timedelta

import pendulum
import requests
from airflow.sdk import dag, task
from airflow.timetables.interval import CronDataIntervalTimetable

INGESTION_URL = os.environ["INGESTION_URL"]


@dag(
    dag_id="monthly_ingestion",
    # Interval timetable: a run starts after its interval has ended (the run for
    # [Dec 1, Jan 1) starts on Jan 1), so the month it ingests is complete.
    schedule=CronDataIntervalTimetable("0 0 1 * *", timezone="UTC"),
    start_date=pendulum.datetime(2009, 12, 1, tz="UTC"),
    end_date=pendulum.datetime(2011, 12, 1, tz="UTC"),  # last month in the dataset
    catchup=True,
    max_active_runs=1,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(seconds=30),
        "retry_exponential_backoff": True,
    },
    tags=["ingestion"],
)
def monthly_ingestion():
    @task
    def ingest(data_interval_start=None):
        # The run for interval [Dec 1, Jan 1) ingests December.
        year, month = data_interval_start.year, data_interval_start.month
        resp = requests.post(f"{INGESTION_URL}/ingest/{year}/{month}", timeout=300)
        resp.raise_for_status()
        result = resp.json()
        print(result)
        return result

    ingest()


monthly_ingestion()
