# DLMDSEDE02 – Batch Data Platform

Batch-processing data architecture for an online retailer (IU, Data Engineering, Task 1).
Monthly transaction exports are ingested, stored in a medallion data lake, processed with
Spark and delivered once per quarter to a serving database for ML training.

The C4 model lives in [`architecture.dsl`](architecture.dsl) (Structurizr DSL).

## Architecture

```
Data source (nginx, monthly CSV)
        │  HTTP
        ▼
Ingestion service (FastAPI) ──► MinIO  bronze ─► (Spark) ─► silver ─► (Spark) ─► gold
        ▲                          └─► quarantine (invalid rows)                     │
        │ HTTP, monthly                                                              │ JDBC
Airflow (orchestration) ── spark-submit, quarterly ──► Spark cluster                 ▼
                                                                          Serving DB (Postgres)
                                                                                     ▲
                                                                          ML application reads
```

| Service | Image | Role |
|---|---|---|
| `data-source` | nginx | Simulates the external source, serves one CSV per month |
| `ingestion` | custom (Python, FastAPI) | Validates schema, writes Parquet to bronze, rejects to quarantine |
| `minio` | `cgr.dev/chainguard/minio` | S3 data lake, one bucket per layer (`bronze`, `silver`, `gold`, `quarantine`) |
| `spark-master`, `spark-worker` ×2 | custom (Spark 3.5.3) | Cleansing, pseudonymization, aggregation |
| `airflow` | custom (Airflow 3.1) | Schedules monthly ingestion and quarterly processing |
| `airflow-db` | postgres:16 | Airflow metadata |
| `serving-db` | postgres:16 | Gold features for the ML application |
| `minio-provision` | hashicorp/terraform | One-shot: buckets, users and policies (IaC) |

### Data flow

* **Ingestion (monthly):** `POST /ingest/{year}/{month}` fetches `YYYY-MM.csv`, checks the
  schema and writes `bronze/year=…/month=…/part-0.parquet`. Invalid rows go to
  `quarantine/…/rejected.parquet` with a reason.
* **bronze → silver:** only product rows (`StockCode` starting with 5 digits, `Price > 0`),
  duplicates removed, `Customer ID` pseudonymized (salted SHA-256), partitioned by year/month.
* **silver → gold:** per-customer features per quarter (orders, revenue, return rate,
  distinct products, recency, …).
* **gold → serving DB:** full reload of `customer_features` via JDBC.

### Reliability, scalability, maintainability, security

* **Reliability:** Airflow retries with backoff; every step is idempotent (fixed partition
  paths overwritten on re-run, dynamic partition overwrite in Spark, full reload into the
  serving DB). Airflow catchup backfills missing months and quarters.
* **Scalability:** services are separate containers and could run on separate machines;
  Spark workers scale horizontally (`docker compose up -d --scale spark-worker=4`).
* **Maintainability:** infrastructure as code (Compose, Terraform), pinned image digests/versions,
  unit tests, small single-purpose jobs.
* **Security / governance:** one MinIO user per service with least-privilege policies
  (`infra/terraform/main.tf`), pseudonymized customer ids in silver and gold, secrets only in
  `.env` (git-ignored), ports bound to `127.0.0.1`.

## Run it

Requirements: Docker with Compose v2 (about 6 GB RAM for Docker).


1. **Dataset:** nothing to do. *Online Retail II* (about 1.07 million rows, Dec 2009 – Dec 2011,
   CC BY 4.0) is shipped as `data/online_retail_II.zip`, see [`data/README.md`](data/README.md).
2. **Configuration:** `cp .env.example .env` and replace the placeholder secrets.
3. **Start:**
   ```bash
   docker compose build          # first build downloads Spark/Airflow dependencies (several minutes)
   docker compose up -d
   ```
   The `seed` container splits the CSV into monthly files, `minio-provision` creates buckets,
   users and policies.
4. **Run the pipeline:** open Airflow at <http://localhost:8081> (user `admin`, password
   `AIRFLOW_ADMIN_PASSWORD` from `.env`). Both DAGs are active; `monthly_ingestion` backfills
   all 25 months, `quarterly_processing` waits for each quarter's months in bronze and then
   runs the Spark jobs.
5. **Check the result:**
   ```bash
   docker compose exec serving-db psql -U serving -d serving \
     -c "SELECT quarter, count(*) FROM customer_features GROUP BY quarter ORDER BY quarter;"
   ```

| UI | URL |
|---|---|
| Airflow | <http://localhost:8081> |
| Spark master | <http://localhost:8080> |
| MinIO console | <http://localhost:9001> |

### Run steps manually (without Airflow)

```bash
curl -X POST localhost:8000/ingest/2010/1          # repeat for months 2 and 3
docker compose run --rm spark-job /jobs/bronze_to_silver.py --quarter 2010Q1
docker compose run --rm spark-job /jobs/silver_to_gold.py --quarter 2010Q1
docker compose run --rm spark-job /jobs/load_serving.py
```

### Tests

```bash
docker run --rm -v "$PWD":/repo -w /repo python:3.12-slim sh -c \
  "pip install -q -r ingestion/requirements.txt -r ingestion/requirements-dev.txt \
   && (cd ingestion && python -m pytest -q tests) && (cd source && python -m pytest -q tests)"
```

### Architecture diagrams (PNG with legend)

```bash
scripts/export-diagrams.sh     # writes PNGs to out/
```

## Known limitations

* Single Airflow instance (`airflow standalone`) is a single point of failure; monitor it
  (Airflow UI, container health). In production it would run with separate scheduler/API
  server components and a non-local executor.
* Terraform state is local (`infra/terraform/terraform.tfstate`, git-ignored).
* Business rules in silver are a deliberate simplification (see `processing/jobs/`).
