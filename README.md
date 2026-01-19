<div align="center">

# JADX-AI-MCP

> 🔱 **Fork of [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp)**

⚡ Let AI directly analyze Android APKs and Java JARs via JADX + MCP protocol.

![Latest release](https://img.shields.io/github/release/xjoker/jadx-ai-mcp.svg)
![Java 11+](https://img.shields.io/badge/Java-11%2B-blue)
![Python 3.10+](https://img.shields.io/badge/python-3%2E10%2B-blue)
[![License](http://img.shields.io/:license-apache-blue.svg)](http://www.apache.org/licenses/LICENSE-2.0.html)

[📖 Full Documentation](docs/index.md) | [简体中文](README.zh-cn.md)

</div>

---

## ⚡ 30-Second Quick Start

```bash
# One command to start
docker run -d --name jadx -p 6080:6080 -p 8651:8651 -v ~/apks:/apks xjoker/jadx-ai-mcp:latest

# Open in browser
open http://localhost:6080
```

**That's it!** Put your APK or JAR in `~/apks/`, open it in JADX, and let AI analyze it.

> 💡 **Auto-load**: Name your file `target.apk` (or `target.jar`) and JADX will load it automatically on startup.

<details>
<summary>💡 <strong>Let AI guide your installation?</strong></summary>

Send this to Claude/ChatGPT:

```
Guide me through installing JADX-AI-MCP step by step using this document:
https://raw.githubusercontent.com/xjoker/jadx-ai-mcp/jadx-ai/docs/getting-started/installation.md

Rules:
1. Ask me one question at a time, wait for my response before proceeding
2. Only use commands from the document, do not invent new ones
3. After each step, ask me to paste the output before continuing
4. If something fails, help me troubleshoot before moving on
```

> **If AI cannot access URLs**: Copy the content from [installation.md](docs/getting-started/installation.md) and paste it directly into the chat.
</details>

---

## 🤖 What is this?

**JADX-AI-MCP** enables Claude, ChatGPT, and other AI to **directly analyze Android APKs and Java JARs**.

| Capability | Example |
|:-----------|:--------|
| 🔍 **Code Search** | "Find all encryption-related classes" |
| 📖 **Code Reading** | "Explain the login method" |
| 🔗 **Reference Tracking** | "Who calls this API?" |
| 🛡️ **Security Audit** | "Check for hardcoded secrets" |

### Supported File Types

| Type | Description |
|:-----|:------------|
| **APK** | Android apps |
| **JAR** | Java libraries, Spring Boot apps |
| **AAR** | Android libraries |
| **DEX** | Dalvik bytecode |

---

## 🚀 Deployment Options

| Method | Use Case | Guide |
|:-------|:---------|:------|
| **Docker** (Recommended) | Quick start, single user | [→ Docker Guide](docs/deployment/docker.md) |
| **Docker Compose** | Multi-instance, team use | [→ Compose Guide](docs/deployment/docker-compose.md) |
| **Local Installation** | Development, customization | [→ Local Guide](docs/deployment/local.md) |

### Port Reference

| Port | Service | Description |
|:----:|:--------|:------------|
| **6080** | noVNC | JADX GUI web access |
| **8650** | JADX Plugin | Internal API |
| **8651** | MCP Server | AI client connection |

### Recommended Docker Command (with cache)

```bash
docker run -d --name jadx \
  -p 6080:6080 -p 8651:8651 \
  -v ~/apks:/apks \
  -v jadx-cache:/root/.cache \
  xjoker/jadx-ai-mcp:latest
```

> 📦 The cache volume speeds up subsequent analysis significantly.

---

## 📖 Documentation

### Getting Started

| Document | Description |
|:---------|:------------|
| [Quick Start](docs/getting-started/quickstart.md) | 5-minute Docker setup |
| [Installation Guide](docs/getting-started/installation.md) | Detailed installation for all platforms |

### Reference

| Document | Description |
|:---------|:------------|
| [Tools Reference](docs/reference/tools.md) | Complete 51 MCP tools matrix |
| [Configuration](docs/reference/configuration.md) | All configuration options |
| [FAQ](docs/troubleshooting/faq.md) | Common issues and solutions |

### Other

| Document | Description |
|:---------|:------------|
| [Security](docs/security/security.md) | Authentication and permissions |
| [Changelog](docs/changelog/CHANGELOG.md) | Version history |

---

## 🛠️ MCP Tools Overview

**51 tools** for APK/JAR analysis:

| Category | Tools |
|:---------|:------|
| **Code Analysis** | `get_class_source`, `get_method_by_name`, `get_class_info` |
| **Search** | `search_classes_by_keyword`, `search_native_methods` |
| **Cross-references** | `get_xrefs_to_class`, `get_xrefs_to_method` |
| **Batch** | `batch_get_class_source`, `batch_get_xrefs` |
| **Android** | `get_android_manifest`, `get_smali_of_class` |
| **JAR** | `jar_get_manifest`, `jar_get_entry_points` |
| **Instance** | `list_jadx_instances`, `add_jadx_instance` |

> See [Tools Reference](docs/reference/tools.md) for the complete matrix.

---

## 🙏 Credits

- Original project: [@zinja-coder](https://github.com/zinja-coder/jadx-ai-mcp)
- JADX decompiler: [skylot/jadx](https://github.com/skylot/jadx)

---

## 📜 License

Apache 2.0 - See [LICENSE](LICENSE)
