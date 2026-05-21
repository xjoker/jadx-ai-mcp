# Changelog

All notable changes to jadx-ai-mcp are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).  
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

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
