# Changelog

**English** | [简体中文](CHANGELOG.zh-cn.md)

---

All notable changes to JADX-AI-MCP are documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) and [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

> 🔱 This changelog covers changes since forking from [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp).

---

## [6.1.6] - 2026-03-19

### 🐛 Bug Fixes

**Instance Management**
- Fixed: `register_instance_tools(mcp)` was imported but never called — all 7 instance management tools (`list_jadx_instances`, `add_jadx_instance`, etc.) were unavailable at runtime. This was the root cause of AI mis-routing instance queries to `get_file_info`.
- Removed cross-instance fallback: each JADX instance loads a different APK/JAR, so silently routing to another instance returns data from the wrong app. Now reports a clear error instead.
- Fixed `auth_failed` status oscillation: instances with 401 errors no longer flip between `auth_failed` and `connected` every health check cycle.
- Fixed: connected instances whose token is revoked now correctly transition to `auth_failed` (previously stayed `connected` because `/health` doesn't require auth).

**Concurrency & Caching**
- `handleClassSource` and `handleBatchClassSource` now acquire write lock before calling `cls.getCode()` — JADX internal state is not thread-safe for concurrent decompilation.
- All rename operations (`rename_class/method/field/package`) now call `ClassCacheManager.invalidateCode()` to prevent stale decompiled code from being returned after rename.
- `JadxSearchLock.tryAcquire()`: tracking state (`holdingThread`, `lockAcquireTime`) is only reset after successfully acquiring the lock, not before — prevents permanent tracking loss.
- Rename operations now only invalidate response cache for the affected instance, not all instances.
- Batch `handleBatchClassSource`: added `else` branch to ensure `found` field is always present in response (prevents client NPE).
- `handleBatchClassSource`: `chunk` parameter now wrapped in `try/catch NumberFormatException` (matching all other chunk parse sites).
- `ResponseCache.get()`: changed `del` to `pop(key, None)` for TTL expiry to avoid potential `KeyError` in concurrent asyncio scenarios.

**Instance Connectivity**
- Startup race condition eliminated: health monitor no longer waits 2 seconds before first check. MCP tools called immediately after startup now work.
- On-demand probe: when a pending/disconnected instance is accessed, a 3-second quick probe attempts to connect before returning an error. If JADX is reachable, the instance is promoted to `connected` instantly.
- `get_from_jadx`: `ConnectError` and `ConnectTimeout` now immediately mark the instance as `disconnected` (previously had to wait up to 30s for health monitor).
- Health monitor: pending instance health stats no longer double-count as `unhealthy_count`.
- APK switch detection: health monitor now checks both `apk_package` and `version_name` for changes, and invalidates response cache when either changes.

### 🚀 Improvements

**Fuzzy Instance Routing** (new)
- `instance_id` parameter now supports fuzzy matching across: instance name, APK package name (`com.xingin.xhs`), JADX instance name (`xhs-v835`), app display name, file name, and version.
- Matching priority: exact name → exact package → exact JADX name → exact app name → partial matches → file name → version.
- Example: `get_class_source(class_name="...", instance_id="xhs")` automatically routes to the instance loading XHS.

**Auth Error Clarity** (new)
- New `auth_failed` instance status (distinct from generic `error`) with actionable error messages: "Check jadx_token in config or --auth-token CLI flag."
- On-demand probe and health monitor both distinguish 401 from connectivity issues.
- Status page: `auth_failed` instances show red badge with warning banner.

**APK Display Name** (new)
- `/apk-info` endpoint now extracts `app_name` from `<application android:label="...">` in AndroidManifest.xml.
- If the label is a `@string/` resource reference, returned as `app_name_ref`.
- Used in fuzzy instance matching to route by app display name.

**Tool Description Improvements**
- `list_jadx_instances`: added "USE THIS TOOL WHEN" guidance and fuzzy match tips.
- `get_file_info`: clarified it requires a connected instance and is not for listing instances.
- `get_decompile_status`: clarified it returns runtime metrics, not file metadata.
- `search_classes_by_keyword`: marked as "PRIMARY search tool" with speed guide per `search_in` value.
- `search_method_by_name`: added "PREFER search_classes_by_keyword instead" warning.
- `batch_get_class_source`: added "for single class use get_class_source" guidance.

### ⚡ Performance

- **ReadWriteLock**: JADX operations now use `ReentrantReadWriteLock` — multiple concurrent metadata reads (class listing, method listing) no longer block each other. Only decompilation (`getCode`, `getSmali`) requires exclusive write lock.
- **Decompiled code cache**: `ClassCacheManager.codeCache` (LRU, 200 entries, 10-min TTL) caches decompiled Java source. Subsequent requests for the same class skip decompilation.
- **MCP response cache**: Python-side `ResponseCache` (LRU, 100 entries, 60s TTL) caches deterministic endpoint responses (`class-info`, `methods-of-class`, `fields-of-class`, etc.).
- **Parallel health checks**: `asyncio.gather()` checks all instances concurrently instead of serially.
- **Strings cache**: `ResourceCacheManager.parsedStringsCache` (ConcurrentHashMap) caches parsed `strings.xml` to avoid re-parsing.
- **Shared HTTP client**: `InstanceRegistry` uses a shared `httpx.AsyncClient` with connection pooling for health checks.

### 📦 Changed Files
- `jadx-mcp-server/jadx_mcp_server.py` — Added `register_instance_tools(mcp)` call
- `jadx-mcp-server/src/server/config.py` — On-demand probe, fuzzy matching, scoped cache invalidation, instant disconnect marking, 401 detection, no cross-instance fallback
- `jadx-mcp-server/src/server/health_monitor.py` — No startup delay, auth_failed handling, APK change detection, parallel checks, pending count fix
- `jadx-mcp-server/src/server/instance_registry.py` — `find_instance_by_apk()`, `update_instance_status(error_message=)`, `auth_failed` status
- `jadx-mcp-server/src/server/response_cache.py` — New LRU response cache module, TTL expiry fix
- `jadx-mcp-server/src/server/status_page.py` — `auth_failed` badge and warning
- `jadx-mcp-server/src/server/tools/class_tools.py` — Tool description improvements
- `jadx-mcp-server/src/server/tools/search_tools.py` — Tool description improvements
- `jadx-mcp-server/src/server/tools/instance_tools.py` — Tool description improvements, fuzzy match guidance
- `jadx-mcp-server/src/server/tools/resource_tools.py` — `get_file_info` description clarification
- `src/main/java/com/zin/jadxaimcp/server/routes/ClassRoutes.java` — Write lock on decompilation, batch chunk validation, batch found field
- `src/main/java/com/zin/jadxaimcp/server/routes/RefactoringRoutes.java` — Cache invalidation after rename
- `src/main/java/com/zin/jadxaimcp/server/routes/ApkInfoRoutes.java` — `app_name` extraction from AndroidManifest
- `src/main/java/com/zin/jadxaimcp/utils/JadxSearchLock.java` — ReadWriteLock, tracking reset fix
- `src/main/java/com/zin/jadxaimcp/utils/ClassCacheManager.java` — Decompiled code LRU cache
- `src/main/java/com/zin/jadxaimcp/utils/ResourceCacheManager.java` — Strings cache

---

## [6.1.5] - 2026-03-18

### 🚀 Improvements

**Deployment & Configuration**
- Docker Compose timezone is now configurable via `TZ` env var (default: `UTC`, was hardcoded `Asia/Shanghai`)
- Added `docker/.env.example` with documented environment variables
- Added `/health` endpoint (lightweight, no auth required); Docker healthcheck now uses it
- Startup warning when default tokens (`admin-secret-token`, `jadx-plugin-secret-token`) are in use

**Unified Error Response Format**
- New `make_error(code, message, **extra)` helper for standardized error responses
- Added error codes: `RATE_LIMITED`, `TIMEOUT`, `INTERNAL_ERROR`
- All error returns in `config.py`, `transfer_tools.py`, `instance_tools.py` now use consistent `{error, message}` format

**Status Page Enhancements**
- Warning section hidden when no warnings (SSR + JS toggle)
- Instance table horizontally scrollable on mobile (`overflow-x:auto`)
- Scheduler column header/cells have tooltip explaining `m=metadata c=code_read x=exclusive q=queue`
- Refresh failure shows red error indicator (`.refresh-error` CSS class)
- Session cookie now expires after 24 hours (`max_age=86400`)

**Login CSRF Protection**
- Double-submit cookie pattern for `/status/login` POST endpoint
- CSRF token generated on every page render, validated on form submit

**Code Architecture**
- Extracted 30+ inline tool registrations from `jadx_mcp_server.py` into `register_*_tools()` functions in 6 tool modules
- Main server file reduced from 1366 to 595 lines (56% reduction)
- Each tool module now self-registers via `register_class_tools(mcp, with_busy_check)` pattern

**Instance Fallback**
- When default instance is disconnected, automatically falls back to first connected instance
- New `InstanceRegistry.get_first_connected()` method

**Rename Dry-Run**
- `rename` tool now accepts `dry_run=True` parameter
- Returns target existence check and class info preview without executing the rename

### 📦 Changed Files
- `docker/docker-compose.yaml` — TZ configurable, healthcheck uses `/health`
- `docker/.env.example` — New file
- `docker/scripts/start.sh` — Default token warning
- `jadx-mcp-server/jadx_mcp_server.py` — Tool registration extracted, token warnings
- `jadx-mcp-server/src/server/types.py` — `make_error()`, new error codes
- `jadx-mcp-server/src/server/config.py` — Unified error format, instance fallback
- `jadx-mcp-server/src/server/status_page.py` — Warnbox hide, scroll, tooltip, CSRF, refresh error
- `jadx-mcp-server/src/server/instance_registry.py` — `get_first_connected()`
- `jadx-mcp-server/src/server/tools/*.py` — `register_*_tools()` functions added
- `jadx-mcp-server/tests/test_status_page.py` — CSRF test cases

---

## [6.1.4] - 2026-03-02

### 🐛 Bug Fixes

**Cross-Classloader Port Leak**
- Fixed port leak when JADX performs "Reset Code Cache" (classloader reload)
- Uses JVM-global `System.getProperties()` to store `ServerSocketChannel` reference across classloaders
- Automatically closes orphaned server sockets before rebinding, preventing `BindException`

**Stale Menu Cleanup**
- Fixed duplicate "JADX AI MCP Server" menu entries after classloader reload
- Removes stale menu items by text-match before adding new ones (reverse-iteration, EDT-safe)

### 🛡️ MCP Error Handling

**Structured Error Responses**
- Added instance status pre-check: returns structured error when instance is `disconnected` or `pending`
- Fine-grained HTTP exception handling: `ConnectError`, `ConnectTimeout`, `ReadTimeout` each return actionable `suggestion` field
- Enhanced HTTP 500 responses with truncated error details and recovery guidance
- Enhanced HTTP 503 responses with `retry_after` parsing and initialization status

### 📚 Documentation

- Complete documentation restructure: consolidated 44 bilingual guides
- Added architecture overview and introduction pages
- Replaced FAQ/Windows troubleshooting with unified common-issues guide
- Streamlined README with focused feature table

### ⚙️ CI/CD

- Split base image build into standalone `docker-base.yml` workflow
- Matrix builds with native ARM runners (`ubuntu-24.04-arm`) — 3min vs 20min with QEMU
- Updated `JADX_VERSION` to 1.5.5, `BASE_IMAGE_VERSION` to 1.2
- Removed unused `test.yml` workflow

### 🔧 Code Quality

- Removed debug tools (`DebugRoutes.java`, `debug_tools.py`)
- Code review fixes and debug code removal

---

## [6.1.2] - 2026-02-06

### 🐛 Bug Fixes

**Docker Container Security Hardening**
- Fixed supervisord PID file permission: changed from `/var/run/supervisord.pid` to `/tmp/supervisord.pid`
- Fixed UID conflict: changed from UID 1000 to UID 1001 (base image already has `ubuntu` user at UID 1000)
- Fixed uv binary permission: changed from symlink to copy (`ln -s` → `cp`) to allow non-root user access
- Fixed `/var/log/supervisor` directory permission for non-root user
- Fixed `/apks` directory permission for non-root user
- Added X11 socket directory `/tmp/.X11-unix` with proper permissions

**Dockerfile.local**
- Added missing non-root user configuration (was running as root)

**Dockerfile.mcp**
- Added non-root user `mcp` (UID 1001) for improved security
- Fixed uv binary permission (symlink → copy)

### 🔒 Security Enhancements

- All Docker containers now run as non-root user (UID 1001)
- Updated base image version to 1.2 with security fixes
- Implemented timing-safe token comparison to prevent timing attacks

### 🛡️ Code Quality

- Added batch size input validation (maximum 20 classes per request)
- Added conservative fallback (5000 bytes/class) for size estimation failures

---

## [6.1.1] - 2026-02-05

### 🐛 Bug Fixes

**All-in-One Container**
- Fixed All-in-One container unable to connect to JADX instance
  - Changed default JADX instance from `host.docker.internal` to `127.0.0.1`
  - Fixed MCP Server connection configuration inside container

- Fixed supervisord startup failure
  - Removed undefined `JADX_MCP_BIND_ADDRESS` environment variable reference
  - Optimized container service binding address to `0.0.0.0`

### 📚 Documentation

**Port Documentation**
- Added comprehensive port reference table (6080/8650/8651)
- Detailed port purpose, access source, and security notes

**Deployment Scenarios**
- Added three deployment scenario guides:
  - **Standard Mode** (GUI + AI): `docker run -p 6080:6080 -p 8651:8651 ...`
  - **AI-Only Mode** (No GUI port exposed): `docker run -p 8651:8651 ...`
  - **Development Mode** (Full ports): `docker run -p 6080:6080 -p 8650:8650 -p 8651:8651 ...`

- Improved quick start commands with complete port mapping instructions
- Unified Chinese and English documentation

### 🐳 Docker

**Multi-Platform Support**
- Base image `xjoker/jadx-ai-mcp-base:1.1` upgraded to Java 25 + Ubuntu 24.04 Noble
- Main image `xjoker/jadx-ai-mcp:latest` supports linux/amd64 and linux/arm64

### 📦 Changed Files

- `README.md` / `README.zh-cn.md` - Documentation improvements
- `docker/Dockerfile` - Removed incorrect environment variable
- `docker/README.md` / `docker/README.zh-cn.md` - Docker documentation updates
- `docker/scripts/supervisord.conf` - Fixed configuration error
- `jadx-mcp-server/data/config/jadx-config.toml` - Default instance configuration

---

## [6.1.0] - 2026-01-20

### 🎉 Major Features

**Transfer API** - Large File Download System
- Bypass MCP message size limits (~16KB) for batch operations
- HTTP-based token system for direct data download
- Support for JSON and ZIP formats
- Multiple compression options (Brotli, GZIP, none)

**JAR/AAR/DEX Support** (Full JVM bytecode analysis)
- Transform JADX-AI-MCP from Android-only to universal JVM platform
- 5 JAR-specific tools + unified interface tools
- File type detection and dynamic tool availability

### Added

**Transfer API Tools**:
- `create_transfer_token` — Generate download token with configurable timeout
- `get_transfer_token_status` — Check token validity and usage status  
- `revoke_transfer_token` — Manually revoke token (auto-expires by default)

**Transfer API Endpoints** (HTTP):
- `/transfer/download/batch-classes` — Download multiple class sources
- Supports `format=json|zip` and `compression=br|gzip|none|auto`
- Rate limiting: 10 tokens/min creation, 20 requests/min download

**Configuration**:
- `MCP_SERVER_URL` environment variable (highest priority)
- `[server] mcp_url` in `jadx-config.toml`
- Auto-detection from startup parameters (fallback)

**Unified Interface Tools** (APK/JAR/AAR/DEX):
- `get_file_info` — Unified file metadata with type detection
- `get_config_strings` — Config strings (APK: strings.xml, JAR: *.properties)
- `get_package_classes` — Get classes by package with `auto=true` detection

**JAR-Specific Tools**:
- `jar_get_manifest` — Read META-INF/MANIFEST.MF
- `jar_get_services` — Read SPI services from META-INF/services/*
- `jar_get_entry_points` — Discover entry points (Main-Class, @SpringBootApplication)
- `jar_get_dependencies` — Analyze embedded dependencies
- `jar_get_bytecode` — View class bytecode structure

**Infrastructure**:
- `FileTypeDetector.java` — Magic number-based file type detection
- `NotApplicableResponse.java` — Unified NOT_APPLICABLE responses
- `jadx://capabilities` MCP Resource for dynamic tool availability
- Security: Rate limiting and parameter validation for Transfer API

### Changed
- APK-only tools return `NOT_APPLICABLE` instead of crashing on JAR files
- Tool docstrings enhanced with `Returns:` specifications
- Exception messages sanitized (removed `str(e)` in 6 places)

### Removed
- `set_jadx_port()` function (unused legacy code)
- `health_ping()` function (superseded by HealthMonitor)
- Deprecated `stateless_http` parameter from FastMCP initialization

### Fixed
- DeprecationWarning from FastMCP library
- Transfer API Python usage examples in tool documentation

### Technical Details
- **60+ files changed**, **+5,000 lines** of code
- Transfer API: Token store with auto-cleanup, single-use enforcement
- Tested with Nexus JAR (112,699 classes) and XHS APK (322,723 classes)
- Full backward compatibility maintained

### Docker
```bash
docker run -d \
  -e MCP_SERVER_URL="http://192.168.75.144:8651" \
  -p 6080:6080 -p 8650:8650 -p 8651:8651 \
  -v ./apks:/apks \
  xjoker/jadx-ai-mcp:latest
```



---

## [6.0.53] - 2026-01-16 18:26

### Added
- **`search_native_methods` tool** for JNI/SO security analysis
  - Searches all native methods across APK without triggering decompilation
  - Supports `package` filter and pagination
  - Returns Frida-compatible parameter types (`param_types_frida`)
  - Found 1,425 native methods in XHS app

---

## [6.0.52] - 2026-01-16 18:06

### Added
- **`native_method_names`** field in `get_class_info` response
  - Lists all native methods in a class for quick JNI analysis
  - `native_count` for summary statistics

### Changed
- Removed `frida_hook_template` from `get_method_signature` (AI can generate from type info)

---

## [6.0.51] - 2026-01-16 17:28

### Added
- **Frida-friendly output format** for methods and fields:
  - `type_frida` field in `get_fields_of_class` (e.g., `[B` for `byte[]`)
  - `frida_overload` string in `get_method_signature` for direct Frida hook
  - Structured JSON output for `/fields-of-class` and `/methods-of-class`
  - `is_static`, `is_native`, `overload_count` in method listings

### Breaking Changes
- `/fields-of-class` now returns JSON (was plain text)
- `/methods-of-class` now returns JSON (was plain text)

---

## [6.0.50] - 2026-01-16 15:32

### Added
- **Disable auto-rename for accurate Hook development**
  - Docker: Added `--rename-flags none` to `jadx-gui-wrapper.sh`
  - Plugin: Clears `renameFlags` on startup via `JadxArgs` API
  - Field/method names now match actual runtime names (e.g., `a` instead of `f439360a`)

---

## [6.0.49] - 2026-01-16 11:36


### Added
- **MCP Resources** for AI-guided decision making:
  - `usage-guide`: Complete tool usage reference
  - `decision-matrix`: Performance-aware tool selection guide
  - `performance-benchmarks`: Expected timing for all operations
- MCP Instructions for proactive guidance
- Enhanced tool docstrings with performance characteristics

---

## [6.0.48] - 2026-01-16 11:27

### Added
- **Smart batch parallel search optimization**
- Removed deprecated `class_offset`/`class_limit` from tool registration

---

## [6.0.47] - 2026-01-16 10:37

### Added
- Compatibility table documentation
- Enhanced example configuration files

---

## [6.0.46] - 2026-01-15 18:55

### Added
- Performance warnings in tool docstrings for large classes/resources
- Documentation for tool timeout behavior

### Fixed
- Docker Compose multi-instance deployment with `JADX_MCP_BIND_ADDRESS`

---

## [6.0.45] - 2026-01-15 18:24

### Fixed
- `clear_class_cache` correct InstanceRegistry usage
- Documentation updates for cache management

---

## [6.0.44] - 2026-01-15 18:14

### Changed
- Version bump for release

---

## [6.0.43] - 2026-01-15 18:05

### Added
- 30-second global cooldown for cache clear operations
- Optimized `RefactoringRoutes` with debounced cache invalidation

---

## [6.0.42] - 2026-01-15 17:22

### Added
- Complete ClassCacheManager rollout to all 5 batch tools:
  - `batch_get_class_source`
  - `batch_get_method_by_name`
  - `batch_get_xrefs`
  - `batch_get_method_callees`
  - `batch_get_method_callers`

---

## [6.0.41] - 2026-01-15 17:02

### Added
- ClassCacheManager integration for batch tools

---

## [6.0.40] - 2026-01-15 16:56

### Added
- Automatic cache invalidation on rename operations
- `clear_class_cache` MCP tool for manual cache clearing

---

## [6.0.39] - 2026-01-15 16:38

### Added
- **ClassCacheManager** for optimized batch class source retrieval
- Enhanced loading status messages with progress indicators
- `LOADING` status response for in-progress cache operations

---

## [6.0.38] - 2026-01-15 16:21

### Added
- Initial ClassCacheManager implementation for `batch_get_class_source`

---

## [6.0.37] - 2026-01-15 15:17

### Changed
- Updated Python MCP tool definitions for AI-friendly strings API

---

## [6.0.36] - 2026-01-15 15:13

### Added
- `[JAI]` prefix and timestamps to all log messages
- Improved log readability for debugging

---

## [6.0.35] - 2026-01-15 15:05

### Added
- **AI-friendly strings API with 4 modes**:
  - `summary`: Overview with key counts
  - `list`: List of all string names
  - `search`: Search strings by keyword
  - `get`: Get specific string by name/ID

---

## [6.0.34] - 2026-01-15 15:00

### Fixed
- `get_strings` performance optimization - avoid loading all file contents

---

## [6.0.33] - 2026-01-15 14:38

### Fixed
- Removed misleading `progress_percent` from responses
- Added accurate health monitoring for ResourceCacheManager

---

## [6.0.32] - 2026-01-15 14:35

### Added
- Comprehensive health monitoring for ResourceCacheManager
- Cache status endpoints for debugging

---

## [6.0.31] - 2026-01-15 14:31

### Added
- 100% automated `get_strings` using ResourceCacheManager
- Background resource caching

---

## [6.0.30] - 2026-01-15 14:28

### Fixed
- Rewrote `handleStrings` to be purely non-blocking
- Eliminated EDT blocking issues

---

## [6.0.29] - 2026-01-15 14:24

### Added
- Detailed logging for `getOpenedResourceTabs` diagnosis

---

## [6.0.28] - 2026-01-15 14:11

### Added
- Hybrid resource loading (GUI tabs + non-blocking EDT fallback)

---

## [6.0.27] - 2026-01-15 01:49

### Changed
- Improved status messages for `get_strings` TAB access

---

## [6.0.26] - 2026-01-15 01:46

### Added
- GUI tab-based resource access (eliminates `loadContent` blocking)

---

## [6.0.25] - 2026-01-15 01:32

### Fixed
- Replaced `ctx.future()` async with synchronous `Future.get(timeout)`

---

## [6.0.24] - 2026-01-15 01:12

### Fixed
- Python `get_strings` handler for new response format

---

## [6.0.23] - 2026-01-15 01:02

### Fixed
- Dedicated single-thread executor for async resource loading

---

## [6.0.22] - 2026-01-15 00:52

### Added
- Async HTTP resource loading with 60-second timeout

---

## [6.0.21] - 2026-01-15 00:47

### Fixed
- Skip `resources.arsc` parsing in `get_strings` to prevent server hang

---

## [6.0.20] - 2026-01-15 00:32

### Changed
- Reverted to original synchronous loading
- Removed background cache (stability issues)

---

## [6.0.19] - 2026-01-15 00:23

### Changed
- Reverted `get_strings` to original behavior with variants support

---

## [6.0.18] - 2026-01-15 00:12

### Fixed
- Added 5-second per-file timeout for `get_strings` content loading

---

## [6.0.17] - 2026-01-14 23:54

### Added
- O(1) pre-computed `strings.xml` cache

---

## [6.0.16] - 2026-01-14 23:38

### Added
- **ResourceCacheManager** for unified resource caching
- Background preloading for large APKs

---

## [6.0.15] - 2026-01-14 23:24

### Added
- Background caching for `get_strings` on large APKs

---

## [6.0.14] - 2026-01-14 23:04

### Fixed
- `get_strings` timeout with streaming pagination

---

## [6.0.13] - 2026-01-14 21:22

### Added
- Complete Docker and local deployment documentation
- Volume reference guides

---

## [6.0.12] - 2026-01-14 20:45

### Added
- Fast-fail search lock with retry hint
- `BUSY` response for concurrent search operations

---

## [6.0.11] - 2026-01-14 20:37

### Added
- **Global JadxSearchLock** for thread-safe search operations
- Prevents search result corruption from concurrent requests

---

## [6.0.10] - 2026-01-14 20:15

### Fixed
- Removed MAX_SCAN limit from `searchByCode`

### Added
- Version display in JADX plugin UI

---

## [6.0.9] - 2026-01-14 19:51

### Changed
- Use 'dev' placeholder for versions (replaced by CI at build time)

---

## [6.0.7] - 2026-01-14 17:09

### Changed
- Split Docker base image for faster CI builds
- Reduced image build time by 60%

---

## [6.0.6] - 2026-01-13 18:03

### Fixed
- Maven shade plugin warnings suppression
- Filter `module-info.class` and signature files
- Use `ServicesResourceTransformer` for SPI merging

---

## [6.0.5] - 2026-01-13 17:40

### Added
- **Batch retrieval tools**:
  - `batch_get_class_source`
  - `batch_get_method_by_name`

---

## [6.0.4] - 2026-01-13 16:28

### Added
- Environment variable support for Docker deployment
- `JADX_HOST`, `JADX_PORT`, `JADX_MCP_AUTH_TOKEN`

---

## [6.0.3] - 2026-01-13 11:15

### Changed
- Documentation cleanup and consolidation
- Translated all code comments to English
- Unified `.gitignore` configuration

---

## [6.0.2] - 2026-01-12 21:45

### Added
- **Multi-instance JADX support** - connect multiple JADX instances
- **Unified settings panel** in JADX GUI for plugin configuration
- `instance_id` parameter for all MCP tools
- Instance management tools: `list_jadx_instances`, `add_jadx_instance`, etc.

---

## [6.0.1] - 2026-01-12 16:59

### Fixed
- CI sync version from git tag to `pom.xml`

### Changed
- Initial fork from [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp)
- Bumped version to 6.0.x series

---

## Pre-Fork History

For changes before v6.0.1, see the [original repository](https://github.com/zinja-coder/jadx-ai-mcp).
