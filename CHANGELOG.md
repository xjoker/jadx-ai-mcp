# Changelog

All notable changes to jadx-ai-mcp are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).  
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [6.6.0] - 2026-05-26 *(final release — project archived)*

### Added

- **Three-layer test suite covering all 39 MCP tools** — establishes a quantified baseline
  for the future headless rewrite (`jadx-mcp-core`):
  - **Layer 1 — Smoke tests** (`test_smoke_xhs.py`): 16 happy-path tests against the live XHS
    APK instance; full suite completes in <5 s and validates every endpoint is reachable after
    deploy. Fixtures dynamically resolve the first class name to avoid hardcoding.
  - **Layer 2 — Unit tests** (10 new files, 195 tests): pure mock coverage for every previously
    untested tool module — `class_tools`, `xrefs_tools`, `resource_tools`, `string_literal_tools`,
    `task_tools`, `analysis_surface_tools`, `transfer_tools`, `diagnostics_tools`,
    `file_management_tools`, `refactor_tools` (extended), `search_tools` (async). Total unit test
    count raised from 119 to **314 passing**.
  - **Layer 3 — Stress + GUI baseline** (`test_stress_baseline.py`): concurrent class-source
    (10 parallel), metadata vs code search P95 comparison, decompile-status stability (20 samples),
    batch operations (10 / 20 classes). Captured baseline written to
    `tests/integration/fixtures/baseline_gui_results.json` — key values: class_source P50 = 26 ms,
    metadata search P50 = 52 ms, memory = 67 %, trigram coverage = 57 %.
  - **Headless contract tests** (`test_headless_contract.py`): 8 skip-marked contract cases
    defining GUI ↔ headless equivalence constraints (source diff < 5 %, xrefs set-equal,
    performance within 2× GUI baseline). Remove `@pytest.mark.skip` when `jadx-mcp-core` is ready.

## [6.5.6] - 2026-05-26

### Fixed

- **`get_decompile_status` no longer crashes the plugin during APK load** — iterating the live class
  list while JADX was still loading a large APK triggered `ConcurrentModificationException`, which
  cascaded into `NoClassDefFoundError` for all subsequent plugin class loads, breaking the entire
  JADX plugin until restart. Fix: take a snapshot (`new ArrayList<>()`) before iterating, and
  return HTTP 202 `{"status":"loading"}` on any exception during the counting phase instead of
  propagating a fatal error.
- **Friendly "loading" status instead of 500 during APK initialization** — Python `get_decompile_status`
  now surfaces `{"status":"loading","retry_after_seconds":3,"suggestion":"..."}` when JADX returns
  HTTP 202, so AI clients know to retry instead of seeing an opaque INTERNAL_ERROR.

## [6.5.5] - 2026-05-26

### Fixed

- **Warmup Phase 1 no longer blocks searches** — `WarmupManager.runPhase1()` previously acquired
  a per-class `JadxSearchLock` write lock serially, creating a continuous write-lock blackout
  for the entire warmup duration (hours on large APKs). Replaced with parallel 8-worker
  `CountDownLatch` pool (`JADX_MCP_WARMUP_DECOMPILE_WORKERS` env, default 8). JADX's
  `cls.getCode()` is thread-safe internally; the global write lock is not needed.
- **Java ticket TTL raised to 600 s** — `CodeSearchCoordinator.TICKET_TTL_SECONDS` was 120 s,
  too short for warmup-phase searches that start before cache is warm. Raised to 600 s to
  match the Python-side async task window.

## [6.5.4] - 2026-05-26

### Added

- **`submit_security_scan` / `submit_callgraph` / `get_task_result` MCP tools** — async
  submit-then-poll wrappers for long-running Python-side operations. Both submit tools
  return a ticket in <5 ms; poll `get_task_result(ticket)` until `status="done"`.
  Backed by the generic `async_tasks` module (Python `asyncio.create_task`, 300 s TTL).

### Fixed

