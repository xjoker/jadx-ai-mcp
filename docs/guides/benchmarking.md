# Benchmarking

Use the benchmark runner to capture a current baseline before optimization and to compare after refactors.

## What It Measures

- Plugin HTTP API throughput, latency, busy rate, and error rate
- MCP tool-layer throughput, latency, busy rate, and error rate
- Cold-start, warm-cache, and degraded-pressure scenarios
- Lightweight pre/post state snapshots from:
  - `/health`
  - `/apk-info`
  - `/decompile-status`
  - `/status.json`

## Default Workflow

All benchmark execution is designed to happen through Docker.

```bash
benchmarks/run_in_container.sh --build --image jadx-ai-mcp:local-benchmark --label baseline-dev
```

Default assumptions:

- APKs are mounted from `temp/`
- `temp/target.apk` is auto-loaded by the all-in-one container
- Results are written to `temp/benchmark-results/`

## Compare With a Previous Run

Use the JSON output from an earlier run as the comparison baseline.

```bash
benchmarks/run_in_container.sh \
  --image jadx-ai-mcp:local-benchmark \
  --label after-optimization \
  --compare /results/20260311-120000_baseline-dev.json
```

If MCP auth is enabled, pass the token:

```bash
benchmarks/run_in_container.sh --mcp-auth-token your-token
```

For focused code-search tuning, use the smaller matrix in
`benchmarks/code_search_focus.json`:

```bash
benchmarks/run_in_container.sh \
  --image jadx-ai-mcp:local-benchmark \
  --config benchmarks/code_search_focus.json \
  --label code-search-focus
```

## Outputs

Each run generates:

- A raw JSON report with full metrics and state snapshots
- A JSON `compare` section when `--compare` is provided
- A Markdown summary table
- A Markdown comparison report when `--compare` is provided

Key fields include:

- `ok_rps`
- `latency_ms.p50/p95/p99`
- `busy_rate`
- `error_rate`
- per-case status-code counts
- pre/post plugin and MCP status snapshots
- comparison `verdict` (`pass` or `regression`) based on `ok_rps`, `p95`, `busy_rate`, and `error_rate`

Workload names:

- `metadata`: fast metadata-only lookups
- `decompile`: source/smali retrieval
- `code_search_only`: `search_in=code` only
- `xref_only`: xref endpoints only
- `search_xref`: mixed search + xref load
- `mixed`: representative AI request mix

## Stable Sample Mode

For before/after optimization work, prefer a fixed sample override so both runs
hit the same class and method targets.

```json
{
  "sample_discovery": {
    "sample_override": {
      "primary_class": "com.example.MainActivity",
      "secondary_class": "com.example.Helper",
      "primary_method": "onCreate",
      "primary_field": "INSTANCE",
      "search_term": "onCreate",
      "package_filter": "com.example",
      "class_source_hint": "MainActivity"
    }
  }
}
```

Only `primary_class` and `primary_method` are required. When no override is
provided, the runner falls back to auto-discovery and now prefers the APK main
activity when available before scanning the wider class list.

## Notes

- `cold_start` is measured against a freshly started benchmark container before the warmup scenarios begin.
- `warm_cache` and `degraded_pressure` intentionally reuse the same running instance to reflect realistic steady-state behavior.
- The benchmark runner auto-discovers a usable class/method pair from the loaded file, so it works with both repository fixtures and large real APKs like `temp/target.apk`.
- MCP `INSTANCE_BUSY` payloads are classified as `busy` even when the client transport reports a structured success envelope.
