# Ubuntu/Python 3.10 variant: PySpark needs the same Python minor version on driver (Airflow image) and workers.
FROM apache/spark:3.5.3-scala2.12-java17-python3-ubuntu

# Connectors baked into the image so every node has them and no download happens at run time:
# S3A (MinIO) and the Postgres JDBC driver. Versions match Hadoop 3.3.4 shipped with Spark 3.5.3.
# Retry loop with resume (-C -): the AWS SDK bundle is ~270 MB and a plain ADD fails on flaky networks.
USER root
RUN set -eux; \
    mvn=https://repo1.maven.org/maven2; \
    for jar in \
      org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar \
      com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar \
      org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar; do \
        out="/opt/spark/jars/$(basename "$jar")"; \
        n=0; \
        until curl -fsSL -C - -o "$out" "$mvn/$jar"; do \
          n=$((n+1)); [ "$n" -lt 15 ] || exit 1; sleep 3; \
        done; \
        chmod 644 "$out"; \
    done
USER spark
