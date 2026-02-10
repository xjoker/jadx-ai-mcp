# Introduction

**English** | [简体中文](introduction.zh-cn.md)

---

## One-Sentence Summary

**JADX-AI-MCP** enables AI (Claude, ChatGPT) to directly analyze Android APKs and Java JARs, completing code audits, reverse engineering, and security research through natural language.

---

## What Problem Does It Solve?

### Pain Points in Traditional Reverse Engineering

```
1. Open JADX → manually search for class names
2. Click each one to view source code
3. Manually track references
4. Copy-paste to notes
5. Repeat above ×100
```

**Problems**:
- ❌ Low efficiency: lots of repetitive operations
- ❌ Easy to miss: no global search
- ❌ Hard to understand: complex call chains difficult to trace

### JADX-AI-MCP's Solution

```
You: "Find all encryption-related classes and analyze their security"
AI: ✅ Auto search → decompile → analyze → generate report
```

**Advantages**:
- ✅ Efficient: AI automates batch operations
- ✅ Comprehensive: cross-class search, reference tracking
- ✅ Intelligent: understands code logic, discovers vulnerabilities

---

## Supported File Types

| Type | Full Name | Typical Use | Characteristics |
|:-----|:----------|:------------|:----------------|
| **APK** | Android Package | Android app installer | Contains DEX, resources, Manifest |
| **JAR** | Java Archive | Java libraries, Spring Boot apps | Pure Java bytecode |
| **AAR** | Android Archive | Android libraries | Library form of APK |
| **DEX** | Dalvik Executable | Android bytecode | Executable code within APK |

### Special Support: JAR Analysis

Beyond APK, this project provides **5 JAR-specific tools**:

| Tool | Purpose |
|:-----|:--------|
| `jar_get_manifest` | Read MANIFEST.MF (Main-Class, version, etc.) |
| `jar_get_entry_points` | Discover entry points (main methods, Spring Boot) |
| `jar_get_dependencies` | Analyze dependencies (Maven, BOOT-INF/lib) |
| `jar_get_services` | Read SPI services (JDBC, logging frameworks) |
| `jar_get_bytecode` | Get bytecode (similar to javap) |

**Use Cases**:
- Spring Boot application analysis
- Java malware analysis
- Third-party library auditing

---

## Core Capabilities Matrix

### 1. Code Search

| Capability | Example | Search Scope |
|:-----------|:--------|:-------------|
| **Class Search** | "Find all Activities" | Class names, package names |
| **Method Search** | "Find all onClick methods" | Method signatures |
| **Field Search** | "Find all password fields" | Field declarations |
| **Code Content Search** | "Find all code calling AES" | Method body content |
| **Comment Search** | "Find all TODO comments" | Code comments |

**Performance**:
- Metadata search (class/method/field): **<100ms**
- Code content search: **<60s** (first time triggers decompilation)

---

### 2. Reference Tracking

**Cross-references (Xrefs)**: Find "who is calling this class/method/field"

```
You: "Who calls NetworkUtil.sendRequest()?"
AI:
  ✅ LoginActivity.doLogin() (line 45)
  ✅ PaymentService.submitOrder() (line 89)
  ✅ ApiClient.post() (line 123)
```

**Use Cases**:
- Vulnerability impact analysis
- API usage statistics
- Dead code detection

---

### 3. Security Auditing

| Audit Type | AI Prompt Example |
|:-----------|:------------------|
| **Hardcoded Keys** | "Check for hardcoded API keys" |
| **Insecure Crypto** | "Find all code using MD5/DES" |
| **SQL Injection** | "Check for SQL string concatenation" |
| **Permission Abuse** | "Analyze dangerous permissions in Manifest" |
| **WebView Vulnerabilities** | "Check if WebView has JavaScript enabled" |

**OWASP Coverage**:
- A01: Broken Access Control
- A02: Cryptographic Failures
- A03: Injection
- A08: Software and Data Integrity Failures

---

### 4. Code Understanding

| Scenario | AI Capability |
|:---------|:--------------|
| **Explain Complex Logic** | Analyze obfuscated code's real intent |
| **Generate Flowcharts** | Draw login/payment flows |
| **Extract Configuration** | Extract API endpoints, encryption params from code |
| **Restore Algorithms** | Restore custom encryption/signature algorithms |

---

## AI Skills System

Install specialized analysis skills for Claude Code, Cursor, and other AI assistants:

```bash
# Install all skills
npx skills add xjoker/jadx-ai-mcp

# Install specific skill
npx skills add xjoker/jadx-ai-mcp --skill security-audit
```

### Skills List

| Skill | Description | Use Case |
|:------|:------------|:---------|
| **quickstart** | Getting started, performance optimization | Onboarding |
| **logic-tracing** | Call chain tracking, API flow analysis | Understanding business logic |
| **security-audit** | OWASP checks, vulnerability hunting | Security auditing |
| **crypto-analysis** | Encryption algorithm analysis, anti-debugging | Malware analysis |
| **frida-hooks** | Generate Frida scripts | Dynamic instrumentation |
| **refactoring** | Rename obfuscated code | Improve readability |

> Browse more skills: [skills.sh](https://skills.sh)

---

## Use Cases

### 1. Security Research

- **Vulnerability Hunting**: Batch detect common vulnerability patterns
- **Malware Analysis**: Identify malicious behaviors (permission abuse, privacy theft)
- **Compliance Audit**: Verify GDPR, COPPA compliance

### 2. Application Analysis

- **Competitor Analysis**: Understand competitor app's technical architecture
- **Third-party SDK Audit**: Check SDK privacy compliance
- **Version Comparison**: Compare differences between versions

### 3. CTF and Challenges

- **Reverse Engineering**: Quickly locate Flag hiding spots
- **Cryptography**: Analyze encryption algorithms and write decryption scripts
- **Obfuscation Analysis**: Remove obfuscation, restore original logic

### 4. Development and Debugging

- **Dependency Analysis**: View JAR dependency relationships
- **Code Learning**: Study excellent open-source project implementations
- **Bug Location**: Locate issues in decompiled code

---

## What Makes This Fork Different

Compared to the original [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp), this fork provides major enhancements:

| Feature | Description |
|:--------|:------------|
| 🚀 **Smart Batch Optimization** | 4-tier strategy avoids 60-120s wasted decompilation. Auto-chunks large responses (>8KB). |
| 🔄 **Transfer API** | HTTP direct download bypasses MCP's ~16KB limit. Tested with 322K classes. |
| 💼 **Full JVM Support** | APK, JAR, AAR, DEX all supported. 5 JAR-specific tools. |
| ⚡ **ClassCacheManager** | Background caching + auto-invalidation, 10-50x faster repeated analysis. |
| 🐳 **All-in-One Docker** | One-command deployment of GUI + AI server. Multi-platform (amd64/arm64). |

> 📚 **44 bilingual guides** covering deployment, tools, troubleshooting, and AI testing prompts.

---

## Quick Start

```bash
# One command to start (GUI + AI)
docker run -d --name jadx -p 6080:6080 -p 8651:8651 -v ~/apks:/apks xjoker/jadx-ai-mcp:latest

# Open JADX GUI in browser
open http://localhost:6080
```

Done! Put your APK or JAR in `~/apks/`, open it in JADX, and let AI analyze it.

---

## Related Documentation

- [System Architecture](architecture.md) - Understand the three-tier design
- [Quick Start](../getting-started/quickstart.md) - 5-minute deployment
- [Tools Reference](../reference/tools.md) - Complete 45 tools matrix
- [AI Skills](../guides/ai-prompts.md) - Testing prompt examples

---

*Last updated: 2026-02-10*
