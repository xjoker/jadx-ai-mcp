#!/usr/bin/env bash
# jadx-ai-mcp benchmark / regression script
#
# Usage:
#   ./scripts/benchmark.sh [HOST] [PORT] [MODE]
#
# Args (positional, all optional):
#   HOST   default: 127.0.0.1
#   PORT   default: 8650  (Java REST plugin)
#   MODE   single|baseline|stress|rename|all  default: baseline
#
# Auth token read from env: JADX_MCP_AUTH_TOKEN
#
# Output:
#   stdout  — machine-readable JSON result (pipe to jq, diff between runs, etc.)
#   stderr  — human-readable progress/summary
#
# Can run inside the container:
#   docker exec jadx /opt/jadx/scripts/benchmark.sh 127.0.0.1 8650 baseline
#
set -euo pipefail

# ──────────────────────────── config ────────────────────────────
HOST="${1:-127.0.0.1}"
PORT="${2:-8650}"
MODE="${3:-baseline}"
TOKEN="${JADX_MCP_AUTH_TOKEN:-}"

BASE_URL="http://${HOST}:${PORT}"
TIMESTAMP="$(date +%Y%m%dT%H%M%S)"
RAW_DIR="/tmp/benchmark-${TIMESTAMP}"
mkdir -p "${RAW_DIR}"

# ──────────────────────────── helpers ───────────────────────────
log() { echo "$*" >&2; }

auth_header() {
  if [[ -n "${TOKEN}" ]]; then
    printf '%s' "X-Auth-Token: ${TOKEN}"
  else
    printf '%s' "X-Unused: 1"
  fi
}

# json_field <file> <field> — extract a top-level JSON string/number field
json_field() {
  python3 -c "
import json, sys
try:
    d = json.load(open('$1'))
    print(d.get('$2', ''))
except Exception:
    print('')
"
}

# percentiles <file-of-floats>
percentiles() {
  python3 -c "
import sys, json, math
vals = []
for line in open('$1'):
    line = line.strip()
    if line:
        try:
            vals.append(float(line))
        except ValueError:
            pass
if not vals:
    print(json.dumps({'count':0,'p50':0,'p95':0,'p99':0,'max':0,'mean':0}))
    sys.exit(0)
vals.sort()
n = len(vals)
def p(pct):
    idx = int(math.ceil(pct / 100.0 * n)) - 1
    return round(vals[max(0, min(idx, n-1))], 3)
print(json.dumps({'count':n,'p50':p(50),'p95':p(95),'p99':p(99),'max':round(vals[-1],3),'mean':round(sum(vals)/n,3)}))
"
}

# http_histogram <file-of-http-codes>
http_histogram() {
  python3 -c "
import json
from collections import Counter
codes = [l.strip() for l in open('$1') if l.strip()]
c = Counter(codes)
print(json.dumps(dict(sorted(c.items()))))
"
}

# single_call <label> <url> — one curl, returns latency in seconds, saves response
single_call() {
  local label="$1"
  local url="$2"
  local out="${RAW_DIR}/${label}-$$.json"
  local header
  header="$(auth_header)"
  local latency
  latency=$(curl -s -o "${out}" -w "%{time_total}" \
    -H "${header}" \
    "${url}" 2>/dev/null || echo "error")
  echo "${latency}"
}

# ──────────────────────────── check prerequisite ────────────────
check_reachable() {
  log "→ checking ${BASE_URL}/health ..."
  local header
  header="$(auth_header)"
  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "${header}" "${BASE_URL}/health" 2>/dev/null || echo "000")
  if [[ "${http_code}" != "200" ]]; then
    log "ERROR: /health returned ${http_code}. Is the server running? Is TOKEN set?"
    exit 1
  fi
  log "  server healthy (HTTP ${http_code})"
}

# ──────────────────────────── get sample class names ────────────
get_sample_classes() {
  local header
  header="$(auth_header)"
  local out="${RAW_DIR}/all-classes.json"
  curl -s -H "${header}" "${BASE_URL}/all-classes" -o "${out}" 2>/dev/null || true
  python3 -c "
import json, sys
try:
    data = json.load(open('${out}'))
    classes = data if isinstance(data, list) else data.get('classes', data.get('result', []))
    names = [c.get('name','') if isinstance(c, dict) else str(c) for c in classes[:30]]
    print('\n'.join(n for n in names if n))
except Exception as e:
    print('', file=sys.stderr)
" 2>/dev/null
}

# ──────────────────────────── scenarios ─────────────────────────

