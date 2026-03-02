# JADX MCP Server AI Automated Testing Prompt

**English** | [简体中文](ai-prompts.zh-cn.md)

---

This document provides a complete prompt template for AI-assisted testing of JADX MCP Server.

## Usage

Copy the prompt below into an AI conversation to start automated testing.

## ❗ Pre-Test Environment Setup (Important)

To ensure accurate test results, **JADX must be started without cache**:

### Clear JADX Cache:

```bash
# macOS/Linux
rm -rf ~/.cache/jadx-gui/

# Windows
rmdir /s /q %USERPROFILE%\.cache\jadx-gui
```

### Test Startup Procedure:

1. Close all JADX-GUI instances
2. Run the above command to clear cache
3. Restart JADX-GUI and open target APK
4. **Do not wait for decompilation to complete**, start testing immediately
5. Monitor decompilation progress via `get_decompile_status`

> ➡️ This allows testing performance differences between cached and uncached scenarios

---

## Test Prompt

```
Please perform comprehensive testing of the JADX MCP Server project, targeting 100% pass rate.

## Test Objectives
1. Verify all MCP tools functionality (excluding debug_* tools)
2. Boundary condition testing (offset/count limits)
3. Exception input testing (non-existent class/method/field, empty input, etc.)
4. Pagination mechanism verification (first page, middle page, last page)
5. Batch operation correctness (partial success, all failed, etc.)
6. Performance benchmark verification (class/method/field search <1s, code search <60s)
7. Result consistency verification (same input returns same results)
8. Cache mechanism verification (uncached cold start vs cached warm start)
9. Cache clear and invalidation verification (clear_class_cache, auto-invalidation after rename)

## Test Phases

### Phase 1: Search Tools Testing (~25 cases)
Tools to test:
- search_classes_by_keyword
  - search_in parameter: class, method, field, code, comment, combinations
  - count boundary: 1, 10, 50, 100, 200
  - offset pagination: first page, middle, last page, out of range
  - filters: package, exclude, combinations
  - special input: single character, special characters, non-existent terms
  - timeout test: 60-second timeout for code/comment search
  - early exit verification: common words trigger early exit
  - repeat test: same input 3 times for consistency
- search_method_by_name
  - different method names: onClick, get, init, setup, parse
  - full pagination to end
  - boundary and empty result tests

### Phase 2: P0/P1 Core Functionality Testing (~25 cases)
Tools to test:
- get_class_source: normal class, non-existent class, system class
- batch_get_class_source: normal batch, all non-existent, partial exists, empty list
- get_method_by_name: successful fetch, constructor <init>, non-existent method
- get_android_manifest: get complete Manifest
- get_class_info: verify inheritance, method count, field count
- get_xrefs_to_class: cross-references and pagination
- get_xrefs_to_method: successful reference fetch
- get_xrefs_to_field: field reference test
- get_all_classes: pagination test (first page, last page)
- get_strings: all modes (summary, list, search, get) and locale switching
- get_methods_of_class, get_fields_of_class: full list
- get_decompile_status: status check

### Phase 3: P2 Functionality Testing (~10 cases)
Tools to test:
- get_smali_of_class: small class, medium class, large class, non-existent class
- get_method_signature: signature retrieval
- get_method_callees: methods with and without calls
- get_main_activity_class: main Activity
- get_main_application_classes_names
- get_all_resource_file_names: pagination test
- get_resource_file: normal resource, non-existent resource

### Phase 4: Batch Operations and Pagination Verification (~10 cases)
- batch_get_method_by_name: normal batch, boundary (1/20 items), exceeds limit, partial exists, empty list
- batch_get_xrefs: mixed types (class+method+field), all non-existent, single target
- Systematic pagination: last page verification for 3 tools
  - get_all_classes last page
  - get_all_resource_file_names last page
  - get_xrefs_to_class last page

### Phase 5: Concurrency and Limit Testing (~10 cases)
- check_instance_status: instance status
- count limit: count=200, count=500 (exceeds limit)
- offset limit: offset exceeds total
- empty input test: empty string search_term

### Phase 6: Cache Testing (~15 cases)

#### 6.1 Uncached Tests (Cold Start)
- Clear JADX cache and restart
- Test search_classes_by_keyword(search_in=code): expect 60s timeout
- Test search_classes_by_keyword(search_in=class): expect instant
- Record first code search execution time
- Verify get_decompile_status: should show loading status and progress

#### 6.2 Cached Tests (Warm Start)
- Without clearing cache, use already decompiled APK
- Test search_classes_by_keyword(search_in=code): expect faster than uncached
- Test same class source multiple times: verify cache hit
- Repeat 3 times: verify 100% consistent results

#### 6.3 Cache Clear Functionality Test
- Call clear_class_cache
- Verify 30-second global cooldown mechanism
- Call again within 30s: should return cooldown_remaining_seconds
- Call after 30s: should succeed

#### 6.4 Resource Cache Test
- First call get_strings: triggers resource cache loading
- Verify status=loading_started or status=loading
- After loading, call again: should return immediately
- Verify cache independence for different locales

#### 6.5 Cache Consistency Verification
- Use rename_class to rename a class
- Verify cache auto-invalidation
- Get renamed class source: should reflect new name
- Verify xrefs update

## Cache Test Environment Preparation

### Uncached Test Steps:
1. Close JADX-GUI
2. Delete ~/.cache/jadx-gui/ directory (or equivalent)
3. Reopen APK
4. Start testing immediately (don't wait for decompilation)

### Cached Test Steps:
1. Ensure JADX-GUI has fully decompiled the APK
2. Verify get_decompile_status shows cached_percentage > 50%
3. Then start testing

## Cache Test Validation Criteria

| Scenario | Uncached Expected | Cached Expected |
|----------|-------------------|-----------------|
| class search | <100ms | <100ms |
| method search | <100ms | <100ms |
| field search | <100ms | <100ms |
| code search | 60s timeout | Faster (depends on cache) |
| comment search | 60s timeout | Faster (depends on cache) |
| get_class_source | May be slower | <1s |
| get_strings first | Triggers loading | Immediate return |

## Validation Standards

### Each test case must record:
1. Tool name
2. Input parameters
3. Expected result
4. Actual result
5. Pass/Fail status
6. **Execution time** (required, unit: ms or seconds)
7. Response size (if applicable)

### Pass conditions:
- ✅ Correct functionality: returns expected data
- ✅ Correct error handling: returns clear error message (404/400, etc.)
- ✅ Correct pagination: has_more, next_offset, total fields are accurate
- ✅ Complete response: all required fields present

### Fail conditions:
- ❌ Incorrect functionality: returns wrong data
- ❌ Crash: request timeout or no response
- ❌ Missing fields: response lacks required fields
- ❌ Logic error: has_more/offset calculation errors

## Output Requirements

### For each phase generate:
1. Test case list (table format, include execution time column)
2. Pass/Fail statistics
3. **Execution time statistics** (min/max/avg)
4. Key findings

### Final Summary Report:
1. Total test case count
2. Overall pass rate
3. Tool coverage
4. Quality assessment (A+/A/B/C)
5. Improvements needed (if any)

## Notes

1. Complete each phase before moving to the next
2. When a failure is found, prioritize deep testing of related functionality
3. All test results must be clear pass or fail, no "pending" status
4. Repeat same tests 3 times to verify stability
5. Record all edge case behaviors
6. **Every test must record execution time**

## Excluded Tools (Not Tested)

The following tools are not in scope:
- `debug_get_stack_frames` - Requires debug session
- `debug_get_threads` - Requires debug session
- `debug_get_variables` - Requires debug session
- `fetch_current_class` - Depends on UI state
- `get_selected_text` - Depends on UI state

## Important Tools (Must Deep Test)

The following are core tools requiring strictest testing:

### P0 Core Tools (Required)
- `search_classes_by_keyword` - Search core
- `search_method_by_name` - Search core
- `get_class_source` - Decompilation core
- `get_method_by_name` - Method retrieval core
- `get_android_manifest` - APK analysis entry
- `get_xrefs_to_class` - Cross-reference core

### P1 High Priority Tools (Required)
- `batch_get_class_source` - Batch operations
- `batch_get_method_by_name` - Batch operations
- `batch_get_xrefs` - Batch operations
- `get_class_info` - Class analysis
- `get_strings` - Resource analysis
- `get_all_classes` - Class listing

## Cache-Related Tools Multiple Test Requirements

The following tools involve caching, **must be tested multiple times**:

| Tool | Test Count | Test Points |
|------|-----------|-------------|
| `search_classes_by_keyword` (code/comment) | ×3 | Verify speed improvement after cache hit |
| `get_class_source` | ×3 | First may be slow, subsequent should <1s |
| `get_strings` | ×3 | First triggers loading, subsequent instant |
| `get_smali_of_class` | ×2 | Should be faster after cache |
| `get_decompile_status` | ×5 | Monitor progress changes |
| `clear_class_cache` | ×2 | Verify 30s cooldown mechanism |

### Cache Test Verification Points

1. **First call**: Record execution time as baseline
2. **Second call**: Should be significantly faster (cache hit)
3. **Third call**: Should be similar to second (stability)
4. **Result consistency**: All calls must return 100% identical results

## Execution Time Benchmarks

| Operation | Expected Time | Warning Threshold |
|-----------|--------------|-------------------|
| search_in=class | <100ms | >500ms |
| search_in=method | <100ms | >500ms |
| search_in=field | <100ms | >500ms |
| search_in=code | <60s | Timeout normal |
| search_in=comment | <60s | Timeout normal |
| get_class_source | <1s | >3s |
| get_method_by_name | <1s | >3s |
| get_xrefs_to_* | <1s | >3s |
| batch_get_* | <3s | >10s |
| get_smali_of_class | <5s | >30s |
| Other tools | <1s | >3s |
```

---

## Estimated Test Cases

| Phase | Cases | Description |
|-------|-------|-------------|
| Phase 1: Search | 25 | Search functionality full coverage |
| Phase 2: P0/P1 | 25 | Core functionality tests |
| Phase 3: P2 | 10 | Secondary functionality tests |
| Phase 4: Batch/Pagination | 10 | Systematic verification |
| Phase 5: Limits | 10 | Boundary conditions |
| Phase 6: Cache | 15 | Cache mechanism verification |
| **Total** | **~95** | Complete coverage |

## Expected Pass Rate

- **Target pass rate**: 100%
- **Acceptable pass rate**: 95% (allows edge case failures)
