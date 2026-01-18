<div align="center">

# JADX-AI-MCP

> 🔱 **Fork of [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp)**  
> Adds multi-instance support, JAR analysis, and Docker deployment.

⚡ Let AI directly analyze Android APKs and Java JARs via JADX + MCP protocol.

![Latest release](https://img.shields.io/github/release/xjoker/jadx-ai-mcp.svg)
![Java 11+](https://img.shields.io/badge/Java-11%2B-blue)
![Python 3.10+](https://img.shields.io/badge/python-3%2E10%2B-blue)
[![License](http://img.shields.io/:license-apache-blue.svg)](http://www.apache.org/licenses/LICENSE-2.0.html)

[简体中文](docs/README.zh-cn.md) | [Full Documentation](docs/)

</div>

---

## 🤖 What is this?

**JADX-AI-MCP** enables Claude, ChatGPT, and other AI to **directly analyze Android APKs and Java JARs**.

| Capability | Example |
|:-----------|:--------|
| 🔍 **Code Search** | "Find all encryption-related classes" |
| 📖 **Code Reading** | "Explain the login method" |
| 🔗 **Reference Tracking** | "Who calls this API?" |
| 🛡️ **Security Audit** | "Check for hardcoded secrets" |
| ✏️ **Reverse Engineering** | "Rename obfuscated classes" |

### Supported File Types

| Type | Description |
|:-----|:------------|
| **APK** | Android apps |
| **JAR** | Java libraries, Spring Boot apps |
| **AAR** | Android libraries |
| **DEX** | Dalvik bytecode |

---

## 🚀 Quick Start

### Docker (Recommended ⭐)

```bash
# 1. Create workspace
mkdir -p ~/jadx-ai-mcp/apks && cd ~/jadx-ai-mcp

# 2. Run container
docker run -d --name jadx \
  -p 6080:6080 -p 8651:8651 \
  -v ~/jadx-ai-mcp/apks:/apks \
  xjoker/jadx-ai-mcp:latest

# 3. Put your APK/JAR in ~/jadx-ai-mcp/apks/
```

**Access:**
- 🌐 Browser: http://localhost:6080 (JADX Desktop)
- 📂 In JADX: File → Open → `/apks/your-app.apk`

> 💡 **Let AI guide you?** Send this to AI:
> ```
> Guide me through installing JADX-AI-MCP using: https://raw.githubusercontent.com/xjoker/jadx-ai-mcp/jadx-ai/docs/INSTALL_GUIDE.md
> ```

### Local Installation

```bash
# 1. Install JADX plugin
jadx plugins --install "github:xjoker:jadx-ai-mcp"

# 2. Install MCP Server
pip install "git+https://github.com/xjoker/jadx-ai-mcp#subdirectory=jadx-mcp-server"

# 3. Start
jadx-gui your-app.apk
jadx-mcp-server --transport streamable-http
```

---

## 📖 Documentation

| Document | Description |
|:---------|:------------|
| [Quick Start](docs/QUICK_START.md) | Docker setup guide |
| [Tools Reference](docs/TOOLS.md) | 51 MCP tools matrix |
| [详细中文文档](docs/README.zh-cn.md) | Full Chinese documentation |
| [Security](docs/SECURITY.md) | Authentication, permissions |
| [FAQ](docs/FAQ.md) | Troubleshooting |
| [Changelog](docs/CHANGELOG.md) | Version history |

---

## 🛠️ MCP Tools Overview

**51 tools** available for APK/JAR analysis:

| Category | Examples |
|:---------|:---------|
| **Code Analysis** | `get_class_source`, `get_method_by_name`, `get_class_info` |
| **Search** | `search_classes_by_keyword`, `search_native_methods` |
| **Cross-references** | `get_xrefs_to_class`, `get_xrefs_to_method` |
| **Batch Operations** | `batch_get_class_source`, `batch_get_xrefs` |
| **Android-specific** | `get_android_manifest`, `get_smali_of_class` |
| **JAR-specific** | `jar_get_manifest`, `jar_get_entry_points` |
| **Instance Management** | `list_jadx_instances`, `add_jadx_instance` |

> See [docs/TOOLS.md](docs/TOOLS.md) for complete matrix.

---

## 🙏 Credits

- Original project: [@zinja-coder](https://github.com/zinja-coder/jadx-ai-mcp)
- JADX decompiler: [skylot/jadx](https://github.com/skylot/jadx)

---

## 📜 License

Apache 2.0 - See [LICENSE](LICENSE)
