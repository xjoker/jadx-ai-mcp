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
# Query specific instance
get_class_source(class_name="com.example.Main", instance_id="app-v2")

# Compare across instances
source_v1 = get_class_source(class_name="com.example.Main", instance_id="app-v1")
source_v2 = get_class_source(class_name="com.example.Main", instance_id="app-v2")
```

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