run_baseline() {
  log ""
  log "═══════════════ BASELINE ═══════════════"
  local header
  header="$(auth_header)"
  local latencies_file="${RAW_DIR}/baseline-latencies.txt"
  > "${latencies_file}"

  # 5x class search
  log "→ class search (5 sequential calls) ..."
  for i in 1 2 3 4 5; do
    local lat
    lat=$(single_call "class-search-${i}" \
      "${BASE_URL}/search-classes-by-keyword?keyword=Activity&page=1&pageSize=10")
    echo "${lat}" >> "${latencies_file}"
    log "  call ${i}: ${lat}s"
  done

  # 5x method search
  log "→ method search (5 sequential calls) ..."
  for i in 1 2 3 4 5; do
    local lat
    lat=$(single_call "method-search-${i}" \
      "${BASE_URL}/search-method-by-name?name=onCreate&page=1&pageSize=10")
    echo "${lat}" >> "${latencies_file}"
    log "  call ${i}: ${lat}s"
  done

  # 1x decompile status
  log "→ decompile status ..."
  local lat
  lat=$(single_call "decompile-status" "${BASE_URL}/decompile-status")
  echo "${lat}" >> "${latencies_file}"
  log "  status: ${lat}s"

  local stats
  stats=$(percentiles "${latencies_file}")
  log "  baseline latency stats: ${stats}"
  echo "${stats}"
}

