# Batch Analysis Optimization Skill

## Overview

This skill guides AI agents on efficient batch operations when working with JADX-AI-MCP. Following these patterns ensures optimal performance and avoids timeouts or memory issues.

## Decision Flowchart

```
                    +---------------------------+
                    |     Start Batch Operation |
                    +---------------------------+
                                |
                                v
                    +---------------------------+
                    | 1. get_decompile_status() |
                    +---------------------------+
                                |
                                v
                    +---------------------------+
                    |   Check cached_percentage |
                    +---------------------------+
                                |
            +-------------------+-------------------+
            |                   |                   |
            v                   v                   v
      < 20% cached        20-50% cached       > 50% cached
            |                   |                   |
            v                   v                   v
    +---------------+   +---------------+   +---------------+
    | search_in=    |   | search_in=    |   | search_in=    |
    | 'class' or    |   | 'class',      |   | 'class',      |
    | 'method' ONLY |   | 'method', or  |   | 'method', or  |
    |               |   | 'code' (small)|   | 'code' (safe) |
    +---------------+   +---------------+   +---------------+
            |                   |                   |
            +-------------------+-------------------+
                                |
                                v
                    +---------------------------+
                    |   Estimate response size  |
                    +---------------------------+
                                |
            +-------------------+-------------------+
            |                   |                   |
            v                   v                   v
      < 20KB              20KB - 50KB           > 50KB
      (Normal)            (Large)              (Oversized)
            |                   |                   |
            v                   v                   v
    +---------------+   +---------------+   +-------------------+
    | Direct        |   | Execute with  |   | BATCH_TOO_LARGE   |
    | execution     |   | warning, may  |   | Use Transfer API  |
    |               |   | need chunking |   | or split request  |
    +---------------+   +---------------+   +-------------------+
            |                   |                   |
            +-------------------+-------------------+
                                |
                                v
                    +---------------------------+
                    |   Check _chunking field   |
                    +---------------------------+
                                |
                    +-----------+-----------+
                    |                       |
                    v                       v
            has_more=false          has_more=true
                    |                       |
                    v                       v
            +---------------+       +-------------------+
            | Done          |       | Call again with   |
            |               |       | chunk=N parameter |
            +---------------+       +-------------------+
```

## Step-by-Step Guide

### Step 1: Always Check System Status First

Before any batch operation, call `get_decompile_status` to understand the current state:

```python
status = get_decompile_status()
cached_pct = status["cached_percentage"]
total_classes = status["total_classes"]
```

Key metrics to check:
- `cached_percentage`: How much of the codebase is already decompiled
- `total_classes`: Total number of classes in the APK
- `decompile_mode`: Current decompilation mode

### Step 2: Choose Search Strategy Based on Cache Status

| Cache Status | Recommended `search_in` | Reason |
|:-------------|:------------------------|:-------|
| < 20% | `class` or `method` | Code search triggers decompilation, causing delays |
| 20% - 50% | `class`, `method`, or `code` (small queries) | Partial cache, code search may be slow |
| > 50% | `class`, `method`, or `code` | Most code is cached, safe for full search |

**Example:**

```python
if cached_pct < 20:
    # Use structural search only
    results = search_classes(pattern="*Activity*", search_in="class")
else:
    # Safe to search in code
    results = search_classes(pattern="password", search_in="code")
```

### Step 3: Use Tiered Strategy for batch_get_class_source

Estimate the response size before requesting multiple classes:

| Size Category | Estimated Size | Action |
|:--------------|:---------------|:-------|
| Normal | < 20KB | Direct execution |
| Large | 20KB - 50KB | Execute with warning, prepare for chunking |
| Oversized | > 50KB | Returns `BATCH_TOO_LARGE` error |

**Estimation heuristic:**
- Average class size: ~2-5KB
- Request 5-10 classes at a time for normal operations
- Never request more than 20 classes in a single batch

**Example:**

```python
# Good: Request a small batch
sources = batch_get_class_source(class_names=[
    "com.example.MainActivity",
    "com.example.LoginActivity",
    "com.example.BaseActivity"
])

# Bad: Requesting too many classes at once
sources = batch_get_class_source(class_names=[...50 classes...])  # Will fail
```

### Step 4: Handle Chunking for Large Responses

