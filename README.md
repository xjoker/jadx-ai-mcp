<div align="center">

# JADX-AI-MCP (Part of Zin MCP Suite)

> 🔱 **This is a fork of [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp)**  
> Original project created by [@zinja-coder](https://github.com/zinja-coder). This fork adds multi-instance support and other enhancements.

⚡ Fully automated MCP server + JADX plugin built to communicate with LLM through MCP to analyze Android APKs using LLMs like Claude — uncover vulnerabilities, analyze APK, and reverse engineer effortlessly.

**👉 Original Project**: [github.com/zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp)

English | [简体中文](README_ZH.md)

![GitHub contributors JADX-AI-MCP](https://img.shields.io/github/contributors/xjoker/jadx-ai-mcp)
![GitHub contributors JADX-MCP-SERVER](https://img.shields.io/github/contributors/xjoker/jadx-ai-mcp)
![GitHub all releases](https://img.shields.io/github/downloads/xjoker/jadx-ai-mcp/total)
![GitHub release (latest by SemVer)](https://img.shields.io/github/downloads/xjoker/jadx-ai-mcp/latest/total)
![Latest release](https://img.shields.io/github/release/xjoker/jadx-ai-mcp.svg)
![Java 11+](https://img.shields.io/badge/Java-11%2B-blue)
![Python 3.10+](https://img.shields.io/badge/python-3%2E10%2B-blue)
[![License](http://img.shields.io/:license-apache-blue.svg)](http://www.apache.org/licenses/LICENSE-2.0.html)

#### ⭐ Contributors

Thanks to these wonderful people for their contributions ⭐
<table>
  <tr align="center">
    <td>
      <a href="https://github.com/badmonkey7">
        <img src="https://avatars.githubusercontent.com/u/41368882?v=4" width="30px;" alt=""/>
        <br /><sub><b>badmonkey7</b></sub>
      </a>
    </td>
       <td>
      <a href="https://github.com/tiann">
        <img src="https://avatars.githubusercontent.com/u/4233744?v=4" width="30px;" alt=""/>
        <br /><sub><b>tiann</b></sub>
      </a>
    </td>
    <td>
      <a href="https://github.com/ljt270864457">
        <img src="https://avatars.githubusercontent.com/u/8609890?v=4" width="30px;" alt=""/>
        <br /><sub><b>ljt270864457</b></sub>
      </a>
    </td>
    <td>
      <a href="https://github.com/ZERO-A-ONE">
        <img src="https://avatars.githubusercontent.com/u/18625356?v=4" width="30px;" alt=""/>
        <br /><sub><b>ZERO-A-ONE</b></sub>
      </a>
    </td>
    <td>
      <a href="https://github.com/neoz">
        <img src="https://avatars.githubusercontent.com/u/360582?v=4" width="30px;" alt=""/>
        <br /><sub><b>neoz</b></sub>
      </a>
    </td>
    <td>
      <a href="https://github.com/SamadiPour">
        <img src="https://avatars.githubusercontent.com/u/24422125?v=4" width="30px;" alt=""/>
        <br /><sub><b>SamadiPour</b></sub>
      </a>
    </td>
    <td>
      <a href="https://github.com/wuseluosi">
        <img src="https://avatars.githubusercontent.com/u/192840340?v=4" width="30px;" alt=""/>
        <br /><sub><b>wuseluosi</b></sub>
      </a>
    </td>
    <td>
      <a href="https://github.com/CainYzb">
        <img src="https://avatars.githubusercontent.com/u/50669073?v=4" width="30px;" alt=""/>
        <br /><sub><b>CainYzb</b></sub>
      </a>
    </td>
    <td>
      <a href="https://github.com/tbodt">
        <img src="https://avatars.githubusercontent.com/u/5678977?v=4" width="30px;" alt=""/>
        <br /><sub><b>tbodt</b></sub>
      </a>
    </td>
    <td>
      <a href="https://github.com/LilNick0101">
        <img src="https://avatars.githubusercontent.com/u/100995805?v=4" width="30px;" alt=""/>
        <br /><sub><b>LilNick0101</b></sub>
      </a>
    </td>
    <td>
      <a href="https://github.com/lwsinclair">
        <img src="https://avatars.githubusercontent.com/u/2829939?v=4" width="30px;" alt=""/>
        <br /><sub><b>lwsinclair</b></sub>
      </a>
    </td>
  </tr>
</table>



</div>

<!-- It is a still in early stage of development, so expects bugs, crashes and logical erros.-->

<!-- Standalone Plugin for [JADX](https://github.com/skylot/jadx) (Started as Fork) with Model Context Protocol (MCP) integration for AI-powered static code analysis and real-time code review and reverse engineering tasks using Claude.-->

---

## 🎯 Project Positioning

**JADX-AI-MCP** is a **bridge between JADX and AI/LLM via MCP protocol**.

**This is:**
- ✅ Enable Claude/ChatGPT to directly invoke JADX decompilation capabilities
- ✅ Support multi-instance, multi-user remote collaborative analysis
- ✅ Production-ready Docker deployment solution

**This is NOT:**
- ❌ A replacement for JADX GUI
- ❌ A production-grade security service (no audit logs, no fine-grained RBAC)
- ❌ A complete automated reverse engineering framework

> 📖 For security considerations, see [SECURITY.md](SECURITY.md)

---

## 🤖 What is JADX-AI-MCP?

**JADX-AI-MCP** is a plugin for the [JADX decompiler](https://github.com/skylot/jadx) that integrates directly with [Model Context Protocol (MCP)](https://github.com/anthropic/mcp) to provide **live reverse engineering support with LLMs like Claude**.

> 💡 This project was originally created by [@zinja-coder](https://github.com/zinja-coder). See the [original repository](https://github.com/zinja-coder/jadx-ai-mcp) for the upstream project.

Think: "Decompile → Context-Aware Code Review → AI Recommendations" — all in real time.

#### High Level Sequence Diagram

```mermaid
sequenceDiagram
LLM CLIENT->>JADX MCP SERVER: INVOKE MCP TOOL
JADX MCP SERVER->>JADX AI MCP PLUGIN: INVOKE HTTP REQUEST
JADX AI MCP PLUGIN->>REQUEST HANDLERS: INVOKE HTTP REQUEST HANDLER
REQUEST HANDLERS->>JADX GUI: PERFORM ACTION/GATHER DATA
JADX GUI->>REQUEST HANDLERS: ACTION PERFORMED/DATA GATHERED
REQUEST HANDLERS->>JADX AI MCP PLUGIN: CRAFT HTTP RESPONSE
JADX AI MCP PLUGIN->>JADX MCP SERVER:HTTP RESPONSE
JADX MCP SERVER->>LLM CLIENT: MCP TOOL RESULT
```


It is combination of two tools:
1. JADX-AI-MCP
2. [JADX MCP SERVER](https://github.com/zinja-coder/jadx-mcp-server)

## 🤖 What is JADX-MCP-SERVER?

**JADX MCP Server** is a standalone Python server that interacts with a `JADX-AI-MCP` plugin (see: [jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp)) via MCP (Model Context Protocol). It lets LLMs communicate with the decompiled Android app context live.

---

## Other projects in Zin MCP Suite
 - **[APKTool-MCP-Server](https://github.com/zinja-coder/apktool-mcp-server)**
 - **[JADX-MCP-Server](https://github.com/zinja-coder/jadx-mcp-server)**
 - **[ZIN-MCP-Client](https://github.com/zinja-coder/zin-mcp-client)**

## Current MCP Tools

The following MCP tools are available. **All tools support an optional `instance_id` parameter for multi-instance targeting.**

### Code Analysis Tools
- `fetch_current_class(instance_id?)` — Get the class name and full source of selected class
- `get_selected_text(instance_id?)` — Get currently selected text
- `get_all_classes(offset=0, count=0, instance_id?)` — List all classes in the project (paginated)
- `get_class_source(class_name, instance_id?)` — Get full source of a given class
- `batch_get_class_source(class_names, instance_id?)` — **Batch retrieve multiple class sources (max 20)**
- `get_class_info(class_name, instance_id?)` — **Get class structure (inheritance, interfaces, member counts)**
- `get_method_by_name(class_name, method_name, instance_id?)` — Fetch a method's source
- `batch_get_method_by_name(methods, instance_id?)` — **Batch retrieve multiple methods (format: class:method, max 20)**
- `get_method_signature(class_name, method_name, instance_id?)` — **Get structured method signature (return type, params)**
- `get_method_callees(class_name, method_name, instance_id?)` — **Get methods called by this method**
- `search_method_by_name(method_name, offset=0, count=50, instance_id?)` — Search method across classes (paginated)
- `search_classes_by_keyword(search_term, package="", exclude="", search_in="code", offset=0, count=20, instance_id?)` — Search with optional exclusion filter
- `get_methods_of_class(class_name, instance_id?)` — List methods in a class
- `get_fields_of_class(class_name, instance_id?)` — List fields in a class
- `get_smali_of_class(class_name, instance_id?)` — Fetch smali of class
- `get_main_activity_class(instance_id?)` — Fetch main activity from AndroidManifest.xml
- `get_main_application_classes_code(offset=0, count=0, instance_id?)` — Fetch main application classes' code
- `get_main_application_classes_names(instance_id?)` — Fetch main application classes' names

### Resource Tools
- `get_android_manifest(instance_id?)` — Retrieve AndroidManifest.xml content
- `get_strings(mode="summary", query?, key?, locale="values", offset=0, limit=50, instance_id?)` — **AI-friendly string analysis** (modes: summary, list, search, get)
- `get_all_resource_file_names(offset=0, count=0, instance_id?)` — List all resource file names
- `get_resource_file(resource_name, instance_id?)` — Retrieve resource file content

### Refactoring Tools
- `rename_class(class_name, new_name, instance_id?)` — Rename a class
- `rename_method(method_name, new_name, instance_id?)` — Rename a method
- `rename_field(class_name, field_name, new_name, instance_id?)` — Rename a field
- `rename_package(old_name, new_name, instance_id?)` — Rename a package

### Debug Tools
- `debug_get_stack_frames(instance_id?)` — Get stack frames from debugger
- `debug_get_threads(instance_id?)` — Get thread information from debugger
- `debug_get_variables(instance_id?)` — Get variables from debugger

### Cross-Reference Tools
- `get_xrefs_to_class(class_name, offset=0, count=20, instance_id?)` — Find all references to a class
- `get_xrefs_to_method(class_name, method_name, offset=0, count=20, instance_id?)` — Find all references to a method
- `get_xrefs_to_field(class_name, field_name, offset=0, count=20, instance_id?)` — Find all references to a field
- `batch_get_xrefs(targets, instance_id?)` — **Batch query xrefs for multiple targets (max 10)** (targets: list of "type:class:member")

### Multi-Instance Management Tools
- `list_jadx_instances()` — List all connected JADX instances
- `add_jadx_instance(host, port, name?, token?)` — Add a new JADX instance dynamically
- `remove_jadx_instance(name)` — Remove a JADX instance
- `set_default_jadx_instance(name)` — Set the default instance for tool calls
- `get_jadx_instance_info(name)` — Get detailed info about an instance
- `health_check_jadx_instances()` — Check health of all instances
- `check_instance_status(instance_name?)` — **Check if instance is busy processing**
- `clear_class_cache(instance_id?)` — **Clear ClassCacheManager cache (30s global cooldown)**

---

## 🧭 MCP Prompts (AI Guidance)

Built-in prompts to guide AI for effective reverse engineering workflows:

| Prompt | Description |
|--------|-------------|
| `analyze-activity` | Step-by-step guide for analyzing Android Activities from Manifest |
| `search-code` | Efficient code search strategy to avoid timeouts on large APKs |
| `trace-method` | Method tracing workflow: implementation → callers → callees |
| `warm-up-package` | Pre-warm decompilation cache for faster subsequent analysis |
| `batch-operations` | Best practices for batch operations to reduce overhead |

**Usage Example:**

```
Use the analyze-activity prompt to analyze MainActivity
```

---

## 🗒️ Sample Prompts

🔍 Basic Code Understanding

    "Explain what this class does in one paragraph."

    "Summarize the responsibilities of this method."

    "Is there any obfuscation in this class?"

    "List all Android permissions this class might require."

🛡️ Vulnerability Detection

    "Are there any insecure API usages in this method?"

    "Check this class for hardcoded secrets or credentials."

    "Does this method sanitize user input before using it?"

    "What security vulnerabilities might be introduced by this code?"

🛠️ Reverse Engineering Helpers

    "Deobfuscate and rename the classes and methods to something readable."

    "Can you infer the original purpose of this smali method?"

    "What libraries or SDKs does this class appear to be part of?"

    "Tell me which classes contains code related to 'encryption'?"

📦 Static Analysis

    "List all network-related API calls in this class."

    "Identify file I/O operations and their potential risks."

    "Does this method leak device info or PII?"

🤖 AI Code Modification

    "Refactor this method to improve readability."

    "Add comments to this code explaining each step."

    "Rewrite this Java method in Python for analysis."

📄 Documentation & Metadata

    "Generate Javadoc-style comments for all methods."

    "What package or app component does this class likely belong to?"

    "Can you identify the Android component type (Activity, Service, etc.)?"

🐞 Debugger Assistant
```
   "Fetch stack frames, varirables and threads from debugger and provide summary"

   "Based the stack frames from debugger, explain the execution flow of the application"

   "Based on the state of variables, is there security threat?"
```

---

## 🚀 Quick Start

### Architecture Overview

```mermaid
flowchart TB
    subgraph LLM["LLM Clients"]
        Claude["Claude Desktop"]
        Cursor["Cursor / Other MCP Clients"]
    end
    
    subgraph MCP["MCP Server (Python)"]
        Server["jadx-mcp-server :8651"]
        Auth["Multi-User Auth"]
        Registry["Instance Registry"]
    end
    
    subgraph JADX["JADX Instances"]
        J1["JADX #1 :8650<br/>app-v1.apk"]
        J2["JADX #2 :8651<br/>app-v2.apk"]
        J3["JADX #3 :8652<br/>dev.apk"]
    end
    
    Claude --> |HTTP/MCP| Server
    Cursor --> |HTTP/MCP| Server
    Server --> Auth
    Auth --> Registry
    Registry --> J1
    Registry --> J2
    Registry --> J3
```

### Step 1: Install JADX Plugin

```bash
jadx plugins --install "github:xjoker:jadx-ai-mcp"
```

### Step 2: Start MCP Server

**Option A: Docker (Recommended)**

```bash
# All-in-One: JADX GUI + MCP Server
docker run -d -p 6080:6080 -p 8651:8651 xjoker/jadx-ai-mcp:latest

# Standalone MCP Server only
docker run -d -p 8651:8651 xjoker/jadx-mcp-server:latest
```

**Option B: Local Installation**

```bash
# 1. Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install MCP Server
uv tool install "git+https://github.com/xjoker/jadx-ai-mcp#subdirectory=jadx-mcp-server"

# 3. Run MCP Server (choose one)

# Simple mode - connect to local JADX
jadx_mcp_server --http --host 0.0.0.0 --port 8651

# With specific JADX instance
jadx_mcp_server --http --host 0.0.0.0 --jadx-host 192.168.1.10 --jadx-port 8650

# With config file
jadx_mcp_server --http --config jadx-config.toml

# Multi-instance mode
jadx_mcp_server --http --jadx-instances "192.168.1.10:8650:app-v1,192.168.1.11:8650:app-v2"
```

**Environment Variables:**

| Variable | Description |
|----------|-------------|
| `JADX_HOST` | JADX plugin host (default: 127.0.0.1) |
| `JADX_PORT` | JADX plugin port (default: 8650) |
| `JADX_MCP_AUTH_TOKEN` | Authentication token for JADX plugin |
| `JADX_MCP_SERVER_PORT` | MCP server port (default: 8651) |
| `JADX_MCP_BIND_ADDRESS` | Plugin bind address (default: 127.0.0.1, use 0.0.0.0 for Docker) |

### Step 3: Connect LLM Client

```bash
# Claude CLI - Connect to HTTP MCP Server
claude mcp add --transport http jadx http://localhost:8651/mcp
```

Or configure `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jadx": {
      "type": "http",
      "url": "http://localhost:8651/mcp"
    }
  }
}
```

---

## 📦 Docker Deployment

Two Docker images are available:

| Image | Description | Size | Use Case |
|-------|-------------|------|----------|
| `xjoker/jadx-ai-mcp` | JADX GUI + noVNC + MCP Server | ~800MB | Quick start, single APK |
| `xjoker/jadx-mcp-server` | MCP Server only | ~100MB | Production, multi-instance |

### 🚀 Docker Compose (推荐)

**一键启动 1 MCP + 3 JADX 多实例环境：**

```bash
cd docker
docker compose up -d
```

**访问地址：**

| 服务 | 地址 | 说明 |
|:-----|:-----|:-----|
| MCP Server | http://localhost:8651/mcp | 连接 Claude/LLM |
| JADX #1 | http://localhost:6080 | noVNC 桌面 |
| JADX #2 | http://localhost:6081 | noVNC 桌面 |
| JADX #3 | http://localhost:6082 | noVNC 桌面 |

**自动加载 APK：**

将 APK 文件命名为 `target.apk` 放入对应目录，JADX 启动时会自动加载：

```bash
docker/apks/jadx-1/target.apk  → JADX #1 自动打开
docker/apks/jadx-2/target.apk  → JADX #2 自动打开
docker/apks/jadx-3/target.apk  → JADX #3 自动打开
```

**使用场景：**
- 比较 APP 不同版本：在 JADX #1 和 #2 分别打开 v1 和 v2，让 AI 比较差异
- 团队协作分析：不同成员使用不同实例分析不同模块

> 📖 详细使用说明见 [docker/QUICK_START.md](docker/QUICK_START.md)

### All-in-One Container

**Basic Usage:**

```bash
docker run -d --name jadx \
  -p 6080:6080 \
  -p 8650:8650 \
  -p 8651:8651 \
  -v $(pwd)/apks:/apks \
  xjoker/jadx-ai-mcp:latest
```

**With Cache and Config (Recommended):**

```bash
docker run -d --name jadx \
  -p 6080:6080 \
  -p 8650:8650 \
  -p 8651:8651 \
  -v $(pwd)/apks:/apks \
  -v $(pwd)/config:/app/data/config \
  -v jadx-cache:/root/.cache \
  -v jadx-gui-cache:/root/.jadx-gui \
  xjoker/jadx-ai-mcp:latest
```

**Access:**
- 🌐 **noVNC Desktop**: http://localhost:6080
- 🔌 **Plugin API**: http://localhost:8650
- 🤖 **MCP Server**: http://localhost:8651

### Volume Reference

| Volume | Path | Purpose |
|--------|------|---------|
| APK Files | `/apks` | Mount APK files for analysis |
| Config | `/app/data/config` | Configuration files (jadx-config.toml) |
| Cache | `/root/.cache` | JADX decompilation cache (10-50x faster) |
| GUI Settings | `/root/.jadx-gui` | GUI preferences persistence |

> **Tip**: First code search on a large APK triggers decompilation (slow). Subsequent searches are fast due to cache.

### Standalone MCP Server

For production environments connecting to external JADX instances:

**Option 1: With Config File**

```bash
# Create config directory and file
mkdir -p config
cat > config/jadx-config.toml << 'EOF'
[server]
host = "0.0.0.0"
port = 8651

[[jadx_instances]]
name = "jadx-1"
host = "192.168.1.10"
port = 8650
enabled = true
EOF

# Run with config
docker run -d --name mcp-server \
  -p 8651:8651 \
  -v $(pwd)/config:/app/data/config \
  xjoker/jadx-mcp-server:latest
```

**Option 2: With Environment Variables**

```bash
docker run -d --name mcp-server \
  -p 8651:8651 \
  -e JADX_HOST=192.168.1.10 \
  -e JADX_PORT=8650 \
  -e JADX_MCP_AUTH_TOKEN=your-token \
  xjoker/jadx-mcp-server:latest
```

**Option 3: CLI Arguments**

```bash
docker run -d --name mcp-server \
  -p 8651:8651 \
  xjoker/jadx-mcp-server:latest \
  jadx_mcp_server --http --host 0.0.0.0 \
    --jadx-instances "192.168.1.10:8650:app-v1,192.168.1.11:8650:app-v2"
```

---

## 🚦 Search Behavior

### Concurrent Search Handling

Search operations use a **serialized lock** to prevent JADX internal state conflicts:

| Scenario | Response | AI Action |
|----------|----------|-----------|
| Search available | `200 OK` + results | Process normally |
| Search busy | `200 OK` + `{"error": "INSTANCE_BUSY", ...}` | Wait and retry (default timeout 300s) |

**Why serialization?**
- JADX decompilation is not thread-safe
- Concurrent code searches can cause inconsistent results
- Lock ensures correctness over speed

### Search Mode Performance

| Mode | Speed | Triggers Decompilation |
|------|-------|------------------------|
| `search_in="class"` | Fast | No |
| `search_in="method"` | Fast | No |
| `search_in="field"` | Fast | No |
| `search_in="code"` | Slow | Yes (once per class) |

> **Best Practice**: Start with `class`/`method`/`field` searches. Use `search_in="code"` with package filter for targeted full-text search.

---

## 🗂️ Class Cache & Auto-Invalidation

For performance, batch operations (`batch_get_class_source`, `batch_get_method_by_name`, `batch_get_xrefs`) use **ClassCacheManager**:

| Feature | Description |
|---------|-------------|
| **Lazy Loading** | Cache is populated on first batch call. May return `LOADING` status initially. |
| **Auto-Invalidation** | Any rename operation (`rename_class`, `rename_method`, `rename_field`, `rename_package`) automatically clears the cache. |
| **30s Global Cooldown** | Cache clear operations are debounced with a 30-second cooldown to prevent excessive reloading. |

> **Note**: Use `clear_class_cache()` to manually clear if you suspect stale data after JADX-side modifications.

---

## ⚡ Tool Performance Tips

Some tools may timeout on large APKs. Use these best practices:

| Tool | Warning | Recommendation |
|:-----|:--------|:---------------|
| `get_class_source` | Very large classes (R.class with 10000+ fields) may timeout | Use `get_method_by_name` for specific methods |
| `batch_get_class_source` | Include large classes may cause timeout | Use `get_class_info` first to check size |
| `get_main_application_classes_code` | `count=0` (all) may timeout | Use `count=1-5` for pagination |
| `get_resource_file` | Obfuscated APKs may have renamed resources | Use `get_all_resource_file_names` first |
| `search_classes_by_keyword` | `search_in="code"` is slow | Prefer `search_in="class"` or `"method"` |

---

## ⚙️ Configuration File

Create `jadx-config.toml` for advanced configuration:

### Complete Configuration Reference

```toml
# =============================================================================
# Server Configuration
# =============================================================================
[server]
host = "0.0.0.0"          # Bind address (0.0.0.0 for Docker)
port = 8651               # MCP Server port

# =============================================================================
# Default Settings
# =============================================================================
[defaults]
request_timeout = 120     # HTTP request timeout (seconds)
busy_timeout = 300        # Max busy wait time (seconds)
jadx_token = ""           # Default JADX plugin auth token (or set JADX_MCP_AUTH_TOKEN env var)
health_check_interval = 30  # Background health check interval (seconds)

# =============================================================================
# Security Settings
# =============================================================================
[security]
allow_dynamic_instances = false  # Allow users to add instances via AI commands

# =============================================================================
# Multi-User Authentication
# =============================================================================
# Each user gets a unique token for MCP client authentication
# Dynamic instances created by a user are only visible to that user

[[users]]
name = "alice"
token = "token-alice-xxxxx"

[[users]]
name = "bob"
token = "token-bob-yyyyy"

[[users]]
name = "admin"
token = "token-admin-zzzzz"
is_admin = true           # Admin can see all users' instances
can_add_instances = true  # Explicitly grant instance addition permission

# =============================================================================
# Pre-configured JADX Instances
# =============================================================================
# These instances are shared and visible to all users

[[jadx_instances]]
name = "app-v1"
host = "192.168.1.10"
port = 8650
enabled = true
token = ""                # Instance-specific token (optional)

[[jadx_instances]]
name = "app-v2"
host = "192.168.1.11"
port = 8650
enabled = true

[[jadx_instances]]
name = "local-dev"
host = "127.0.0.1"
port = 8650
enabled = false           # Disabled, won't connect
```

### Configuration Options Explained

```mermaid
flowchart LR
    subgraph Config["jadx-config.toml"]
        Server["[server]<br/>host, port"]
        Defaults["[defaults]<br/>timeouts, jadx_token"]
        Users["[[users]]<br/>name, token, is_admin"]
        Instances["[[jadx_instances]]<br/>name, host, port, enabled"]
    end
    
    Server --> |"MCP Server binds to"| Bind["0.0.0.0:8651"]
    Users --> |"Controls access"| Auth["User Authentication"]
    Instances --> |"Pre-connects to"| JADX["JADX Plugin Servers"]
    Defaults --> |"Applied to all"| Conn["Connections"]
```

**`[server]`** - Server binding

| Key | Description |
|-----|-------------|
| `host` | MCP Server bind address |
| `port` | MCP Server port |

**`[defaults]`** - Default settings

| Key | Description |
|-----|-------------|
| `request_timeout` | HTTP timeout for JADX requests |
| `busy_timeout` | Max busy wait time for instance lock |
| `jadx_token` | Default auth token for JADX plugins |
| `health_check_interval` | Background health check interval (seconds) |

**`[security]`** - Security options

| Key | Description |
|-----|-------------|
| `allow_dynamic_instances` | Allow users to add instances via AI |

**`[[users]]`** - User authentication (repeatable)

| Key | Description |
|-----|-------------|
| `name` | Username for identification |
| `token` | Bearer token for MCP client auth |
| `is_admin` | Can see all users' dynamic instances |
| `can_add_instances` | Override permission to add instances |

**`[[jadx_instances]]`** - Pre-configured instances (repeatable)

| Key | Description |
|-----|-------------|
| `name` | Instance identifier |
| `host` | JADX plugin IP address |
| `port` | JADX plugin port |
| `enabled` | Whether to connect on startup |

---

## 🔗 Multi-Instance Management

### Why Multiple Instances?

```mermaid
flowchart TB
    subgraph Use Cases
        UC1["Compare app versions<br/>v1 vs v2"]
        UC2["Team collaboration<br/>Different targets"]
        UC3["A/B security testing"]
    end
    
    subgraph MCP Server
        Registry["Instance Registry"]
    end
    
    subgraph Instances
        I1["app-v1.apk<br/>192.168.1.10:8650"]
        I2["app-v2.apk<br/>192.168.1.11:8650"]
        I3["dev-build.apk<br/>localhost:8652"]
    end
    
    UC1 --> Registry
    UC2 --> Registry
    UC3 --> Registry
    Registry --> I1
    Registry --> I2
    Registry --> I3
```

### Connect via Configuration

```toml
[[jadx_instances]]
name = "xhs-v8"
host = "192.168.1.10"
port = 8650

[[jadx_instances]]
name = "xhs-v9"
host = "192.168.1.11"
port = 8650
```

### Connect via AI Command

```
Please connect to JADX at 192.168.1.100:8650, name it "my-app"

Or multiple:
Connect to these JADX instances:
1. 192.168.1.10:8650 as "app-v1"
2. 192.168.1.11:8650 as "app-v2"
```

### Target Specific Instance

All MCP tools support `instance_id` parameter:

```
Get the MainActivity from app-v1

Compare the encryption methods between app-v1 and app-v2

Check if the vulnerability in v1 was fixed in v2
```

---

## 🔐 Authentication

### Authentication Flow

```mermaid
sequenceDiagram
    participant Client as LLM Client
    participant MCP as MCP Server
    participant JADX as JADX Plugin
    
    Client->>MCP: Request + Bearer Token
    MCP->>MCP: Validate User Token
    MCP->>JADX: Request + JADX Token
    JADX->>MCP: Response
    MCP->>Client: MCP Tool Result
```

### User Isolation & Permissions

**Instance Visibility Rules:**

| User Type | Config Instances | Own Dynamic Instances | Others' Dynamic |
|:----------|:----------------:|:---------------------:|:---------------:|
| Regular User | ✅ See | ✅ See / Delete | ❌ Hidden |
| Admin (`is_admin: true`) | ✅ See | ✅ See / Delete | ✅ See / Delete |

**Admin Privileges (`is_admin: true`):**
- View all instances (including dynamic instances created by other users)
- Remove any user's dynamic instances
- Set any instance as default
- Access all MCP tools without owner restrictions

### Dynamic Instance Creation

**`security.allow_dynamic_instances` Logic:**

```mermaid
flowchart TD
    A["AI calls add_jadx_instance(host, port, name?)"] --> B{"User is admin?<br/>(is_admin: true)"}
    B -->|YES| C["✅ ALLOW<br/>(admin bypass)"]
    B -->|NO| D{"User has<br/>can_add_instances: true?"}
    D -->|YES| E["✅ ALLOW"]
    D -->|NO| F{"Global<br/>allow_dynamic_instances: true?"}
    F -->|YES| G["✅ ALLOW"]
    F -->|NO| H["❌ DENY<br/>(PERMISSION_DENIED)"]
    
    style C fill:#90EE90
    style E fill:#90EE90
    style G fill:#90EE90
    style H fill:#FFB6C1
```

**Enable Dynamic Instances:**

```toml
# Option 1: Enable for all users
[security]
allow_dynamic_instances = true

# Option 2: Grant to specific user
[[users]]
name = "alice"
token = "token-alice-xxxxx"
can_add_instances = true  # Override global setting
```

### AI Instance Management Commands

**Add Instance:**
```
Connect to JADX at 192.168.1.100:8650
# → add_jadx_instance(host="192.168.1.100", port=8650)

Connect to JADX at 10.0.0.5:8650 and name it "payment-module"
# → add_jadx_instance(host="10.0.0.5", port=8650, name="payment-module")
```

**List Instances:**
```
List all JADX instances
# → list_jadx_instances() — returns visible instances based on user permissions
```

**Remove Instance:**
```
Remove the payment-module instance
# → remove_jadx_instance(name="payment-module")
# Owner or admin required
```

**Set Default:**
```
Set xhs-v9 as the default instance
# → set_default_jadx_instance(name="xhs-v9")
```

### Connect with Authentication

```bash
# Claude CLI with Bearer token
claude mcp add --transport http jadx http://server:8651/mcp \
  --header "Authorization: Bearer token-alice-xxxxx"
```

```json
// claude_desktop_config.json
{
  "mcpServers": {
    "jadx": {
      "type": "http",
      "url": "http://server:8651/mcp",
      "headers": {
        "Authorization": "Bearer token-alice-xxxxx"
      }
    }
  }
}
```

---

## 🛠️ Command Line Reference

```bash
jadx_mcp_server [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--config FILE` | None | TOML configuration file path |
| `--http` | False | Enable HTTP mode (required for remote) |
| `--host HOST` | 127.0.0.1 | MCP Server bind address |
| `--port PORT` | 8651 | MCP Server port |
| `--jadx-host HOST` | 127.0.0.1 | Single JADX instance host |
| `--jadx-port PORT` | 8650 | Single JADX instance port |
| `--jadx-instances LIST` | None | Multiple instances: `host:port:name,...` |
| `--auth-token TOKEN` | None | JADX plugin auth token |
| `--mcp-auth-token TOKEN` | None | MCP server auth token (single user) |

### Examples

```bash
# Simple local setup
jadx_mcp_server

# HTTP mode for remote access
jadx_mcp_server --http --host 0.0.0.0

# With configuration file
jadx_mcp_server --http --config jadx-config.toml

# Multiple instances via CLI
jadx_mcp_server --http --jadx-instances "192.168.1.10:8650:v1,192.168.1.11:8650:v2"
```

---

## 🔌 JADX Plugin Settings

In JADX GUI: `Plugins → JADX AI MCP Server → 设置...`

| Setting | Description |
|---------|-------------|
| **Port** | Plugin HTTP API port (default: 8650) |
| **Bind Address** | Use `0.0.0.0` for network access |
| **Auto Start** | Start server when JADX opens |
| **Auth Token** | Token for MCP Server authentication |

---

## Troubleshooting

If you encounter issues:
1. Ensure JADX GUI is running with an APK loaded
2. Verify the plugin is installed and enabled
3. Check that the MCP server is running
4. If using authentication, ensure tokens match
5. For network issues, verify firewall settings

---

## 🙏 Credits

This project is a plugin for JADX, an amazing open-source Android decompiler created and maintained by [@skylot](https://github.com/skylot). This project is a fork of [jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp) created by [zinja-coder](https://github.com/zinja-coder). Huge thanks for their original work!

[📎 Original README (JADX)](https://github.com/skylot/jadx)

### Dependencies

- Plugin - Java
  - Javalin     - https://javalin.io/ - Apache 2.0 License
  - SLF4J       - https://slf4j.org/  - MIT License

- MCP Server - Python
  - FastMCP - https://github.com/jlowin/fastmcp - Apache 2.0 License
  - httpx   - https://www.python-httpx.org      - BSD-3-Clause

## 📄 License

JADX-AI-MCP inherits the Apache 2.0 License from the original JADX repository.

## ⚖️ Legal Warning

The tools `jadx-ai-mcp` and `jadx_mcp_server` are intended strictly for educational, research, and ethical security assessment purposes. Users are solely responsible for ensuring compliance with all applicable laws.

---

## 🙌 Contribute or Support

- Found it useful? Give it a ⭐️
- Got ideas? Open an [issue](https://github.com/xjoker/jadx-ai-mcp/issues) or submit a PR

---

Built with ❤️ for the reverse engineering and AI communities.