- **`run_security_scan` code-search timeout** — code-pattern searches inside
  `_run_security_scan` were hitting the 30 s metadata timeout instead of the 120 s
  `TIMEOUT_CODE_READ` budget, causing silent skips on loaded APKs. Fix: pass
  `timeout=TIMEOUT_CODE_READ` when `search_in == "code"`.

## [6.5.3] - 2026-05-26

### Added

- **`submit_code_search` / `get_code_search_result` MCP tools** — submit-then-poll async code
  search that eliminates MCP client timeouts entirely. `submit_code_search` returns a ticket in
  <100 ms; `get_code_search_result(ticket)` polls until `status="done"`. Cache hits return
  `status="done"` immediately. Follower deduplication: identical concurrent submits share one
  background task. Java side: `POST /submit-code-search` + `GET /code-search-status` endpoints.
- `CodeSearchCoordinator.registerTicket(future)` and `pollByTicket(ticket)` — UUID-based async
  ticket registry with `TICKET_TTL_SECONDS=120` TTL; handles RUNNING / DONE / TIMED_OUT /
  CANCELLED / ERROR / NOT_FOUND states.

## [6.5.2] - 2026-05-26

### Fixed

- **`search_in='code'` always timing out** — `search-classes-by-keyword` was misclassified in
  `_METADATA_ENDPOINTS` (30 s timeout). Code searches on large APKs take 38–40 s; they exceeded
  the 30 s client timeout before the Java server could reply. Fix: when `search_in` contains
  `'code'`, the Python layer now passes `timeout=TIMEOUT_CODE_READ` (120 s) to the HTTP call,
  overriding the metadata-tier default.

## [6.5.1] - 2026-05-26

### Fixed

- **Code search timeout on hex/UUID patterns** — `CodeContentIndex.candidatesForTerm()` previously
  returned `null` when all trigrams existed in the index but their intersection was empty, causing
  `SearchRoutes` to fall back to a full scan of all 237k classes (including ~113k non-indexed large
  classes that require disk I/O per class). Now returns an empty `BitSet` to signal "definitively
  absent from indexed classes", allowing the fallback to skip already-indexed classes and only scan
  the non-indexed large classes. Worst-case scan reduced by ~50% for patterns like AES keys, hashes,
  and UUIDs.
- Added `CodeContentIndex.isIndexed(JavaClass)` public method for O(1) indexed-class check.
- `search_info` response now includes `trigram_definitively_empty` field so callers can observe
  which optimization path was taken.

### Changed

- MCP decision guide updated: `get_index_stats()` trigram coverage replaces `cached_percentage`
  as the primary metric for code-search viability. Added explicit prohibition list for pattern
  types that always cause full scans (hex strings ≥8 chars, UUID, Base64, long URL paths).

### Added

- **`warm_cache(skip_libraries)` MCP tool** — triggers full background decompilation of all classes
  so `search_in='code'` works without waiting for the cache to warm organically.
  `skip_libraries=True` (default) filters out known third-party SDK prefixes
  (`android.*`, `kotlin.*`, `okhttp3.*`, etc.) to save time and memory.
  Returns immediately; poll `get_warmup_status()` or `get_decompile_status()`
  to track `cached_percentage` progress.
- **`get_warmup_status()` MCP tool** — polls the background warmup started by
  `warm_cache()`. Returns `{phase, running, total, processed, failed, percentage, elapsed_seconds}`.
- Java `WarmupManager` utility class with two-phase warmup: serial decompile under
  `JadxSearchLock` (phase 1) + parallel trigram-index fill (phase 2); supports
  cancel, memory-pressure pause, and per-class timeout.
- REST endpoints `POST /cache/warmup`, `GET /cache/warmup-status`,
  `POST /cache/warmup/cancel` on the JADX plugin server.