When a response is too large, the API returns chunked data. Check the `_chunking` field:

```python
response = batch_get_class_source(class_names=classes)

if response.get("_chunking", {}).get("has_more"):
    chunk_info = response["_chunking"]
    current_chunk = chunk_info["current_chunk"]
    total_chunks = chunk_info["total_chunks"]

    # Get next chunk
    next_response = batch_get_class_source(
        class_names=classes,
        chunk=current_chunk + 1
    )
```

**Chunking fields:**
- `has_more`: Boolean indicating if more chunks exist
- `current_chunk`: Current chunk number (0-indexed)
- `total_chunks`: Total number of chunks
- `chunk_size`: Number of items per chunk

### Step 5: Use Transfer API for Very Large Operations

For operations exceeding 16KB response size, use the Transfer API:

```python
# Instead of direct retrieval
large_source = get_class_source(class_name="com.example.VeryLargeClass")

# Use transfer API
transfer = create_transfer(
    type="class_source",
    class_name="com.example.VeryLargeClass"
)
transfer_id = transfer["transfer_id"]

# Retrieve in chunks
content = ""
while True:
    chunk = get_transfer_chunk(transfer_id=transfer_id)
    content += chunk["data"]
    if not chunk["has_more"]:
        break
```

## Best Practices

### Do's

1. **Always warm up the cache** for frequently accessed packages:
   ```python
   # Pre-cache a package before intensive operations
   warm_up_package(package="com.example.core")
   ```

2. **Use specific class names** instead of patterns when possible:
   ```python
   # Good: Specific classes
   get_class_source(class_name="com.example.MainActivity")

   # Less efficient: Pattern matching
   search_classes(pattern="*Activity*")
   ```

3. **Check decompile status periodically** during long operations

4. **Handle errors gracefully**:
   ```python
   try:
       sources = batch_get_class_source(class_names=classes)
   except BatchTooLargeError as e:
       # Split into smaller batches
       for chunk in split_list(classes, chunk_size=5):
           sources.extend(batch_get_class_source(class_names=chunk))
   ```

### Don'ts

1. **Don't use `search_in='code'`** when cache percentage is low
2. **Don't request more than 20 classes** in a single batch
3. **Don't ignore chunking indicators** - always check `has_more`
4. **Don't retry failed large requests** without reducing batch size

## Error Handling

| Error Code | Meaning | Resolution |
|:-----------|:--------|:-----------|
| `BATCH_TOO_LARGE` | Request exceeds size limit | Split into smaller batches or use Transfer API |
| `DECOMPILE_TIMEOUT` | Decompilation took too long | Wait for cache to warm up, use cached classes only |
| `CLASS_NOT_FOUND` | Class doesn't exist | Verify class name with `list_classes` |
| `CHUNK_NOT_FOUND` | Invalid chunk number | Start from chunk=0 |

## Performance Tips

1. **Parallel package analysis**: When analyzing multiple packages, check which are already cached and prioritize those.

2. **Incremental search**: Start with structural searches (`class`, `method`), then narrow down with code search only on relevant classes.

3. **Batch size tuning**: Start with 10 classes per batch, adjust based on average class size in the APK.

4. **Monitor memory**: Large APKs may require more conservative batch sizes. Check `get_decompile_status()` for memory indicators.

## Example Workflow

```python
# Complete optimized batch analysis workflow

# 1. Check system status
status = get_decompile_status()
print(f"Cache: {status['cached_percentage']}%")

# 2. Choose search strategy
if status['cached_percentage'] < 20:
    # Warm up critical packages first
    warm_up_package(package="com.target.app")

# 3. Search for target classes
results = search_classes(
    pattern="*Crypto*",
    search_in="class"  # Safe for any cache level
)

# 4. Batch retrieve in small chunks
class_names = [r["class_name"] for r in results[:10]]
sources = batch_get_class_source(class_names=class_names)

# 5. Handle chunking if needed
while sources.get("_chunking", {}).get("has_more"):
    next_chunk = sources["_chunking"]["current_chunk"] + 1
    more_sources = batch_get_class_source(
        class_names=class_names,
        chunk=next_chunk
    )
    # Merge results...

# 6. Process results
for class_name, source in sources.items():
    if not class_name.startswith("_"):  # Skip metadata fields
        analyze_source(class_name, source)
```
