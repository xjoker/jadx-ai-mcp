# Changelog

All notable changes to JADX-AI-MCP are documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) and [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

> 🔱 This changelog covers changes since forking from [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp).

---

## [6.0.46] - 2026-01-15

### Added
- Performance warnings in tool docstrings for large classes/resources
- Documentation for tool timeout behavior

### Fixed
- Docker Compose multi-instance deployment with `JADX_MCP_BIND_ADDRESS`

---

## [6.0.45] - 2026-01-15

### Fixed
- `clear_class_cache` correct InstanceRegistry usage
- Documentation updates for cache management

---

## [6.0.44] - 2026-01-15

### Changed
- Version bump for release

---

## [6.0.43] - 2026-01-15

### Added
- 30-second global cooldown for cache clear operations
- Optimized `RefactoringRoutes` with debounced cache invalidation

---

## [6.0.42] - 2026-01-15

### Added
- Complete ClassCacheManager rollout to all 5 batch tools:
  - `batch_get_class_source`
  - `batch_get_method_by_name`
  - `batch_get_xrefs`
  - `batch_get_method_callees`
  - `batch_get_method_callers`

---

## [6.0.41] - 2026-01-15

### Added
- ClassCacheManager integration for batch tools

---

## [6.0.40] - 2026-01-15

### Added
- Automatic cache invalidation on rename operations
- `clear_class_cache` MCP tool for manual cache clearing

---

## [6.0.39] - 2026-01-15

### Added
- **ClassCacheManager** for optimized batch class source retrieval
- Enhanced loading status messages with progress indicators
- `LOADING` status response for in-progress cache operations

---

## [6.0.38] - 2026-01-15

### Added
- Initial ClassCacheManager implementation for `batch_get_class_source`

---

## [6.0.37] - 2026-01-15

### Changed
- Updated Python MCP tool definitions for AI-friendly strings API

---

## [6.0.36] - 2026-01-15

### Added
- `[JAI]` prefix and timestamps to all log messages
- Improved log readability for debugging

---

## [6.0.35] - 2026-01-15

### Added
- **AI-friendly strings API with 4 modes**:
  - `summary`: Overview with key counts
  - `list`: List of all string names
  - `search`: Search strings by keyword
  - `get`: Get specific string by name/ID

---

## [6.0.34] - 2026-01-15

### Fixed
- `get_strings` performance optimization - avoid loading all file contents

---

## [6.0.33] - 2026-01-15

### Fixed
- Removed misleading `progress_percent` from responses
- Added accurate health monitoring for ResourceCacheManager

---

## [6.0.32] - 2026-01-15

### Added
- Comprehensive health monitoring for ResourceCacheManager
- Cache status endpoints for debugging

---

## [6.0.31] - 2026-01-15

### Added
- 100% automated `get_strings` using ResourceCacheManager
- Background resource caching

---

## [6.0.30] - 2026-01-15

### Fixed
- Rewrote `handleStrings` to be purely non-blocking
- Eliminated EDT blocking issues

---

## [6.0.29] - 2026-01-15

### Added
- Detailed logging for `getOpenedResourceTabs` diagnosis

---

## [6.0.28] - 2026-01-15

### Added
- Hybrid resource loading (GUI tabs + non-blocking EDT fallback)

---

## [6.0.27] - 2026-01-15

### Changed
- Improved status messages for `get_strings` TAB access

---

## [6.0.26] - 2026-01-15

### Added
- GUI tab-based resource access (eliminates `loadContent` blocking)

---

## [6.0.25] - 2026-01-15

### Fixed
- Replaced `ctx.future()` async with synchronous `Future.get(timeout)`

---

## [6.0.24] - 2026-01-15

### Fixed
- Python `get_strings` handler for new response format

---

## [6.0.23] - 2026-01-15

### Fixed
- Dedicated single-thread executor for async resource loading

---

## [6.0.22] - 2026-01-15

### Added
- Async HTTP resource loading with 60-second timeout

---

## [6.0.21] - 2026-01-15

### Fixed
- Skip `resources.arsc` parsing in `get_strings` to prevent server hang

---

## [6.0.20] - 2026-01-15

### Changed
- Reverted to original synchronous loading
- Removed background cache (stability issues)

---

## [6.0.19] - 2026-01-15

### Changed
- Reverted `get_strings` to original behavior with variants support

---

## [6.0.18] - 2026-01-15

### Fixed
- Added 5-second per-file timeout for `get_strings` content loading

---

## [6.0.17] - 2026-01-14

### Added
- O(1) pre-computed `strings.xml` cache

---

## [6.0.16] - 2026-01-14

### Added
- **ResourceCacheManager** for unified resource caching
- Background preloading for large APKs

---

## [6.0.15] - 2026-01-14

### Added
- Background caching for `get_strings` on large APKs

---

## [6.0.14] - 2026-01-14

### Fixed
- `get_strings` timeout with streaming pagination

---

## [6.0.13] - 2026-01-14

### Added
- Complete Docker and local deployment documentation
- Volume reference guides

---

## [6.0.12] - 2026-01-14

### Added
- Fast-fail search lock with retry hint
- `BUSY` response for concurrent search operations

---

## [6.0.11] - 2026-01-14

### Added
- **Global JadxSearchLock** for thread-safe search operations
- Prevents search result corruption from concurrent requests

---

## [6.0.10] - 2026-01-14

### Fixed
- Removed MAX_SCAN limit from `searchByCode`

### Added
- Version display in JADX plugin UI

---

## [6.0.9] - 2026-01-14

### Changed
- Use 'dev' placeholder for versions (replaced by CI at build time)

---

## [6.0.7] - 2026-01-14

### Changed
- Split Docker base image for faster CI builds
- Reduced image build time by 60%

---

## [6.0.6] - 2026-01-13

### Fixed
- Maven shade plugin warnings suppression
- Filter `module-info.class` and signature files
- Use `ServicesResourceTransformer` for SPI merging

---

## [6.0.5] - 2026-01-13

### Added
- **Batch retrieval tools**:
  - `batch_get_class_source`
  - `batch_get_method_by_name`

---

## [6.0.4] - 2026-01-13

### Added
- Environment variable support for Docker deployment
- `JADX_HOST`, `JADX_PORT`, `JADX_MCP_AUTH_TOKEN`

---

## [6.0.3] - 2026-01-13

### Changed
- Documentation cleanup and consolidation
- Translated all code comments to English
- Unified `.gitignore` configuration

---

## [6.0.2] - 2026-01-12

### Added
- **Multi-instance JADX support** - connect multiple JADX instances
- **Unified settings panel** in JADX GUI for plugin configuration
- `instance_id` parameter for all MCP tools
- Instance management tools: `list_jadx_instances`, `add_jadx_instance`, etc.

---

## [6.0.1] - 2026-01-12

### Fixed
- CI sync version from git tag to `pom.xml`

### Changed
- Initial fork from [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp)
- Bumped version to 6.0.x series

---

## Pre-Fork History

For changes before v6.0.1, see the [original repository](https://github.com/zinja-coder/jadx-ai-mcp).
