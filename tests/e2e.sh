#!/usr/bin/env bash
# End-to-end test: follow the tutorial from a fresh clone of the repository, in order.
#
#   tests/e2e.sh /path/to/your/.env
#
# It builds an independent copy of the lakehouse in e2e_bronze, e2e_silver and e2e_gold, with
# its own streaming checkpoint, so your f1_* tables are not touched. It does not publish to
# Kafka; it replays the races already on the topic. Drop the e2e_* schemas afterwards.
ENV_FILE="$(cd "$(dirname "${1:?usage: tests/e2e.sh /path/to/.env}")" && pwd)/$(basename "$1")"
E2E="${E2E_DIR:-$(mktemp -d)/f1-e2e}"
PASS=(); FAIL=()
step() { local name="$1"; shift; echo; echo "=================== $name"; echo "\$ $*"
  if "$@"; then PASS+=("$name"); else FAIL+=("$name"); echo "!!! FAILED: $name"; fi; }

rm -rf "$E2E"
step "Step 1: clone" git clone -q https://github.com/adiDaBEzt/f1-lakehouse-watsonx-tutorial.git "$E2E"
cd "$E2E" || exit 1
step "Step 1: venv" uv venv -q -p 3.12 .venv
step "Step 1: install" uv pip install -q -p .venv -r requirements.txt
step "Step 1: env template" cp .env.example .env
# Fill .env with the real values, plus independent schemas and checkpoint for this test.
cp "$ENV_FILE" .env
cat >> .env <<'EOF'
BRONZE_SCHEMA=e2e_bronze
SILVER_SCHEMA=e2e_silver
GOLD_SCHEMA=e2e_gold
CHECKPOINT_PREFIX=checkpoints-e2e
EOF
L=".venv/bin/python -m lakehouse"
until $L sql "SELECT 1" >/dev/null 2>&1; do sleep 20; done

step "Step 2: engines" $L engines
step "Step 2: catalogs" $L sql "SHOW CATALOGS"
step "Step 4: upload" $L upload
step "Step 5: bronze" $L bronze
step "Step 6: silver" $L silver
step "Step 6: silver re-run" $L silver
step "Step 6: quarantine" $L sql 'SELECT source_table, reason, count(*) AS n FROM ${catalog}.${silver}.quarantine GROUP BY 1, 2'
step "Step 7: gold" $L gold
step "Step 7: 2025 check" $L sql 'SELECT points_rank, driver_name, constructors, points, wins FROM ${catalog}.${gold}.driver_season WHERE season = 2025 ORDER BY points_rank LIMIT 3'
step "Step 7: 1988 check" $L sql 'SELECT season, points_rank, driver_name, points, wins FROM ${catalog}.${gold}.driver_season WHERE season = 1988 AND points_rank <= 2 ORDER BY points_rank'
step "Step 8: producer list" .venv/bin/python -m streaming.producer --list
step "Step 9: register kafka" $L register kafka
step "Step 9: kafka query" $L sql lakehouse/sql/live/kafka_round_results.sql --max-rows 3
step "Step 10: refresh" $L refresh
step "Step 10: snapshots" $L sql lakehouse/sql/time_travel/01_snapshots.sql
SNAP=$(.venv/bin/python - <<'PY'
from lakehouse import config
from lakehouse.wxd import WatsonxData
w = WatsonxData(config.load()); s = w.s
_, rows = w.sql(f'SELECT snapshot_id FROM {s.catalog}.{s.silver}."results$snapshots" ORDER BY committed_at')
print(rows[-2][0])
PY
)
BA="$E2E/before_after.sql"
sed "s/<SNAPSHOT_ID>/$SNAP/" lakehouse/sql/time_travel/02_before_after.sql > "$BA"
step "Step 10: time travel" $L sql "$BA"
step "Step 10: files" $L files e2e_silver.results
step "Step 11: load postgres" .venv/bin/python postgres/load.py
step "Step 11: register postgres" $L register postgres
step "Step 11: fantasy table" $L sql lakehouse/sql/federation/01_fantasy_league_table.sql --max-rows 3
step "Step 11: three-way" $L sql lakehouse/sql/federation/02_three_way_live.sql --max-rows 5
step "Step 15: freshness" $L sql lakehouse/sql/live/freshness.sql
step "Step 15: live standings" $L sql lakehouse/sql/live/live_standings.sql --max-rows 4
step "Step 13: deploy agent" .venv/bin/python agent/deploy.py </dev/null
ask() { printf 'exit\n' | COLUMNS=150 .venv/bin/orchestrate chat ask -n f1_race_analyst "$1" 2>&1 | grep -v "EOF when reading" | sed -n '/f1_race_analyst ─/,/╰/p' | head -30; }
step "Step 14: ask fantasy" ask "Who leads our fantasy league in 2026? Captains score double."

echo; echo "=================== SUMMARY"
echo "PASSED (${#PASS[@]}):"; printf '  %s\n' "${PASS[@]}"
echo "FAILED (${#FAIL[@]}):"; printf '  %s\n' "${FAIL[@]}"
[ ${#FAIL[@]} -eq 0 ]