run_stress() {
  log ""
  log "═══════════════ STRESS ══════════════════"
  local header
  header="$(auth_header)"
  local duration=60
  local concurrency=80

  log "→ ${concurrency} concurrent class search requests for ${duration}s ..."
  local cs_codes="${RAW_DIR}/stress-cs-codes.txt"
  local cs_lats="${RAW_DIR}/stress-cs-lats.txt"
  > "${cs_codes}"; > "${cs_lats}"

  # Generate request list and run with xargs -P
  local end_time=$(( $(date +%s) + duration ))
  seq 1 99999 | xargs -P "${concurrency}" -I{} bash -c "
    if [ \$(date +%s) -lt ${end_time} ]; then
      result=\$(curl -s -o /dev/null -w '%{http_code} %{time_total}' \
        -H '${header}' \
        '${BASE_URL}/search-classes-by-keyword?keyword=Activity&page=1&pageSize=5' 2>/dev/null || echo '000 0')
      code=\$(echo \"\$result\" | awk '{print \$1}')
      lat=\$(echo \"\$result\" | awk '{print \$2}')
      echo \"\$code\" >> '${cs_codes}'
      echo \"\$lat\" >> '${cs_lats}'
    fi
  " 2>/dev/null || true

  local cs_hist cs_stats
  cs_hist=$(http_histogram "${cs_codes}")
  cs_stats=$(percentiles "${cs_lats}")

  log "  class search HTTP codes: ${cs_hist}"
  log "  class search latency (s): ${cs_stats}"
  total=$(wc -l < "${cs_codes}" | tr -d ' ')
  ok=$(grep -c '^200$' "${cs_codes}" 2>/dev/null || echo 0)
  throughput=$(python3 -c "print(round(${ok} / ${duration}, 1))")
  log "  throughput: ${throughput} req/s (${ok}/${total} 200s over ${duration}s)"

  log "→ ${concurrency} concurrent code search for ${duration}s ..."
  local code_codes="${RAW_DIR}/stress-code-codes.txt"
  local code_lats="${RAW_DIR}/stress-code-lats.txt"
  > "${code_codes}"; > "${code_lats}"

  end_time=$(( $(date +%s) + duration ))
  seq 1 99999 | xargs -P "${concurrency}" -I{} bash -c "
    if [ \$(date +%s) -lt ${end_time} ]; then
      result=\$(curl -s -o /dev/null -w '%{http_code} %{time_total}' \
        -H '${header}' \
        '${BASE_URL}/search-classes-by-keyword?keyword=onCreate&search_in=code&page=1&pageSize=5' 2>/dev/null || echo '000 0')
      code=\$(echo \"\$result\" | awk '{print \$1}')
      lat=\$(echo \"\$result\" | awk '{print \$2}')
      echo \"\$code\" >> '${code_codes}'
      echo \"\$lat\" >> '${code_lats}'
    fi
  " 2>/dev/null || true

  local code_hist code_stats
  code_hist=$(http_histogram "${code_codes}")
  code_stats=$(percentiles "${code_lats}")
  log "  code search HTTP codes: ${code_hist}"
  log "  code search latency (s): ${code_stats}"

  python3 -c "
import json
cs_hist=${cs_hist}
cs_stats=${cs_stats}
code_hist=${code_hist}
code_stats=${code_stats}
print(json.dumps({
    'class_search': {'http_codes': cs_hist, 'latency_seconds': cs_stats, 'throughput_rps': ${throughput}},
    'code_search':  {'http_codes': code_hist, 'latency_seconds': code_stats},
}))
"
}

run_rename() {
  log ""
  log "═══════════════ RENAME STORM ════════════"
  local header
  header="$(auth_header)"
  local duration=30
  local search_concurrency=50
  local rename_rate=10  # renames per second

  # Get sample classes for rename targets
  log "→ fetching top-30 class names for rename targets ..."
  local class_names
  mapfile -t class_names < <(get_sample_classes)
  if [[ ${#class_names[@]} -eq 0 ]]; then
    log "  WARNING: could not retrieve class names; rename storm skipped"
    echo '{"rename_storm": "skipped: no classes available"}'
    return
  fi
  log "  got ${#class_names[@]} class names"

  local search_codes="${RAW_DIR}/rename-search-codes.txt"
  local rename_5xx="${RAW_DIR}/rename-5xx.txt"
  > "${search_codes}"; > "${rename_5xx}"

  log "→ ${search_concurrency} concurrent searches + rename storm for ${duration}s ..."
  local end_time=$(( $(date +%s) + duration ))

  # Background search workers
  seq 1 99999 | xargs -P "${search_concurrency}" -I{} bash -c "
    if [ \$(date +%s) -lt ${end_time} ]; then
      code=\$(curl -s -o /dev/null -w '%{http_code}' \
        -H '${header}' \
        '${BASE_URL}/search-classes-by-keyword?keyword=Activity&page=1&pageSize=5' 2>/dev/null || echo '000')
      echo \"\$code\" >> '${search_codes}'
    fi
  " 2>/dev/null &
  local search_pid=$!

  # Rename storm — sequential at ~rename_rate/sec, in background
  (
    idx=0
    while [[ $(date +%s) -lt ${end_time} ]]; do
      class="${class_names[$((idx % ${#class_names[@]}))]}"
      newname="Bench_${idx}_$(date +%s%N | tail -c 5)"
      http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST \
        -H "${header}" \
        -H "Content-Type: application/json" \
        -d "{\"class_full_name\":\"${class}\",\"new_name\":\"${newname}\"}" \
        "${BASE_URL}/rename" 2>/dev/null || echo "000")
      if [[ "${http_code}" == 5* ]]; then
        echo "${http_code}" >> "${rename_5xx}"
        log "  WARN: rename returned ${http_code} for class ${class}"
      fi
      idx=$(( idx + 1 ))
      sleep "$(python3 -c "print(1/${rename_rate})")"
    done
  ) &
  local rename_pid=$!

  wait "${search_pid}" 2>/dev/null || true
  wait "${rename_pid}" 2>/dev/null || true

  local total ok five_xx_count
  total=$(wc -l < "${search_codes}" | tr -d ' ')
  ok=$(grep -c '^200$' "${search_codes}" 2>/dev/null || echo 0)
  five_xx_count=$(wc -l < "${rename_5xx}" | tr -d ' ')
  local ratio
  ratio=$(python3 -c "print(round(${ok} / max(${total},1) * 100, 1))")
  log "  search 200-ratio: ${ratio}% (${ok}/${total})"
  log "  rename 5xx incidents: ${five_xx_count}"

  python3 -c "
import json
print(json.dumps({
    'rename_storm': {
        'duration_seconds': ${duration},
        'search_200_ratio_pct': ${ratio},
        'search_total': ${total},
        'search_ok': ${ok},
        'rename_5xx_incidents': ${five_xx_count},
    }
}))
"
}

# ──────────────────────────── single spot-check ─────────────────
run_single() {
  log ""
  log "═══════════════ SINGLE CALL ═════════════"
  local header
  header="$(auth_header)"
  local out="${RAW_DIR}/single-health.json"
  local lat
  lat=$(curl -s -o "${out}" -w "%{time_total}" \
    -H "${header}" "${BASE_URL}/health" 2>/dev/null || echo "error")
  local status
  status=$(json_field "${out}" "status" 2>/dev/null || echo "unknown")
  log "  /health: ${lat}s  status=${status}"
  python3 -c "import json; print(json.dumps({'health_latency_seconds': ${lat}, 'status': '${status}'}))"
}

# ──────────────────────────── main ──────────────────────────────
log "jadx-ai-mcp benchmark"
log "  target : ${BASE_URL}"
log "  mode   : ${MODE}"
log "  raw dir: ${RAW_DIR}"
log "  auth   : $([ -n "${TOKEN}" ] && echo enabled || echo DISABLED)"

check_reachable

case "${MODE}" in
  single)
    result=$(run_single)
    ;;
  baseline)
    baseline=$(run_baseline)
    result=$(python3 -c "
import json
print(json.dumps({'mode': 'baseline', 'baseline': ${baseline}}))
")
    ;;
  stress)
    stress=$(run_stress)
    result=$(python3 -c "
import json
print(json.dumps({'mode': 'stress', 'stress': ${stress}}))
")
    ;;
  rename)
    rename=$(run_rename)
    result=$(python3 -c "
import json
print(json.dumps({'mode': 'rename', 'rename': ${rename}}))
")
    ;;
  all)
    baseline=$(run_baseline)
    stress=$(run_stress)
    rename=$(run_rename)
    result=$(python3 -c "
import json
print(json.dumps({
    'mode': 'all',
    'baseline': ${baseline},
    'stress': ${stress},
    'rename': ${rename},
}))
")
    ;;
  *)
    log "ERROR: unknown mode '${MODE}'. Valid: single|baseline|stress|rename|all"
    exit 1
    ;;
esac

log ""
log "raw results saved to: ${RAW_DIR}"

# Emit final machine-readable JSON to stdout
python3 -c "
import json, datetime
data = ${result}
data['meta'] = {
    'host': '${HOST}',
    'port': ${PORT},
    'timestamp': '${TIMESTAMP}',
}
print(json.dumps(data, indent=2))
"
