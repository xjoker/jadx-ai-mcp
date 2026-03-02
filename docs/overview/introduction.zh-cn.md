# 项目介绍

[English](introduction.md) | **简体中文**

---

## 一句话定位

**JADX-AI-MCP** 让 AI（Claude、ChatGPT）直接分析 Android APK 和 Java JAR 文件，通过自然语言完成代码审计、逆向分析和安全研究。

---

## 解决什么问题？

### 传统逆向工作流的痛点

```
1. 打开 JADX → 手动搜索类名
2. 逐个点击查看源码
3. 手动跟踪引用关系
4. 复制粘贴到笔记
5. 重复以上步骤 ×100
```

**问题**：
- ❌ 效率低：大量重复操作
- ❌ 易遗漏：无法全局搜索
- ❌ 难理解：复杂调用链难以理清

### JADX-AI-MCP 的解决方案

```
你: "找到所有加密相关的类并分析其安全性"
AI: ✅ 自动搜索 → 反编译 → 分析 → 生成报告
```

**优势**：
- ✅ 高效：AI 自动化批量操作
- ✅ 全面：跨类搜索、引用追踪
- ✅ 智能：理解代码逻辑、发现漏洞

---

## 支持的文件类型详解

| 类型 | 全称 | 典型用途 | 特点 |
|:-----|:-----|:---------|:-----|
| **APK** | Android Package | Android 应用安装包 | 包含 DEX、资源、Manifest |
| **JAR** | Java Archive | Java 库、Spring Boot 应用 | 纯 Java 字节码 |
| **AAR** | Android Archive | Android 库 | APK 的库形式 |
| **DEX** | Dalvik Executable | Android 字节码 | APK 内的可执行代码 |

### 特殊支持：JAR 文件分析

除了 APK，本项目还提供 **5 个 JAR 专用工具**：

| 工具 | 用途 |
|:-----|:-----|
| `jar_get_manifest` | 读取 MANIFEST.MF（Main-Class、版本等） |
| `jar_get_entry_points` | 发现入口点（main 方法、Spring Boot） |
| `jar_get_dependencies` | 分析依赖（Maven、BOOT-INF/lib） |
| `jar_get_services` | 读取 SPI 服务（JDBC、日志框架） |
| `jar_get_bytecode` | 获取字节码（类似 javap） |

**适用场景**：
- Spring Boot 应用分析
- Java 恶意软件分析
- 第三方库审计

---

## 核心能力矩阵

### 1. 代码搜索

| 能力 | 示例 | 搜索范围 |
|:-----|:-----|:---------|
| **类名搜索** | "找到所有 Activity" | 类名、包名 |
| **方法名搜索** | "找到所有 onClick 方法" | 方法签名 |
| **字段名搜索** | "找到所有 password 字段" | 字段声明 |
| **代码内容搜索** | "找到所有调用 AES 的代码" | 方法体内容 |
| **注释搜索** | "找到所有 TODO 注释" | 代码注释 |

**性能**：
- 元数据搜索（类/方法/字段）：**<100ms**
- 代码内容搜索：**<60s**（首次触发反编译）

---

### 2. 引用追踪

**交叉引用（Xrefs）**：找出"谁在调用这个类/方法/字段"

```
用户: "谁调用了 NetworkUtil.sendRequest()？"
AI:
  ✅ LoginActivity.doLogin() (第 45 行)
  ✅ PaymentService.submitOrder() (第 89 行)
  ✅ ApiClient.post() (第 123 行)
```

**用途**：
- 漏洞影响面分析
- API 使用统计
- 死代码检测

---

### 3. 安全审计

| 审计类型 | AI 提示词示例 |
|:---------|:--------------|
| **硬编码密钥** | "检查是否有硬编码的 API Key" |
| **不安全加密** | "找出所有使用 MD5/DES 的代码" |
| **SQL 注入** | "检查是否有拼接 SQL 语句的代码" |
| **权限滥用** | "分析 Manifest 中的危险权限" |
| **WebView 漏洞** | "检查 WebView 是否启用了 JavaScript" |

