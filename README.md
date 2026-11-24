# DLMDSEDE02 – Batch Data Platform

Batch data platform for an online retailer (IU Data Engineering, Task 1): monthly ingestion,
medallion data lake, Spark processing, quarterly delivery to a serving DB for ML training.
C4 model: [`architecture.dsl`](architecture.dsl).

## Architecture

```
Data source (nginx) ─HTTP─► Ingestion (FastAPI) ─► MinIO: bronze ─Spark─► silver ─Spark─► gold ─JDBC─► Serving DB
                                  ▲                      └► quarantine (invalid rows)                      ▲
                                  │ monthly                                                    ML application reads
                         Airflow ─┴─ spark-submit, quarterly ─► Spark cluster
```

| Service | Image | Role |
|---|---|---|
| `data-source` | nginx | Serves one CSV per month (simulated source) |
| `ingestion` | custom, FastAPI | Schema check, Parquet to bronze, rejects to quarantine |
| `minio` | `cgr.dev/chainguard/minio` | Data lake, one bucket per layer |
| `spark-master`, `spark-worker` ×2 | custom, Spark 3.5.3 | Cleansing, pseudonymization, aggregation |
| `airflow` | custom, Airflow 3.1 | Monthly ingestion, quarterly processing |
| `airflow-db`, `serving-db` | postgres:16 | Airflow metadata, ML features |
| `minio-provision` | terraform | One-shot: buckets, users, policies |

## Data flow

* **Ingest** (`POST /ingest/{year}/{month}`): bronze Parquet per month; invalid rows to quarantine.
* **Silver:** product rows only, deduplicated, `Customer ID` pseudonymized (salted SHA-256).
* **Gold:** per-customer features per quarter (orders, revenue, return rate, recency, …).
* **Serving DB:** full reload of `customer_features`.

## Quality attributes

| | Measure |
|---|---|
| Reliability | Airflow retries with backoff, idempotent steps (fixed partition paths, overwrite), catchup backfill |
| Scalability | Separate containers, horizontally scalable Spark workers |
| Maintainability | Compose and Terraform (IaC), pinned images, unit tests |
| Security | Least-privilege MinIO user per service, pseudonymization, secrets in `.env`, ports on `127.0.0.1` |

## Run

Requires Docker with Compose v2 (≥ 6 GB RAM recommended). The dataset is included
(`data/online_retail_II.zip`, see [`data/README.md`](data/README.md)).

```bash
cp .env.example .env          # replace the placeholder secrets
docker compose build          # first build: several minutes (large images)
docker compose up -d          # then Airflow backfills everything: ~10-15 min
```

Airflow: <http://localhost:8081> (`admin` / `AIRFLOW_ADMIN_PASSWORD` from `.env`).
Spark: <http://localhost:8080>. MinIO: <http://localhost:9001>.

Result (8 quarters, 2010Q1–2011Q4):

```bash
docker compose exec serving-db psql -U serving -d serving \
  -c "SELECT quarter, count(*) FROM customer_features GROUP BY quarter ORDER BY quarter;"
```

Single steps without Airflow:

```bash
curl -X POST localhost:8000/ingest/2010/1        # also months 2, 3
docker compose run --rm spark-job /jobs/bronze_to_silver.py --quarter 2010Q1
docker compose run --rm spark-job /jobs/silver_to_gold.py --quarter 2010Q1
docker compose run --rm spark-job /jobs/load_serving.py
```

Reset: `docker compose down -v`.

## Tests

Unit tests cover ingestion validation and the seed script. The Spark jobs and DAGs are
verified end to end by the pipeline run.

```bash
docker run --rm -v "$PWD":/repo -w /repo python:3.12-slim sh -c \
  "pip install -q -r ingestion/requirements.txt -r ingestion/requirements-dev.txt \
   && (cd ingestion && python -m pytest -q tests) && (cd source && python -m pytest -q tests)"
```

## Diagrams

`scripts/export-diagrams.sh` writes PNGs with legend to `out/`.

## Troubleshooting

* **Image build fails while downloading a JAR:** network hiccup, run `docker compose build` again.
* **Pipeline looks stuck:** check DAG runs in Airflow; the quarterly DAG waits for bronze data.
* **Port in use:** 8000, 8080, 8081, 9000, 9001, 5433 must be free.

## Known limitations

* Airflow runs as `standalone` (single point of failure), so monitor it.
* Terraform state is local and git-ignored.
* Silver business rules are deliberately simple (`processing/jobs/`).