- **`analyze_apk(path, strategy)` MCP tool** — high-level APK loading with
  smart instance routing. `strategy="auto"` (default) inspects all connected
  instances and routes to a free one; returns `status=ambiguous` when the
  only instance already has a file loaded (prompts the AI to choose
  `replace`, `new_instance`, or `append`); returns `status=all_busy` with
  guidance when every instance is occupied. Explicit strategies `replace`,
  `new_instance`, and `append` are also supported.
  Return shape: `{status, instance, path, ready: false, poll_with, next_steps}`.
- **`list_loaded_files()` MCP tool** — aggregated view of what each instance
  is currently analyzing. Calls `/apk-info` and `/decompile-status` on every
  accessible instance and returns
  `{instances: [{name, loaded_file, decompile_progress, available}], free_count}`.
- New file `jadx-mcp-server/src/server/tools/workflow_tools.py` housing both
  tools; wired into `tools/__init__.py` and `jadx_mcp_server.py`.
- 22 new Python unit tests in `tests/test_workflow_tools.py` covering the
  `auto` decision tree (no instances, free, ambiguous, multi-instance pick,
  all-busy), all explicit strategies, error propagation, and `list_loaded_files`
  aggregation and filtering.
- `docs/deployment.md` — new "Multi-APK workflows" section with three
  example conversations: open one APK, compare two APKs across instances,
  and analyze with JAR dependencies.

---

## [6.3.0] - 2026-05-21

### Performance

- **Split-phase locking** — coarse write lock during decompile, fine-grained read lock after; reduces search stalls under load
- **Snapshot weak cache** — `WeakReference`-backed snapshot layer; GC-friendly for large APKs
- **busy_tracker lane rebalance** — worker lanes rebalanced based on queue depth; avoids hot-lane starvation
- **findClass dual-map** — secondary index keyed by simple name for O(1) short-name lookups
- **Name indices** — separate class-name and method-name sorted indices; faster prefix/infix search
- **Response serialization threshold** (`JADX_MCP_INLINE_RESPONSE_MAX_BYTES`, default 32 768) — large pages stream via transfer token instead of inline JSON; prevents MCP message size blowouts
- **Tool description trim** — all 39 tool descriptions shortened by 44 %; reduces token overhead on every call
- **Predecompile warmup** (`JADX_MCP_WARMUP_TOP_K`, default 100) — top-K classes decompiled in background at startup; search-then-decompile round-trips eliminated for common classes

### Added

- **Trigram inverted index for code-search** (`JADX_MCP_CODE_INDEX_ENABLED`, `JADX_MCP_CODE_INDEX_MAX_TRIGRAMS`, `JADX_MCP_CODE_INDEX_MAX_CLASS_SIZE_BYTES`) — sub-second `search_in=code` after index warm-up; 200 000 trigram cap prevents OOM
- **Streaming response** for large paginated pages — first chunk delivered before full serialization completes
- CI: `respx` added to Python test dependencies; 51 new tests; 119/119 passing

---

## [6.2.0] - 2026-05-21

### Added

- **`load_file` / `list_available_files` MCP tools** — file system access gated by `FilePathSandbox`; requires `JADX_FILE_ROOT` env var (auto-enabled if `/apks` mount present)
- **`/package-tree` endpoint** — hierarchical package/class tree for navigation
- **`rename_variable` MCP tool** — ported from upstream jadx-ai project
- **`method_signature` overload support** — disambiguates overloaded methods by parameter types
- 14 advanced analysis/security/scaling tools added in the v6.1.7-dev → v6.2.0 cycle (Frida hook generation, annotation inspection, analysis planner, call-chain analysis, security scanner, multi-instance routing)

### Fixed

- **503 stability** — scoped rename cache invalidation (invalidates only affected class, not entire cache); prevents cascading 503s on busy rename
- **Async follower decompile** — follower instances decompile asynchronously; leader no longer blocks on follower latency
- **OOM circuit breaker** — heap threshold check before decompile; returns 503 instead of crashing JVM
- **Bounded Jetty QTP** — `JADX_MCP_MAX_THREADS` (default 64) and `JADX_MCP_QUEUE_SIZE` (default 64) cap thread pool; prevents unbounded memory growth under burst traffic
- Auth: integration tests no longer fail with 401 (test suite auth flag corrected)
- `_default_tokens` `UnboundLocalError` when no `JADX_MCP_AUTH_TOKEN` configured
- `batch-method-by-name` response parsing; rename endpoint GET returns correct 200 status
- All API responses include `raw_name` fields for Frida/Xposed script compatibility

