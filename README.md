<div align="center">

# JADX-AI-MCP

> 🔱 **Fork of [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp)**

⚡ Let AI directly analyze Android APKs and Java JARs via JADX + MCP protocol.

![Latest release](https://img.shields.io/github/release/xjoker/jadx-ai-mcp.svg)
![Java 11+](https://img.shields.io/badge/Java-11%2B-blue)
![Python 3.10+](https://img.shields.io/badge/python-3%2E10%2B-blue)
[![License](http://img.shields.io/:license-apache-blue.svg)](http://www.apache.org/licenses/LICENSE-2.0.html)

**[简体中文](README.zh-cn.md)** | [📖 Documentation](docs/index.md) | [🚀 Quick Start](#-30-second-quick-start) | [🛠️ Tools](docs/reference/tools.md)

</div>

## 🌟 What Makes This Fork Different?

This fork provides **major enhancements** over the original project:

| Feature | Description |
|:--------|:------------|
| 🚀 **Smart Batch Optimization** | 4-tier strategy avoids 60-120s wasted decompilation. Auto-splits large responses (>8KB) with chunking. |
| 🔄 **Transfer API** | Bypass MCP's ~16KB limit via HTTP download. Tested with 322K classes. |
| 💼 **Full JVM Support** | APK, JAR, AAR, DEX all supported. 5 JAR-specific tools (manifest, entry points, dependencies, services, bytecode). |
| ⚡ **ClassCacheManager** | 10-50x faster repeated analysis with background caching and auto-invalidation. |
| 🐳 **All-in-One Docker** | One command deploys GUI + AI server. Multi-platform (amd64/arm64). |

> 📚 **44 bilingual guides** covering deployment, tools, troubleshooting, and AI testing prompts. [View details →](docs/reference/tools.md)

---

## ⚡ 30-Second Quick Start

```bash
# One command to start (GUI + AI)
docker run -d --name jadx -p 6080:6080 -p 8651:8651 -v ~/apks:/apks xjoker/jadx-ai-mcp:latest

# Open JADX GUI in browser
open http://localhost:6080
```

**That's it!** Put your APK or JAR in `~/apks/`, open it in JADX, and let AI analyze it.

<details>
<summary><strong>Other deployment scenarios</strong></summary>

**Headless Mode (AI only, no GUI):**
```bash
docker run -d --name jadx -p 8651:8651 -v ~/apks:/apks xjoker/jadx-ai-mcp:latest
```

**Multi-Container / Development (all ports):**
```bash
docker run -d --name jadx -p 6080:6080 -p 8650:8650 -p 8651:8651 -v ~/apks:/apks xjoker/jadx-ai-mcp:latest
```

</details>

> 💡 **Auto-load**: Place `target.jar`, `target.apk`, `target.aar`, or `target.dex` in `/apks` directory. JADX loads it automatically on startup. Priority: JAR > APK > AAR > DEX.

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

## 🧠 AI Skills

Install specialized analysis skills for Claude Code, Cursor, and other AI agents:

```bash
# Install all skills
npx skills add xjoker/jadx-ai-mcp

# Install specific skill
npx skills add xjoker/jadx-ai-mcp --skill logic-tracing
```

| Skill | Use Case |
|:------|:---------|
| **quickstart** | Getting started, performance optimization |
| **logic-tracing** | Understand call chains, API flows, feature implementation |
| **security-audit** | Vulnerability hunting, OWASP checks, risk analysis |
| **crypto-analysis** | Encryption algorithms, malware analysis, anti-debug |
| **frida-hooks** | Generate Frida scripts for dynamic instrumentation |
| **refactoring** | Rename obfuscated code, improve readability |

> Browse all skills at [skills.sh](https://skills.sh)

---

## 🚀 Deployment Options

| Method | Use Case | Guide |
|:-------|:---------|:------|
| **Docker** (Recommended) | Quick start, single user | [→ Docker Guide](docs/deployment/docker.md) |
| **Docker Compose** | Multi-instance, team use | [→ Compose Guide](docs/deployment/docker-compose.md) |
| **Local Installation** | Development, customization | [→ Local Guide](docs/deployment/local.md) |

### Port Reference

| Port | Service | Required? | Access From | Description |
|:----:|:--------|:---------:|:------------|:------------|
| **6080** | noVNC | Optional | Browser | JADX GUI web interface. Skip `-p 6080:6080` for headless mode. |
| **8650** | JADX Plugin API | No* | Container Internal | Internal HTTP API. Only expose for multi-container setup or debugging. |
| **8651** | MCP Server | **Yes** | AI Clients | **Main endpoint** for Claude, ChatGPT, etc. Always required. |

> **\* Port 8650** is only needed when running MCP Server in a separate container. For single-container deployment (default), MCP Server connects to JADX Plugin via internal `localhost:8650`.

### Deployment Commands by Scenario

<details open>
<summary><strong>🎯 Standard (GUI + AI + Cache) - Recommended</strong></summary>

```bash
docker run -d --name jadx \
  -p 6080:6080 -p 8651:8651 \
  -v ~/apks:/apks \
  -v jadx-cache:/root/.cache \
  xjoker/jadx-ai-mcp:latest
```

Access:
- JADX GUI: http://localhost:6080
- AI endpoint: http://localhost:8651/mcp

> 📦 Cache volume speeds up subsequent analysis by 10-50x.

</details>

<details>
<summary><strong>🤖 Headless (AI only, no GUI)</strong></summary>

```bash
docker run -d --name jadx \
  -p 8651:8651 \
  -v ~/apks:/apks \
  -v jadx-cache:/root/.cache \
  xjoker/jadx-ai-mcp:latest
```

Access:
- AI endpoint: http://localhost:8651/mcp

</details>

<details>
<summary><strong>🔧 Development / Multi-Container (all ports)</strong></summary>

```bash
docker run -d --name jadx \
  -p 6080:6080 -p 8650:8650 -p 8651:8651 \
  -v ~/apks:/apks \
  -v jadx-cache:/root/.cache \
  xjoker/jadx-ai-mcp:latest
```

Access:
- JADX GUI: http://localhost:6080
- JADX Plugin API: http://localhost:8650
- AI endpoint: http://localhost:8651/mcp

</details>

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
| [Tools Reference](docs/reference/tools.md) | Complete 45 MCP tools matrix |
| [Configuration](docs/reference/configuration.md) | All configuration options |
| [FAQ](docs/troubleshooting/faq.md) | Common issues and solutions |

### Other

| Document | Description |
|:---------|:------------|
| [Security](docs/security/security.md) | Authentication and permissions |
| [Changelog](docs/changelog/CHANGELOG.md) | Version history |

---

## 🛠️ MCP Tools Overview

**45 tools** for APK/JAR analysis:

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
