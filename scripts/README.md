# scripts/

Utility scripts for jadx-ai-mcp.

## benchmark.sh

Performance and regression benchmark for the Java REST plugin.

### Prerequisites

- `curl`, `xargs`, `python3` (all present in the container image)
- `JADX_MCP_AUTH_TOKEN` env var (if auth is enabled)

### Usage

```bash
# Local (against a running container)
export JADX_MCP_AUTH_TOKEN=change-me
./scripts/benchmark.sh [HOST] [PORT] [MODE]

# Default: baseline against 127.0.0.1:8650
./scripts/benchmark.sh

# Full suite
./scripts/benchmark.sh 127.0.0.1 8650 all

# Inside the container
docker exec -e JADX_MCP_AUTH_TOKEN=change-me jadx \
  /opt/jadx/scripts/benchmark.sh 127.0.0.1 8650 baseline
```

### Modes

| Mode | What it runs | Typical duration |
|---|---|---|
| `single` | One `/health` call | <1s |
| `baseline` | 5x class search + 5x method search + 1x status (sequential) | ~5s |
| `stress` | 80 concurrent × 60s class search; 80 concurrent × 60s code search | ~2 min |
| `rename` | 50 concurrent searches + rename storm (10/s) for 30s | ~30s |
| `all` | baseline + stress + rename | ~3 min |

### Output

- **stdout** — JSON result (machine-readable; diff between runs with `jq`)
- **stderr** — human-readable progress
- **`/tmp/benchmark-<timestamp>/`** — raw curl responses for forensics

### Regression check example

```bash
# Before change
./scripts/benchmark.sh 127.0.0.1 8650 baseline > before.json

# After change
./scripts/benchmark.sh 127.0.0.1 8650 baseline > after.json

# Compare p99 latency
jq '.baseline.p99' before.json after.json
```

---

## run-integration-tests.sh

Runs the full Java + Python integration test suite against a live container.
See `tests/` for details.

## fetch-nexus-jar.sh

Downloads the plugin JAR from a Nexus / Maven repository for air-gapped builds.