### Changed

- All Chinese comments and docstrings translated to English across Java and Python source
- Migrated from `JadxWrapper` global context to `JadxGuiContext` for correct plugin lifecycle

### Tests

- 53/53 JUnit tests passing at release

---

## [6.1.6] - 2026-03-19

### Added

- Multi-instance fuzzy routing — instance selected by keyword match on loaded file name
- `auth_failed` explicit status in `/status` response (distinct from generic connectivity error)

### Fixed

- Scoped cache invalidation on rename
- Batch chunk `param` validation
- 401 detection in health check; `auth_failed` oscillation resolved
- Removed cross-instance fallback (each instance loads a different app; fallback caused wrong-app results)

---

## [6.1.5] - 2026-03-18

### Fixed

- Rebuilt docs cross-references after restructure; fixed tool name mismatches in skill files

---

## [6.1.4] - 2026-03-02

### Fixed

- Cross-classloader `ClassCastException` in plugin route handlers
- MCP error response shape for malformed requests
- Docs restructured into `docs/` hierarchy

---

## [6.1.3] - 2026-02-08

### Fixed

- Version bump bookkeeping; CI tag-sync correction

---

## [6.1.2] - 2026-02-06

### Security

- Docker container security hardening (non-root user, dropped capabilities)

---

## [6.1.1] - 2026-02-05

### Fixed

- All-in-One container could not connect to the internal JADX instance at startup
- `supervisord` start ordering race (JADX GUI must be ready before MCP server starts)
- Default instance auto-registration in single-container mode

### Changed

- Added port reference table to README; three deployment scenario guides

---

## [6.1.0] - 2026-02-05

### Fixed

- `JADX_MCP_BIND_ADDRESS` environment variable ignored in Docker (was missing from `supervisord.conf`)
- Bind address now hardcoded to `0.0.0.0` in wrapper script as fallback

---

## [6.0.x] - 2026-01-12 – 2026-01-19

Incremental patch series (6.0.1 – 6.0.54) covering CI pipeline, Docker base image build automation, and Nexus artifact deployment. No user-facing feature changes.

---

## [6.0.0] - 2025-12-30

Architectural overhaul: Java plugin embedded HTTP server replaces Python-only server; Python layer becomes a thin MCP-to-REST proxy. Introduced `PluginServer` (Jetty), authentication middleware, multi-instance model.

---

<!-- Link references -->
[Unreleased]: https://github.com/xjoker/jadx-ai-mcp/compare/v6.3.0...HEAD
[6.3.0]: https://github.com/xjoker/jadx-ai-mcp/compare/v6.2.0...v6.3.0
[6.2.0]: https://github.com/xjoker/jadx-ai-mcp/compare/v6.1.6...v6.2.0
[6.1.6]: https://github.com/xjoker/jadx-ai-mcp/compare/v6.1.5...v6.1.6
[6.1.5]: https://github.com/xjoker/jadx-ai-mcp/compare/v6.1.4...v6.1.5
[6.1.4]: https://github.com/xjoker/jadx-ai-mcp/compare/v6.1.3...v6.1.4
[6.1.3]: https://github.com/xjoker/jadx-ai-mcp/compare/v6.1.2...v6.1.3
[6.1.2]: https://github.com/xjoker/jadx-ai-mcp/compare/v6.1.1...v6.1.2
[6.1.1]: https://github.com/xjoker/jadx-ai-mcp/compare/v6.1.0...v6.1.1
[6.1.0]: https://github.com/xjoker/jadx-ai-mcp/compare/v6.0.54...v6.1.0
[6.0.0]: https://github.com/xjoker/jadx-ai-mcp/releases/tag/v6.0.0
