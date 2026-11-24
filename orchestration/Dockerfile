# Python 3.10 variant: PySpark requires the same Python minor version as the Spark workers.
FROM apache/airflow:3.1.0-python3.10

# Java for the spark-submit driver (client mode, spark-submit runs inside this container).
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless curl \
    && rm -rf /var/lib/apt/lists/*

USER airflow
RUN pip install --no-cache-dir pyspark==3.5.3 boto3==1.35.90

# The driver needs the same connectors as the workers (S3A, Postgres JDBC), see processing/Dockerfile.
ENV SPARK_HOME=/home/airflow/.local/lib/python3.10/site-packages/pyspark
ENV PATH="${SPARK_HOME}/bin:${PATH}"
RUN set -eux; \
    mvn=https://repo1.maven.org/maven2; \
    for jar in \
      org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar \
      com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar \
      org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar; do \
        out="${SPARK_HOME}/jars/$(basename "$jar")"; \
        n=0; \
        until curl -fsSL -C - -o "$out" "$mvn/$jar"; do \
          n=$((n+1)); [ "$n" -lt 15 ] || exit 1; sleep 3; \
        done; \
    done
