workspace "Batch Data Platform" "C4 model for the IU portfolio Data Engineering (DLMDSEDE02), task 1: batch processing" {

    !identifiers hierarchical

    model {
        engineer = person "Data Engineer" "Operates and monitors the pipelines"

        source = softwareSystem "Data Source" "Provides monthly transaction exports as CSV (Online Retail II, simulated via seed.py)" {
            tags "External"
        }

        mlApp = softwareSystem "ML Application" "Trains a new model version every quarter" {
            tags "External"
        }

        platform = softwareSystem "Batch Data Platform" "Ingests, stores, processes and delivers transaction data for quarterly ML training" {
            orchestration = container "Orchestration" "Schedules monthly ingestion and quarterly processing; retries and backfills" "Apache Airflow, Python DAGs"
            airflowDb = container "Airflow Metadata DB" "DAG runs and task states" "PostgreSQL" {
                tags "Database"
            }
            ingestion = container "Ingestion Service" "Fetches the monthly CSV export, validates the schema, writes Parquet to bronze; invalid rows to quarantine" "Python, FastAPI"
            processing = container "Batch Processing Jobs" "bronze to silver: cleansing, pseudonymization; silver to gold: aggregation into ML features" "PySpark on Apache Spark"
            lake = container "Data Lake" "Medallion layers bronze, silver, gold (+ quarantine); Parquet partitioned by year/month" "MinIO, S3 API" {
                tags "Database"
            }
            servingDb = container "Serving DB" "Gold features for ML training, versioned per quarter" "PostgreSQL" {
                tags "Database"
            }
        }

        # Relationships
        engineer -> platform.orchestration "Monitors DAGs, triggers backfills" "HTTPS, web UI"
        platform.orchestration -> platform.airflowDb "Reads/writes state" "SQL"
        platform.orchestration -> platform.ingestion "Triggers ingestion per month" "HTTP/REST, monthly"
        platform.orchestration -> platform.processing "Submits cleansing and aggregation jobs" "spark-submit, quarterly"
        platform.ingestion -> source "Fetches monthly CSV export" "HTTPS, monthly"
        platform.ingestion -> platform.lake "Writes bronze and quarantine" "S3 API"
        platform.processing -> platform.lake "Reads bronze/silver, writes silver/gold" "S3A"
        platform.processing -> platform.servingDb "Loads gold features per quarter" "JDBC"
        mlApp -> platform.servingDb "Reads training data" "SQL, quarterly"

        # Deployment: everything runs locally via docker-compose
        local = deploymentEnvironment "Local" {
            deploymentNode "Developer Machine" "Single host for development and grading" "Docker Engine, docker-compose" {

                deploymentNode "data-source" "Simulated external source serving monthly CSV files" "Docker container: nginx:alpine" {
                    softwareSystemInstance source
                }

                deploymentNode "airflow" "Scheduler, DAG processor and API server (standalone)" "Docker container: apache/airflow" {
                    containerInstance platform.orchestration
                }
                deploymentNode "airflow-db" "" "Docker container: postgres" {
                    containerInstance platform.airflowDb
                }

                deploymentNode "ingestion" "" "Docker container: custom image (python:3.12-slim)" {
                    containerInstance platform.ingestion
                }

                deploymentNode "Spark Cluster" "Standalone cluster, workers scale horizontally" "Apache Spark" {
                    deploymentNode "spark-master" "Cluster manager" "Docker container: spark" {
                    }
                    deploymentNode "spark-worker" "Executes the PySpark jobs" "Docker container: spark" "" 2 {
                        containerInstance platform.processing
                    }
                }

                deploymentNode "minio" "" "Docker container: minio/minio" {
                    containerInstance platform.lake
                    infrastructureNode "minio-init" "Creates buckets, users and policies on startup (one-shot)" "Docker container: minio/mc"
                }

                deploymentNode "serving-db" "" "Docker container: postgres" {
                    containerInstance platform.servingDb
                }
            }
        }
    }

    views {
        systemContext platform "SystemContext" "Level 1: system context" {
            include *
            autoLayout lr
        }

        container platform "Containers" "Level 2: containers" {
            include *
            autoLayout tb
        }

        deployment platform "Local" "Deployment" "Local deployment via docker-compose" {
            include *
            autoLayout lr
        }

        styles {
            element "Person" {
                shape Person
                background #08427B
                color #ffffff
            }
            element "Software System" {
                background #1168BD
                color #ffffff
            }
            element "Container" {
                background #438DD5
                color #ffffff
            }
            element "External" {
                background #999999
                color #ffffff
            }
            element "Database" {
                shape Cylinder
            }
            element "Infrastructure Node" {
                background #ffffff
                color #000000
            }
            relationship "Relationship" {
                dashed true
            }
        }
    }
}