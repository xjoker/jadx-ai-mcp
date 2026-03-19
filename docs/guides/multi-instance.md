# Multi-Instance Management

**English** | [简体中文](multi-instance.zh-cn.md)

---

> 🔄 Manage multiple JADX instances for parallel APK analysis

## Overview

JADX MCP Server supports connecting to multiple JADX instances simultaneously, enabling:

- **Parallel analysis**: Analyze different APKs at the same time
- **Version comparison**: Compare different versions of the same app
- **Team collaboration**: Each team member works on their own instance

---

## Instance Management Tools

| Tool | Description |
|:-----|:------------|
| `list_jadx_instances` | List all connected instances |
| `add_jadx_instance` | Dynamically add new instance |
| `remove_jadx_instance` | Remove an instance |
| `set_default_jadx_instance` | Set default instance |
| `get_jadx_instance_info` | Get instance details |
| `health_check_jadx_instances` | Check all instances health |

---

## Configuration

### Static Instances (Config File)

```toml
# jadx-config.toml
[[jadx_instances]]
name = "app-v1"
host = "192.168.1.10"
port = 8650
default = true

[[jadx_instances]]
name = "app-v2"
host = "192.168.1.11"
port = 8650
```

### Dynamic Instances (Runtime)

```python
# Add instance at runtime
add_jadx_instance(host="192.168.1.12", port=8650, name="dev-build")

# Switch default
set_default_jadx_instance(name="dev-build")
```

---

## Specifying Instance

Most tools accept `instance_id` parameter:

```python
# Query specific instance by name
get_class_source(class_name="com.example.Main", instance_id="app-v2")

# Compare across instances
source_v1 = get_class_source(class_name="com.example.Main", instance_id="app-v1")
source_v2 = get_class_source(class_name="com.example.Main", instance_id="app-v2")
```

### Fuzzy Matching (v6.1.6+)

`instance_id` supports fuzzy matching — you don't need the exact instance name:

```python
# Match by APK package name
get_class_source(class_name="...", instance_id="com.xingin.xhs")

# Match by partial package name
get_class_source(class_name="...", instance_id="xingin")

# Match by app display name (if available)
get_class_source(class_name="...", instance_id="小红书")

# Match by partial instance name
get_class_source(class_name="...", instance_id="xhs")
```

**Matching priority:** exact name → exact package → exact JADX name → exact app name → partial matches → file name → version.

> **Note:** Fuzzy matching only returns connected instances. Each instance loads a different app — there is no cross-instance fallback.

---

## Instance States

| Status | Description |
|:-------|:------------|
| `connected` | Healthy and ready for requests |
| `pending` | Registered but not yet connected (startup) |
| `disconnected` | Was connected but lost contact |
| `degraded` | Connected but low memory or OOM detected |
| `auth_failed` | JADX plugin returned 401 — check token config |
| `error` | Other error state |

---

## Use Cases

### Version Diff Analysis

```
1. Load app-v1.apk in instance "v1"
2. Load app-v2.apk in instance "v2"
3. Ask AI: "Compare MainActivity between v1 and v2"
```

### Team Workflow

```
Alice → jadx-1: Login module
Bob   → jadx-2: Payment module
Carol → jadx-3: Network layer
```

---

## Related

- [Docker Compose](../deployment/docker-compose.md)
- [Configuration Reference](../reference/configuration.md)
