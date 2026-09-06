#!/usr/bin/env bash
# Smoke test the project venv end-to-end.
set -e
cd "$(dirname "$0")"
VENV=.venv
PY=$VENV/bin/python

echo "[1/5] import all modules"
$PY -c "import app.main, app.cli, app.scheduler, app.mcp_client, app.pipeline.extract, app.pipeline.trends, app.pipeline.ingest; print('  import ok')"

echo "[2/5] cli: generate payments-pod --no-mcp"
$PY -m app.cli generate --pod payments-pod --date 2026-09-06 --no-mcp | tee /tmp/scrum-cli.out
echo

echo "[3/5] inspect rendered JSON + HTML"
ROOT="$(cd .. && pwd)"
RAW="$ROOT/.workdir/pods/payments-pod/raw/2026-09-06.json"
HTML="$ROOT/.workdir/pods/payments-pod/dsu/2026-09-06.html"
[ -f "$RAW" ] && [ -f "$HTML" ] || { echo "  artifacts missing at $RAW / $HTML"; exit 1; }
$PY - <<PY
import json
j = json.load(open("$RAW"))
print(f"  health_score={j['health_score']}  risk={j['risk_level']}  blockers={j['open_blockers']}")
print(f"  delivery={j['delivery']}")
print(f"  team participants={j['team']['participants']}  load={j['team']['load_by_person']}")
print(f"  sections in html:", sum(
    kw in open("$HTML").read()
    for kw in ["交付进展","流动效率","团队信号","趋势对比","质量与风险","阻塞与依赖"]
), "/ 6")
PY

echo "[4/5] boot uvicorn and curl endpoints"
($PY -m uvicorn app.main:app --port 8134 > /tmp/scrum-api.log 2>&1 &)
PID=$!
trap "(kill $PID 2>/dev/null || true) >/dev/null 2>&1" EXIT
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sf http://127.0.0.1:8134/api/pods >/dev/null 2>&1; then break; fi
  sleep 1
done
echo "  /api/pods -> $(curl -s http://127.0.0.1:8134/api/pods | $PY -c "import sys,json;print(json.load(sys.stdin))")"
echo "  /api/dsu/payments-pod -> first 120 bytes: $(curl -s http://127.0.0.1:8134/api/dsu/payments-pod | head -c 120)"
echo "  /dsu/payments-pod/2026-09-06 -> http $(curl -s -o /dev/null -w "%{http_code}, %{size_download} bytes" http://127.0.0.1:8134/dsu/payments-pod/2026-09-06)"

echo "[5/5] scheduler jobs"
$PY -c "from app.scheduler import build; print('  jobs:', [(j.id, str(j.trigger).split(', ')[1]) for j in build().get_jobs()])"

echo "ALL_OK"