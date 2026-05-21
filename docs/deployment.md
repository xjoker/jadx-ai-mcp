# Deployment Runbook — jadx-ai-mcp

Audience: ops engineer doing a first-time or upgrade deployment.  
Reading time: ~5 min.

---

## Container Architecture

```
┌─────────────────────────────────────────────────────┐
│  docker container  (jadx-ai-mcp)                    │
│                                                     │
│  supervisord                                        │
│  ├── Xvfb / fluxbox / x11vnc  (virtual display)    │
│  ├── noVNC  :6080  ──────────────────────────────── │──► host :6080  (browser GUI)
│  ├── jadx-gui  (loads APK via /apks mount)          │
│  │     └── Java HTTP plugin  :8650 (internal)       │
│  └── Python MCP server  :8651  ─────────────────── │──► host :8651  (MCP endpoint)
│                           │ proxies to              │
│                       127.0.0.1:JADX_API_PORT       │
└─────────────────────────────────────────────────────┘
```

Key: the Java plugin binds to `JADX_MCP_PORT` (default 8650 inside the plugin).  
The Python server reads `JADX_API_PORT` to know where to proxy.  
**Both must agree.** See [Port collision gotcha](#port-collision-jadx_mcp_port-8651).

---

## Quick Start

```bash
docker run -d \
  --name jadx \
  -p 6080:6080 \
  -p 8650:8650 \
  -p 8651:8651 \
  -v /data/jadx-home/.jadx:/home/jadx/.jadx \
  -v /data/jadx-home/.cache:/home/jadx/.cache \
  -v /data/jadx-home/.local:/home/jadx/.local \
  -v /apks:/apks \
  -e JADX_API_PORT=8650 \
  -e JADX_MCP_PORT=8650 \
  -e JADX_MCP_AUTH_TOKEN=change-me \
  -e JADX_MCP_AUTH_ENABLED=true \
  -e JADX_FILE_ROOT=/apks \
  xjoker/jadx-ai-mcp:6.3.0
```

> **Do NOT** add `-v /data/jadx-home/.config:/home/jadx/.config`.
> The image bundles the JADX plugin into `/home/jadx/.config/jadx/plugins/`.
> Bind-mounting `.config` hides the plugin directory and the Java HTTP server
> never starts. See [Gotchas](#config-mount-kills-the-plugin).

---

## Target File Auto-Loading

Place (or symlink) your APK/JAR at one of these paths **before** starting the container.  
The wrapper script auto-loads on first-match priority:

| Priority | Path               |
|----------|--------------------|
| 1        | `/apks/target.apk` |
| 2        | `/apks/target.jar` |
| 3        | `/apks/target.aar` |
| 4        | `/apks/target.dex` |

Bootstrap example:

```bash
ln -sf /data/uploads/MyApp-1.2.3.apk /apks/target.apk
docker start jadx
```

---

## Health Check Verification

```bash
# 1. Container status (should show "healthy" after ~30s)
docker ps --filter name=jadx --format '{{.Status}}'

# 2. Java plugin REST endpoint (direct)
curl -s -H "X-Auth-Token: $JADX_MCP_AUTH_TOKEN" \
     http://localhost:8650/health | python3 -m json.tool

# 3. Python MCP proxy health
curl -s http://localhost:8651/health | python3 -m json.tool

# Expected response fields: status=ok, decompile_status, memory.usage_percentage
```

Wait for `decompile_status.cached_percentage` to reach ≥ 20 % before running heavy searches.

---

## Upgrade Procedure

```bash
# 1. Tag-backup current container
docker rename jadx jadx-backup

# 2. Pull new image
docker pull xjoker/jadx-ai-mcp:6.3.0

# 3. Start new container (same mounts + env)
docker run -d \
  --name jadx \
  ... (same flags as Quick Start) ...
  xjoker/jadx-ai-mcp:6.3.0

# 4. Wait for healthy (~30s)
until [ "$(docker inspect --format '{{.State.Health.Status}}' jadx 2>/dev/null)" = "healthy" ]; do
  sleep 5
done

# 5. Verify
curl -s -H "X-Auth-Token: $JADX_MCP_AUTH_TOKEN" http://localhost:8650/health

# 6. Clean up old container
docker rm jadx-backup
```

---

## Rollback Procedure

You have approximately 25 seconds from start before the health check timer marks the new container unhealthy and supervisord restarts services.

```bash
docker stop jadx && docker rm jadx
docker rename jadx-backup jadx
docker start jadx
```

Confirm recovery:

```bash
docker ps --filter name=jadx --format '{{.Status}}'
```

---

## Tunable Environment Variables

All variables are read at JVM startup; a container restart is required to apply changes.

| Variable | Default | Recommended Range | Controls |
|---|---|---|---|
| `JADX_API_PORT` | `8650` | — | Port the Python MCP proxy uses to reach the Java plugin. Must match `JADX_MCP_PORT`. |
| `JADX_MCP_PORT` | `8650` (plugin default); `8651` in image ENV | Set to `8650` | Port the Java plugin HTTP server binds to. Image default of 8651 collides with Python; override to 8650. |
| `JADX_MCP_AUTH_TOKEN` | `jadx-plugin-secret-token` | Any strong secret | Bearer token checked on every request when auth is enabled. Superseded by `JADX_MCP_AUTH_TOKEN_FILE` when set. |
| `JADX_MCP_AUTH_TOKEN_FILE` | _(none)_ | `/run/secrets/jadx_token` | Path to a file containing the service-account token. Whitespace trimmed automatically. Takes priority over `JADX_MCP_AUTH_TOKEN`. Token rotation via UI/API is disabled in this mode. See [File-mount / Docker Secrets](#file-mount--docker-secrets) below. |
| `JADX_MCP_AUTH_ENABLED` | `true` | `true` (production) | Enables/disables token authentication. |
| `JADX_MCP_BIND_ADDRESS` | `0.0.0.0` | `0.0.0.0` or `127.0.0.1` | Address the Java plugin HTTP server binds to. Supersedes `JADX_API_BIND_LOOPBACK_ONLY`. |
| `JADX_API_BIND_LOOPBACK_ONLY` | _(none)_ | `true` | Set to `true` to bind the Java plugin HTTP server to `127.0.0.1` instead of `0.0.0.0`. Useful when Python MCP proxy runs on the same host/container network and external access to port 8650 is undesired. Has no effect if `JADX_MCP_BIND_ADDRESS` is also set. |
| `JADX_MCP_MAX_THREADS` | `64` | `32`–`128` | Jetty QTP max worker threads. Increase for high concurrency. |
| `JADX_MCP_QUEUE_SIZE` | `64` | `32`–`256` | Jetty accept queue depth. Requests beyond this return 503. |
| `JADX_MCP_SEARCH_FOLLOWER_TIMEOUT_SECONDS` | `15` | `10`–`30` | How long the leader waits for follower instances during federated search. |
| `JADX_FILE_ROOT` | _(none)_ | `/apks` | Enables `load_file` / `list_available_files` MCP tools. Sandbox root; only paths under this directory are accessible. Auto-detected if `/apks` mount is present. |
| `JADX_MCP_WARMUP_TOP_K` | `100` | `0` (disable) – `500` | Number of most-referenced classes to predecompile at startup. Set to 0 to disable. |
| `JADX_MCP_INLINE_RESPONSE_MAX_BYTES` | `32768` | `16384`–`131072` | Responses larger than this are returned as a transfer token URL instead of inline JSON. |
| `JADX_MCP_CODE_INDEX_ENABLED` | `true` | `true` | Enables trigram inverted index for fast `search_in=code`. |
| `JADX_MCP_CODE_INDEX_MAX_TRIGRAMS` | `500000` | `200000`–`1000000` | Trigram hard cap; index stops accepting new classes when reached. Higher = more RAM. Raised from 200 000 in v6.4. |
| `JADX_MCP_CODE_INDEX_MAX_CLASS_SIZE_BYTES` | `1048576` | `262144`–`2097152` | Classes with decompiled source larger than this are skipped by the trigram indexer. |
| `JADX_MCP_CODE_INDEX_EVICTION_ENABLED` | `true` | `true` / `false` | Enables adaptive eviction: background sweeps remove low-selectivity trigrams under heap pressure. Set `false` to disable. |
| `JADX_MCP_CODE_INDEX_HEAP_PRESSURE_HIGH` | `0.80` | `0.70`–`0.90` | Heap used/max ratio that triggers an eviction sweep. |
| `JADX_MCP_CODE_INDEX_HEAP_PRESSURE_LOW` | `0.70` | `0.60`–`0.85` | Heap ratio below which eviction stops (hysteresis). Must be less than HIGH. |
| `JADX_MCP_HEAP_WATCHER_INTERVAL_SECONDS` | `10` | `5`–`60` | How often the heap-watcher thread checks JVM memory pressure. |

---

## Common Gotchas

### `.config` mount kills the plugin

**Symptom:** container starts, noVNC `:6080` works, but all REST calls to `:8650` fail with connection refused. Python MCP server logs show repeated "connect: Connection refused" to `127.0.0.1:8650`.

**Cause:** the image installs the JADX plugin JAR into `/home/jadx/.config/jadx/plugins/`. Bind-mounting a host directory at `/home/jadx/.config` shadows the entire directory — the plugin JAR is gone, the Java HTTP server is never registered, so port 8650 is never opened.

**Fix:** only mount subdirectories — `.jadx`, `.cache`, `.local` — not `.config`.

---

### Port collision: `JADX_MCP_PORT=8651`

**Symptom:** Java plugin logs `Address already in use: 0.0.0.0:8651`. Container goes unhealthy. Python MCP server starts successfully (it owns 8651) but the Java plugin can't bind.

**Cause:** the image `Dockerfile` sets `ENV JADX_MCP_PORT=8651` as a default (historical artifact). The Python MCP server also listens on 8651. At runtime both processes try to bind the same port.

**Fix:** always pass `-e JADX_MCP_PORT=8650 -e JADX_API_PORT=8650` explicitly. Port 8650 is the Java plugin's own compiled-in default; it is never claimed by any other process in the container.

---

### `target.apk` symlink convention

The wrapper looks for exact filenames (`target.apk`, `target.jar`, etc.), not glob patterns.  
If your build pipeline names files with version suffixes, create a symlink:

```bash
ln -sf MyApp-2.0.0.apk /apks/target.apk
```

Re-link before restarting the container when switching target apps.

---

## Multi-APK Workflows

The `analyze_apk` and `list_loaded_files` MCP tools wrap the lower-level
`load_file` / instance-registry primitives into AI-friendly single-call
operations. No new Java endpoints are required.

### "Open this APK"

```
AI: analyze_apk("target.apk")
```

The tool inspects all connected instances:
- **One instance, no file loaded** → loads immediately, returns `status=loaded`.
- **One instance with a file** → returns `status=ambiguous` with three choices
  (replace, new_instance, append). The AI picks and retries.
- **Multiple instances** → picks a free one automatically.
- **All busy** → returns `status=all_busy` with guidance to call
  `scale_instances` or `remove_jadx_instance`.

After `status=loaded`, poll `get_decompile_status` until
`cached_percentage` stabilises before running heavy searches.

### "Compare these two APKs"

Spin up two workers, then load each APK into its own instance:

```
1. scale_instances(target_count=2)
2. analyze_apk("app-v1.apk", strategy="new_instance")   # loads on worker-1
3. analyze_apk("app-v2.apk", strategy="new_instance")   # loads on worker-2
4. list_loaded_files()                                   # confirm both ready
```

Cross-reference with `get_xrefs` / `search_classes_by_keyword` passing the
appropriate `instance_id` for each side of the comparison.

### "Analyze APK with JAR dependencies"

Load the main APK first, then append each library:

```
1. analyze_apk("app.apk")                         # replace mode (default auto)
2. analyze_apk("libs/gson.jar", strategy="append")  # add dep to open project
3. analyze_apk("libs/okhttp.jar", strategy="append")
```

The `append` strategy calls `load_file(mode="append")` on the default
instance. After each append, JADX re-indexes and updates the decompile cache
— wait for `cached_percentage` to settle before searching dependency code.

### list_loaded_files

Returns a snapshot of what every instance currently holds:

```json
{
  "instances": [
    {"name": "default", "loaded_file": "target.apk",
     "decompile_progress": 0.7, "available": false},
    {"name": "worker-1", "loaded_file": null, "available": true}
  ],
  "count": 2,
  "free_count": 1
}
```

Use this before routing manual `load_file` calls to pick the right
`instance_id`, or to confirm both instances are ready before cross-APK
analysis.

---

## File-mount / Docker Secrets

Using `JADX_MCP_AUTH_TOKEN_FILE` is the recommended way to inject the shared Java–Python service-account token in production. It avoids putting secrets in environment variables (visible in `docker inspect` and process lists).

### How it works

Both sides read the same file:

| Component | Variable | Behaviour |
|---|---|---|
| Java plugin | `JADX_MCP_AUTH_TOKEN_FILE` | Reads file at startup; trims whitespace. Token rotation via UI/API disabled. Fails fast if file is unreadable. |
| Python MCP proxy | `JADX_MCP_AUTH_TOKEN_FILE` | Reads file at startup; trims whitespace. Overrides `--auth-token` CLI and TOML `jadx_token`. |

### Quick example — docker secrets

```bash
# 1. Create the secret
echo -n "$(openssl rand -base64 32)" | docker secret create jadx_token -

# 2. Run the all-in-one container
docker run -d \
  --secret jadx_token,target=/run/secrets/jadx_token \
  -e JADX_MCP_AUTH_TOKEN_FILE=/run/secrets/jadx_token \
  -e JADX_MCP_AUTH_ENABLED=true \
  -v /path/to/app.apk:/apks/target.apk:ro \
  -p 8651:8651 \
  jadx-ai-mcp:latest
```

The file `/run/secrets/jadx_token` is mounted read-only by the Docker daemon. Both the Java plugin and the Python proxy read it and use the same token automatically.

### Rotating the token

1. Update the secret externally (`docker secret` update, Kubernetes `kubectl create secret --dry-run | kubectl apply`, etc.).
2. Restart the container (or restart the plugin from JADX GUI if in-process).
3. The UI **Regenerate** button and direct `setAuthToken` calls are disabled when `JADX_MCP_AUTH_TOKEN_FILE` is set; this is intentional.

### Loopback-only bind (defence-in-depth)

When the Python proxy and the Java plugin share the same network namespace (same container or `--network host`), you can restrict the Java plugin to loopback:

```bash
-e JADX_API_BIND_LOOPBACK_ONLY=true
```

This changes the default bind from `0.0.0.0` to `127.0.0.1`, so port 8650 is not reachable from outside the container at all. Do **not** set this when Python connects from a different container over a bridge network.
