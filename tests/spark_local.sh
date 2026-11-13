#!/usr/bin/env bash
# Run a lakehouse Spark job locally against a throwaway Iceberg catalog, to test changes
# before submitting them to watsonx.data.
#   JAVA_HOME=... SPARK_SUBMIT=... tests/spark_local.sh bronze_ingest.py|silver_transform.py
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${LOCAL_LAKEHOUSE:-/tmp/f1-local-lakehouse}"
mkdir -p "$WORK/warehouse"
APP="$1"; shift
case "$APP" in
  bronze_ingest.py)    ARGS=(--landing "file://$ROOT/data/raw") ;;
  silver_transform.py) ARGS=() ;;
  *) ARGS=() ;;
esac
"${SPARK_SUBMIT:-spark-submit}" --master 'local[2]' \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1,org.xerial:sqlite-jdbc:3.46.1.3 \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  --conf spark.sql.catalog.local=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.local.catalog-impl=org.apache.iceberg.jdbc.JdbcCatalog \
  --conf spark.sql.catalog.local.uri="jdbc:sqlite:$WORK/catalog.db" \
  --conf spark.sql.catalog.local.jdbc.schema-version=V1 \
  --conf spark.sql.catalog.local.warehouse="file://$WORK/warehouse" \
  --conf spark.ui.showConsoleProgress=false \
  "$ROOT/lakehouse/spark/$APP" --catalog local --warehouse "file://$WORK/warehouse" ${ARGS[@]+"${ARGS[@]}"} "$@"