**OWASP 覆盖**：
- A01: 访问控制
- A02: 加密失效
- A03: 注入
- A08: 软件和数据完整性失败

---

### 4. 代码理解

| 场景 | AI 能力 |
|:-----|:---------|
| **解释复杂逻辑** | 分析混淆代码的真实意图 |
| **生成流程图** | 绘制登录/支付流程 |
| **提取配置** | 从代码中提取 API 端点、加密参数 |
| **还原算法** | 还原自定义加密/签名算法 |

---

## AI 技能系统（Skills）

为 Claude Code、Cursor 等 AI 助手安装专业分析技能：

```bash
# 安装所有技能
npx skills add xjoker/jadx-ai-mcp

# 安装特定技能
npx skills add xjoker/jadx-ai-mcp --skill security-audit
```

### 技能列表

| 技能 | 描述 | 适用场景 |
|:-----|:-----|:---------|
| **quickstart** | 入门指南、性能优化 | 新手上手 |
| **logic-tracing** | 调用链追踪、API 流程分析 | 理解业务逻辑 |
| **security-audit** | OWASP 检查、漏洞挖掘 | 安全审计 |
| **crypto-analysis** | 加密算法分析、反调试 | 恶意软件分析 |
| **frida-hooks** | 生成 Frida 脚本 | 动态插桩 |
| **refactoring** | 重命名混淆代码 | 提高可读性 |

> 浏览更多技能：[skills.sh](https://skills.sh)

---

## 适用场景

### 1. 安全研究

- **漏洞挖掘**：批量检测常见漏洞模式
- **恶意软件分析**：识别恶意行为（权限滥用、隐私窃取）
- **合规审计**：验证是否符合 GDPR、COPPA 等法规

### 2. 应用分析

- **竞品分析**：了解竞品 APP 的技术架构
- **第三方库审计**：检查 SDK 的隐私合规性
- **版本对比**：对比不同版本的差异

### 3. CTF 与挑战

- **逆向题目**：快速定位 Flag 藏匿位置
- **加密题目**：分析加密算法并编写解密脚本
- **混淆分析**：去除混淆，还原原始逻辑

### 4. 开发调试

- **依赖分析**：查看 JAR 的依赖关系
- **代码学习**：学习优秀开源项目的实现
- **Bug 定位**：在反编译代码中定位问题

---

## 本 Fork 的独特优势

相比原版 [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp)，本项目提供重大增强：

| 特性 | 说明 |
|:-----|:-----|
| 🚀 **智能批量优化** | 4 层分级策略，避免 60-120 秒无效反编译。大响应（>8KB）自动分块传输。 |
| 🔄 **Transfer API** | HTTP 直接下载突破 MCP 约 16KB 限制。已验证支持 32.2 万类规模。 |
| 💼 **完整 JVM 支持** | APK、JAR、AAR、DEX 全支持。5 个 JAR 专用工具。 |
| ⚡ **ClassCacheManager** | 后台缓存 + 自动失效，重复分析快 10-50 倍。 |
| 🐳 **All-in-One Docker** | 一键部署 GUI + AI 服务器。多平台支持（amd64/arm64）。 |

> 📚 **44 篇中英双语指南**，涵盖部署、工具、故障排查和 AI 测试提示词。

---

## 快速开始

```bash
# 一键启动（图形界面 + AI）
docker run -d --name jadx -p 6080:6080 -p 8651:8651 -v ~/apks:/apks xjoker/jadx-ai-mcp:latest

# 在浏览器中打开 JADX 图形界面
open http://localhost:6080
```

完成！将你的 APK 或 JAR 放入 `~/apks/`，在 JADX 中打开，让 AI 帮你分析。

---

## 相关文档

- [系统架构](architecture.zh-cn.md) - 理解三层架构设计
- [快速开始](../getting-started/quickstart.zh-cn.md) - 5 分钟部署
- [工具参考](../reference/tools.zh-cn.md) - 完整的 45 个工具矩阵
- [AI 技能](../guides/ai-prompts.zh-cn.md) - 测试提示词示例

---

*最后更新：2026-02-10*
