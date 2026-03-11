<div align="center">

# JADX-AI-MCP

> 🔱 **Fork of [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp)**

⚡ Let AI directly analyze Android APKs and Java JARs via JADX + MCP protocol.

![Latest release](https://img.shields.io/github/release/xjoker/jadx-ai-mcp.svg)
![Java 11+](https://img.shields.io/badge/Java-11%2B-blue)
![Python 3.10+](https://img.shields.io/badge/python-3%2E10%2B-blue)
[![License](http://img.shields.io/:license-apache-blue.svg)](http://www.apache.org/licenses/LICENSE-2.0.html)

**[简体中文](README.zh-cn.md)** | [📖 Documentation](docs/index.md)

</div>

---

> Versioning note: source files keep development placeholder versions. GitHub Actions injects the release version into build artifacts, `pom.xml`, the Java banner, and the Python server banner during release builds.

## 🌟 What Makes This Fork Different?

This fork provides **major enhancements** over the original project:

| Feature | Description |
|:--------|:------------|
| 🚀 **Smart Batch Optimization** | 4-tier strategy avoids 60-120s wasted decompilation. Auto-chunks large responses (>8KB). |
| 🔄 **Transfer API** | Bypass MCP's ~16KB limit via HTTP download. Tested with 322K classes. |
| 💼 **Full JVM Support** | APK, JAR, AAR, DEX all supported. 5 JAR-specific tools (manifest, entry points, dependencies, services, bytecode). |
| ⚡ **ClassCacheManager** | 10-50x faster repeated analysis with background caching and auto-invalidation. |
| 🐳 **All-in-One Docker** | One command deploys GUI + AI server. Multi-platform (amd64/arm64). |

> 📚 **44 bilingual guides** covering deployment, tools, troubleshooting, and AI testing prompts.

---

## ⚡ 30-Second Quick Start

```bash
# One command to start (GUI + AI)
docker run -d --name jadx -p 6080:6080 -p 8651:8651 -v ~/apks:/apks xjoker/jadx-ai-mcp:latest

# Open JADX GUI in browser
open http://localhost:6080
```

**That's it!** Put your APK or JAR in `~/apks/`, open it in JADX, and let AI analyze it.

> 💡 **Auto-load**: Name your file `target.apk`, `target.jar`, `target.aar`, or `target.dex`. JADX loads it automatically on startup.

> ⚠️ **Important**: You MUST load a file (APK/JAR/AAR/DEX) in JADX before AI can connect. The plugin only initializes after loading a file—MCP Server cannot connect to JADX until then.

---

## 📖 Documentation

### 🚀 Getting Started

| Document | Description |
|:---------|:------------|
| **[Introduction](docs/overview/introduction.md)** | Understand core concepts, capabilities, use cases |
| **[System Architecture](docs/overview/architecture.md)** | Three-tier design, port reference, component communication |
| **[5-Minute Quick Start](docs/getting-started/quickstart.md)** | One-command Docker deployment |

### 🐳 Deployment Guides

| Document | Description |
|:---------|:------------|
| **[Docker Complete Guide](docs/deployment/docker.md)** | Single container, multi-container, standalone MCP Server |
| [Docker Compose](docs/deployment/docker-compose.md) | Multi-instance setup (team collaboration, version comparison) |
| [Local Installation](docs/deployment/local.md) | Without Docker |

### 🔧 Configuration & Integration

| Document | Description |
|:---------|:------------|
| **[AI Client Configuration](docs/guides/ai-clients.md)** | Claude, Cursor, Continue, etc. |
| [Multi-Instance Management](docs/guides/multi-instance.md) | Parallel analysis of multiple APKs |
| [AI Testing Prompts](docs/guides/ai-prompts.md) | Automated testing templates |

### 📚 Reference

| Document | Description |
|:---------|:------------|
| [Tools Reference](docs/reference/tools.md) | Complete 45 MCP tools matrix |
| [Configuration Reference](docs/reference/configuration.md) | All configuration options |
| [Security Policy](docs/security/security.md) | Authentication, permissions, SSRF protection |

### 🛠️ Troubleshooting

| Document | Description |
|:---------|:------------|
| **[Common Issues](docs/troubleshooting/common-issues.md)** | FAQ + Windows/Linux/macOS specific issues |
| [Changelog](docs/changelog/CHANGELOG.md) | Version history |

---

## 🧠 AI Skills

Install specialized analysis skills for Claude Code, Cursor, and other AI assistants:

```bash
# Install all skills
npx skills add xjoker/jadx-ai-mcp

# Install specific skill
npx skills add xjoker/jadx-ai-mcp --skill security-audit
```

**6 available skills**: quickstart, logic-tracing, security-audit, crypto-analysis, frida-hooks, refactoring

> See [Introduction - AI Skills System](docs/overview/introduction.md#ai-skills-system) for details.

---

## 🙏 Credits

- Original project: [@zinja-coder](https://github.com/zinja-coder/jadx-ai-mcp)
- JADX decompiler: [skylot/jadx](https://github.com/skylot/jadx)

---

## 📜 License

Apache 2.0 - See [LICENSE](LICENSE)
