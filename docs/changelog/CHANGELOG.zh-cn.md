# 更新日志

[English](CHANGELOG.md) | **简体中文**

---

JADX-AI-MCP 的所有重要变更都记录在此文件中。

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 和 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 规范。

> 🔱 本更新日志涵盖从 [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp) fork 后的所有变更。

---

## [6.1.7] - 2026-03-24

### 🐛 Bug 修复

- 修复 Dockerfile.mcp 健康检查端点（`/status` → `/health`），与实际服务器端点一致。

### 🚀 改进

**Docker OOM 恢复**
- `jadx-gui-wrapper.sh`：检测 OOM 崩溃（`-XX:+ExitOnOutOfMemoryError` 触发的 exit code 3），设置标记使下次重启跳过自动加载，防止 OOM→重启→OOM 无限循环。
- 信号转发：JADX 作为后台子进程运行，包装脚本可将 `docker stop` / supervisord 的 `SIGTERM`/`SIGINT` 转发给 JVM，同时捕获退出码。

**容器内存限制**
- 每个 JADX 实例默认容器内存限制 4GB（`mem_limit`），JVM 堆上限 2560MB（`-Xmx2560m`）。
- MCP Server 容器限制 512MB。
- 可通过 `JADX_MEM_LIMIT` 和 `JADX_JAVA_OPTS` 环境变量配置。

**Supervisord 改进**
- `jadx-gui` 日志重定向到 `stdout`/`stderr`，通过 `docker logs` 可见（OOM 警告、崩溃信息等）。
- 增加 `startretries=5`、`stopwaitsecs=30`、`stopsignal=TERM`，更健壮的进程管理。

**无状态 HTTP 传输**
- MCP HTTP 模式启用 `stateless_http=True`：无会话跟踪，服务器重启后自动恢复。代价：不支持 SSE 流和服务器主动通知。

### 📦 变更文件
- `docker/Dockerfile.mcp` — 健康检查端点修复
- `docker/docker-compose.yaml` — 内存限制、JAVA_OPTS 支持
- `docker/scripts/jadx-gui-wrapper.sh` — OOM 恢复、信号转发
- `docker/scripts/supervisord.conf` — 日志重定向、重试/停止配置
- `jadx-mcp-server/jadx_mcp_server.py` — 无状态 HTTP 传输

---

## [6.1.6] - 2026-03-19

### 🐛 Bug 修复

**实例管理**
- 修复：`register_instance_tools(mcp)` 已导入但从未调用 — 7 个实例管理工具（`list_jadx_instances` 等）在运行时不可用。这是 AI 将实例查询误路由到 `get_file_info` 的根本原因。
- 移除跨实例 fallback：每个 JADX 实例加载不同的 APK/JAR，静默切换到其他实例会返回错误应用的数据。现在改为返回明确的错误提示。
- 修复 `auth_failed` 状态振荡：401 错误的实例不再在每次健康检查时在 `auth_failed` 和 `connected` 之间来回切换。
- 修复：已连接实例的 token 被撤销后，现在正确转换为 `auth_failed`（之前因 `/health` 不需要认证而保持 `connected`）。

**并发与缓存**
- `handleClassSource` 和 `handleBatchClassSource` 现在在调用 `cls.getCode()` 前获取 write lock — JADX 内部状态对并发反编译不是线程安全的。
- 所有重命名操作（`rename_class/method/field/package`）现在调用 `ClassCacheManager.invalidateCode()` 防止返回过期的反编译代码。
- `JadxSearchLock.tryAcquire()`：tracking 状态仅在成功获取锁后重置，而非之前 — 防止 tracking 永久丢失。
- 重命名操作现在仅清除受影响实例的 response cache，而非所有实例。
- 批量 `handleBatchClassSource`：增加 `else` 分支确保 `found` 字段始终存在。
- `handleBatchClassSource`：`chunk` 参数增加 `NumberFormatException` 捕获。
- `ResponseCache.get()`：TTL 过期时将 `del` 改为 `pop(key, None)` 避免并发 `KeyError`。

**实例连接**
- 消除启动竞争条件：health monitor 不再等待 2 秒才执行首次检查。启动后立即调用的 MCP 工具现在可以正常工作。
- On-demand probe：访问 pending/disconnected 实例时，先执行 3 秒快速探测。如果 JADX 可达，立即提升为 `connected`。
- `get_from_jadx`：`ConnectError` 和 `ConnectTimeout` 现在立即将实例标记为 `disconnected`（之前需等待最多 30 秒的 health monitor）。
- Health monitor：pending 实例的健康统计不再重复计入 `unhealthy_count`。
- APK 切换检测：health monitor 现在同时检查 `apk_package` 和 `version_name` 变化，变化时清除 response cache。

### 🚀 改进

**模糊实例路由**（新功能）
- `instance_id` 参数现在支持模糊匹配：实例名、APK 包名（`com.xingin.xhs`）、JADX 实例名（`xhs-v835`）、应用显示名称、文件名、版本号。
- 匹配优先级：精确名称 → 精确包名 → 精确 JADX 名 → 精确应用名 → 部分匹配 → 文件名 → 版本号。
- 示例：`get_class_source(class_name="...", instance_id="xhs")` 自动路由到加载了小红书的实例。

**认证错误明确化**（新功能）
- 新增 `auth_failed` 实例状态（区别于通用 `error`），附带可操作的错误消息。
- On-demand probe 和 health monitor 均区分 401 和连接问题。
- 状态页面：`auth_failed` 实例显示红色徽章和警告横幅。

**APK 显示名称**（新功能）
- `/apk-info` 端点现在从 AndroidManifest.xml 的 `<application android:label="...">` 提取 `app_name`。
- 用于模糊实例匹配，支持按应用显示名称路由。

**工具描述优化**
- `list_jadx_instances`：添加使用场景指引和模糊匹配提示。
- `get_file_info`：明确需要已连接实例，不是用于查询实例状态。
- `get_decompile_status`：明确返回运行时指标，非文件元数据。
- `search_classes_by_keyword`：标记为"主力搜索工具"，附各 `search_in` 值的速度指南。
- `search_method_by_name`：添加"建议改用 search_classes_by_keyword"提示。

### ⚡ 性能优化

- **ReadWriteLock**：元数据读取操作不再互相阻塞，仅反编译需要排他写锁。
- **反编译代码缓存**：`ClassCacheManager.codeCache`（LRU，200 条目，10 分钟 TTL）。
- **MCP 响应缓存**：Python 侧 `ResponseCache`（LRU，100 条目，60 秒 TTL）。
- **并行健康检查**：`asyncio.gather()` 并发检查所有实例。
- **Strings 缓存**：`ResourceCacheManager.parsedStringsCache` 缓存解析后的 `strings.xml`。
- **共享 HTTP 客户端**：`InstanceRegistry` 使用连接池化的 `httpx.AsyncClient`。

---

## [6.1.5] - 2026-03-18

### 🚀 改进

**部署与配置**
- Docker Compose 时区现可通过 `TZ` 环境变量配置（默认 `UTC`，原硬编码 `Asia/Shanghai`）
- 新增 `docker/.env.example`，包含所有可配置环境变量说明
- 新增 `/health` 轻量级健康检查端点（无需认证）；Docker healthcheck 已切换使用
- 启动时检测默认 token（`admin-secret-token`、`jadx-plugin-secret-token`）并打印警告

**统一错误响应格式**
- 新增 `make_error(code, message, **extra)` 辅助函数，统一错误响应结构
- 新增错误码：`RATE_LIMITED`、`TIMEOUT`、`INTERNAL_ERROR`
- `config.py`、`transfer_tools.py`、`instance_tools.py` 所有错误返回改用统一的 `{error, message}` 格式

**状态页增强**
- Warning 区域无警告时自动隐藏（SSR + JS 联动）
- 实例表格移动端可横向滚动（`overflow-x:auto`）
- Scheduler 列表头/单元格添加 tooltip 说明 `m=metadata c=code_read x=exclusive q=queue`
- 刷新失败时显示醒目红色提示（`.refresh-error` CSS 类）
- Session cookie 增加 24 小时过期时间（`max_age=86400`）

**登录 CSRF 防护**
- `/status/login` POST 端点实现 double-submit cookie 模式
- 每次页面渲染生成 CSRF token，表单提交时校验

**代码架构**
- 将 `jadx_mcp_server.py` 中 30+ 个内联工具注册提取到 6 个工具模块的 `register_*_tools()` 函数
- 主服务器文件从 1366 行精简到 595 行（减少 56%）
- 每个工具模块通过 `register_class_tools(mcp, with_busy_check)` 模式自注册

**实例 Fallback**
- 默认实例断开连接时，自动回退到第一个已连接实例
- 新增 `InstanceRegistry.get_first_connected()` 方法

**重命名预检**
- `rename` 工具新增 `dry_run=True` 参数
- 返回目标存在性检查和类信息预览，不执行实际重命名

### 📦 变更文件
- `docker/docker-compose.yaml` — TZ 可配置，healthcheck 使用 `/health`
- `docker/.env.example` — 新文件
- `docker/scripts/start.sh` — 默认 token 警告
- `jadx-mcp-server/jadx_mcp_server.py` — 工具注册提取，token 警告
- `jadx-mcp-server/src/server/types.py` — `make_error()`，新错误码
- `jadx-mcp-server/src/server/config.py` — 统一错误格式，实例 fallback
- `jadx-mcp-server/src/server/status_page.py` — Warnbox 隐藏、滚动、tooltip、CSRF、刷新错误
- `jadx-mcp-server/src/server/instance_registry.py` — `get_first_connected()`
- `jadx-mcp-server/src/server/tools/*.py` — 添加 `register_*_tools()` 函数
- `jadx-mcp-server/tests/test_status_page.py` — CSRF 测试用例

---

## [6.1.4] - 2026-03-02

### 🐛 Bug 修复

**跨 ClassLoader 端口泄漏**
- 修复 JADX 执行"重置代码缓存"（classloader 重载）时的端口泄漏问题
- 使用 JVM 全局 `System.getProperties()` 存储 `ServerSocketChannel` 引用，跨 classloader 存活
- 重新绑定前自动关闭孤立的 server socket，防止 `BindException`

**菜单残留清理**
- 修复 classloader 重载后出现重复 "JADX AI MCP Server" 菜单的问题
- 添加新菜单前按文本匹配移除旧菜单项（倒序遍历，EDT 线程安全）

### 🛡️ MCP 错误处理

**结构化错误响应**
- 添加实例状态预检：实例处于 `disconnected` 或 `pending` 状态时返回结构化错误
- 细粒度 HTTP 异常处理：`ConnectError`、`ConnectTimeout`、`ReadTimeout` 各返回可操作的 `suggestion` 字段
- 增强 HTTP 500 响应，包含截断的错误详情和恢复指导
- 增强 HTTP 503 响应，解析 `retry_after` 和初始化状态

### 📚 文档

- 文档系统全面重构：整合 44 篇双语指南
- 新增架构概述和项目介绍页面
- 统一常见问题指南，替换原有 FAQ/Windows 故障排除
- 精简 README，聚焦功能特性表

### ⚙️ CI/CD

- 基础镜像构建拆分为独立的 `docker-base.yml` 工作流
- 矩阵构建使用原生 ARM runner（`ubuntu-24.04-arm`）— 3分钟 vs QEMU 的 20分钟
- 更新 `JADX_VERSION` 至 1.5.5，`BASE_IMAGE_VERSION` 至 1.2
- 移除未使用的 `test.yml` 工作流

### 🔧 代码质量

- 移除调试工具（`DebugRoutes.java`、`debug_tools.py`）
- 代码审查修复和调试代码清理

---

## [6.1.2] - 2026-02-06

### 🐛 Bug 修复

**Docker 容器安全加固**
- 修复 supervisord PID 文件权限：从 `/var/run/supervisord.pid` 改为 `/tmp/supervisord.pid`
- 修复 UID 冲突：从 UID 1000 改为 UID 1001（基础镜像已有 `ubuntu` 用户占用 UID 1000）
- 修复 uv 二进制权限：从符号链接改为复制（`ln -s` → `cp`）以允许非 root 用户访问
- 修复 `/var/log/supervisor` 目录权限
- 修复 `/apks` 目录权限
- 添加 X11 socket 目录 `/tmp/.X11-unix` 并设置正确权限

**Dockerfile.local**
- 添加缺失的非 root 用户配置（之前以 root 运行）

**Dockerfile.mcp**
- 添加非 root 用户 `mcp`（UID 1001）以提高安全性
- 修复 uv 二进制权限（符号链接 → 复制）

### 🔒 安全增强

- 所有 Docker 容器现在都以非 root 用户运行（UID 1001）
- 更新基础镜像版本至 1.2，包含安全修复
- 实现时间安全的令牌比较以防止时序攻击

### 🛡️ 代码质量

- 添加批量大小输入验证（每次请求最多 20 个类）
- 为大小估算失败添加保守的回退策略（5000 字节/类）

---

## [6.1.1] - 2026-02-05

### 🐛 Bug 修复

**All-in-One 容器**
- 修复 All-in-One 容器无法连接 JADX 实例的问题
  - 将默认 JADX 实例从 `host.docker.internal` 改为 `127.0.0.1`
  - 修复 MCP Server 在容器内的连接配置

- 修复 supervisord 启动失败问题
  - 移除未定义的 `JADX_MCP_BIND_ADDRESS` 环境变量引用
  - 优化容器内服务绑定地址为 `0.0.0.0`

### 📚 文档

**端口说明**
- 添加完整的端口参考表格 (6080/8650/8651)
- 详细说明各端口用途、访问来源和安全注意事项

**部署场景**
- 新增三种部署场景指南：
  - **标准模式**（GUI + AI）：`docker run -p 6080:6080 -p 8651:8651 ...`
  - **仅 AI 模式**（不暴露 GUI 端口）：`docker run -p 8651:8651 ...`
  - **开发模式**（完整端口）：`docker run -p 6080:6080 -p 8650:8650 -p 8651:8651 ...`

- 完善快速启动命令的端口映射说明
- 统一中英文文档

### 🐳 Docker

**多平台支持**
- 基础镜像 `xjoker/jadx-ai-mcp-base:1.1` 升级到 Java 25 + Ubuntu 24.04 Noble
- 主镜像 `xjoker/jadx-ai-mcp:latest` 支持 linux/amd64 和 linux/arm64

### 📦 变更文件

- `README.md` / `README.zh-cn.md` - 文档改进
- `docker/Dockerfile` - 移除错误的环境变量
- `docker/README.md` / `docker/README.zh-cn.md` - Docker 文档更新
- `docker/scripts/supervisord.conf` - 修复配置错误
- `jadx-mcp-server/data/config/jadx-config.toml` - 默认实例配置

---

## [6.1.0] - 2026-01-20

### 🎉 重大功能

**Transfer API** - 大文件下载系统
- 绕过 MCP 消息大小限制（约 16KB）用于批量操作
- 基于 HTTP 的令牌系统，支持直接数据下载
- 支持 JSON 和 ZIP 格式
- 多种压缩选项（Brotli、GZIP、无压缩）

**完整的 JAR/AAR/DEX 支持**（全 JVM 字节码分析）
- 将 JADX-AI-MCP 从 Android 专用工具升级为通用 JVM 字节码分析平台
- 5 个 JAR 专用工具 + 统一接口工具
- 文件类型检测和动态工具可用性

### 新增

**Transfer API 工具**:
- `create_transfer_token` — 生成可配置超时的下载令牌
- `get_transfer_token_status` — 检查令牌有效性和使用状态
- `revoke_transfer_token` — 手动撤销令牌（默认自动过期）

**Transfer API 端点**（HTTP）:
- `/transfer/download/batch-classes` — 下载多个类源码
- 支持 `format=json|zip` 和 `compression=br|gzip|none|auto`
- 速率限制：每分钟创建 10 个令牌，每分钟下载 20 次

**配置**:
- `MCP_SERVER_URL` 环境变量（最高优先级）
- `jadx-config.toml` 中的 `[server] mcp_url`
- 从启动参数自动检测（回退）

**统一接口工具**（适用于 APK/JAR/AAR/DEX）：
- `get_file_info` — 统一文件元数据，自动识别文件类型并推荐工具
- `get_config_strings` — 配置字符串（APK: strings.xml 概要, JAR: *.properties）
- `get_package_classes` — 按包前缀获取类，支持 `auto=true` 自动检测

**JAR 专用工具**：
- `jar_get_manifest` — 读取 META-INF/MANIFEST.MF（Main-Class, Implementation-*, Spring Boot）
- `jar_get_services` — 读取 SPI 服务（META-INF/services/*）
- `jar_get_entry_points` — 发现入口点（Main-Class, @SpringBootApplication, main() 方法）
- `jar_get_dependencies` — 分析嵌入依赖（pom.properties, Class-Path, BOOT-INF/lib）
- `jar_get_bytecode` — 查看类字节码结构（类似 javap）

**基础设施**：
- `FileTypeDetector.java` — 基于 Magic Number 的文件类型检测
- `NotApplicableResponse.java` — APK 专用工具对 JAR 返回统一 NOT_APPLICABLE 响应
- `jadx://capabilities` MCP Resource 提供动态工具可用性
- 安全：Transfer API 的速率限制和参数验证

### 变更
- APK 专用工具现在对 JAR 文件返回 `NOT_APPLICABLE` 明确提示，而非崩溃
- 工具 docstring 增强，添加 `Returns:` 规范
- 异常信息脱敏（移除 6 处 `str(e)`）

### 移除
- `set_jadx_port()` 函数（未使用的遗留代码）
- `health_ping()` 函数（已被 HealthMonitor 取代）
- FastMCP 初始化中已废弃的 `stateless_http` 参数

### 修复
- FastMCP 库的 DeprecationWarning
- 工具文档中 Transfer API Python 使用示例

### 技术细节
- **60+ 个文件修改**，**+5,000 行**代码
- Transfer API：带自动清理的令牌存储，单次使用强制执行
- 使用 Nexus JAR（112,699 类）和 XHS APK（322,723 类）测试
- 完全向后兼容

### Docker
```bash
docker run -d \
  -e MCP_SERVER_URL="http://192.168.75.144:8651" \
  -p 6080:6080 -p 8650:8650 -p 8651:8651 \
  -v ./apks:/apks \
  xjoker/jadx-ai-mcp:latest
```

---

## [6.0.53] - 2026-01-16 18:26

### 新增
- **`search_native_methods` 工具** 用于 JNI/SO 安全分析
  - 搜索 APK 中所有 native 方法，无需触发反编译
  - 支持 `package` 过滤和分页
  - 返回 Frida 兼容参数类型 (`param_types_frida`)
  - 在 XHS 应用中发现 1,425 个 native 方法

---

## [6.0.52] - 2026-01-16 18:06

### 新增
- **`native_method_names`** 字段添加到 `get_class_info` 响应
  - 列出类中所有 native 方法，便于快速 JNI 分析
  - `native_count` 提供统计汇总

### 变更
- 从 `get_method_signature` 移除 `frida_hook_template`（AI 可根据类型信息自行生成）

---

## [6.0.51] - 2026-01-16 17:28

### 新增
- **Frida 友好输出格式** 用于方法和字段：
  - `get_fields_of_class` 添加 `type_frida` 字段（如 `[B` 表示 `byte[]`）
  - `get_method_signature` 添加 `frida_overload` 字符串用于直接 Frida Hook
  - `/fields-of-class` 和 `/methods-of-class` 结构化 JSON 输出
  - 方法列表添加 `is_static`, `is_native`, `overload_count`

### 破坏性变更
- `/fields-of-class` 现返回 JSON（原为纯文本）
- `/methods-of-class` 现返回 JSON（原为纯文本）

---

## [6.0.50] - 2026-01-16 15:32

### 新增
- **禁用自动重命名，确保 Hook 开发准确性**
  - Docker：`jadx-gui-wrapper.sh` 添加 `--rename-flags none`
  - 插件：启动时通过 `JadxArgs` API 清除 `renameFlags`
  - 字段/方法名现在与运行时一致（如 `a` 而非 `f439360a`）

---


## [6.0.49] - 2026-01-16 11:36

### 新增
- **MCP 资源** 用于 AI 智能决策：
  - `usage-guide`: 完整工具使用参考
  - `decision-matrix`: 性能感知工具选择指南
  - `performance-benchmarks`: 所有操作的预期时间
- MCP 指令用于主动引导
- 增强工具文档字符串，添加性能特性说明

---

## [6.0.48] - 2026-01-16 11:27

### 新增
- **智能批量并行搜索优化**
- 移除工具注册中已废弃的 `class_offset`/`class_limit`

---

## [6.0.47] - 2026-01-16 10:37

### 新增
- 兼容性表格文档
- 增强的示例配置文件

---

## [6.0.46] - 2026-01-15 18:55

### 新增
- 工具文档字符串中添加性能警告（大类/资源可能超时）
- 工具超时行为文档

### 修复
- Docker Compose 多实例部署 `JADX_MCP_BIND_ADDRESS` 修复

---

## [6.0.45] - 2026-01-15 18:24

### 修复
- `clear_class_cache` 正确使用 InstanceRegistry
- 缓存管理文档更新

---

## [6.0.44] - 2026-01-15 18:14

### 变更
- 版本号更新

---

## [6.0.43] - 2026-01-15 18:05

### 新增
- 缓存清除操作 30 秒全局冷却时间
- `RefactoringRoutes` 防抖缓存失效优化

---

## [6.0.42] - 2026-01-15 17:22

### 新增
- ClassCacheManager 完整部署到全部 5 个批量工具：
  - `batch_get_class_source`
  - `batch_get_method_by_name`
  - `batch_get_xrefs`
  - `batch_get_method_callees`
  - `batch_get_method_callers`

---

## [6.0.41] - 2026-01-15 17:02

### 新增
- ClassCacheManager 集成到批量工具

---

## [6.0.40] - 2026-01-15 16:56

### 新增
- 重命名操作自动触发缓存失效
- `clear_class_cache` MCP 工具用于手动清除缓存

---

## [6.0.39] - 2026-01-15 16:38

### 新增
- **ClassCacheManager** 优化批量类源码获取
- 增强的加载状态消息与进度指示
- 缓存操作进行中返回 `LOADING` 状态

---

## [6.0.38] - 2026-01-15 16:21

### 新增
- ClassCacheManager 初始实现用于 `batch_get_class_source`

---

## [6.0.37] - 2026-01-15 15:17

### 变更
- 更新 Python MCP 工具定义以支持 AI 友好的 strings API

---

## [6.0.36] - 2026-01-15 15:13

### 新增
- 所有日志添加 `[JAI]` 前缀和时间戳
- 改进日志可读性便于调试

---

## [6.0.35] - 2026-01-15 15:05

### 新增
- **AI 友好的 strings API，支持 4 种模式**：
  - `summary`: 概览与关键计数
  - `list`: 所有字符串名称列表
  - `search`: 按关键字搜索字符串
  - `get`: 按名称/ID 获取特定字符串

---

## [6.0.34] - 2026-01-15 15:00

### 修复
- `get_strings` 性能优化 - 避免加载所有文件内容

---

## [6.0.33] - 2026-01-15 14:38

### 修复
- 移除误导性的 `progress_percent`
- 为 ResourceCacheManager 添加准确的健康监控

---

## [6.0.32] - 2026-01-15 14:35

### 新增
- ResourceCacheManager 综合健康监控
- 缓存状态端点用于调试

---

## [6.0.31] - 2026-01-15 14:31

### 新增
- 使用 ResourceCacheManager 实现 100% 自动化的 `get_strings`
- 后台资源缓存

---

## [6.0.30] - 2026-01-15 14:28

### 修复
- 重写 `handleStrings` 为纯非阻塞模式
- 消除 EDT 阻塞问题

---

## [6.0.29] - 2026-01-15 14:24

### 新增
- `getOpenedResourceTabs` 详细日志用于诊断

---

## [6.0.28] - 2026-01-15 14:11

### 新增
- 混合资源加载（GUI 标签页 + 非阻塞 EDT 回退）

---

## [6.0.27] - 2026-01-15 01:49

### 变更
- 改进 `get_strings` TAB 访问状态消息

---

## [6.0.26] - 2026-01-15 01:46

### 新增
- 基于 GUI 标签页的资源访问（消除 `loadContent` 阻塞）

---

## [6.0.25] - 2026-01-15 01:32

### 修复
- 将 `ctx.future()` 异步替换为同步 `Future.get(timeout)`

---

## [6.0.24] - 2026-01-15 01:12

### 修复
- Python `get_strings` 处理新响应格式

---

## [6.0.23] - 2026-01-15 01:02

### 修复
- 异步资源加载使用专用单线程执行器

---

## [6.0.22] - 2026-01-15 00:52

### 新增
- 异步 HTTP 资源加载，60 秒超时

---

## [6.0.21] - 2026-01-15 00:47

### 修复
- 跳过 `get_strings` 中的 `resources.arsc` 解析以防止服务器挂起

---

## [6.0.20] - 2026-01-15 00:32

### 变更
- 恢复原始同步加载
- 移除后台缓存（稳定性问题）

---

## [6.0.19] - 2026-01-15 00:23

### 变更
- 恢复 `get_strings` 原始行为并支持变体

---

## [6.0.18] - 2026-01-15 00:12

### 修复
- `get_strings` 内容加载添加每文件 5 秒超时

---

## [6.0.17] - 2026-01-14 23:54

### 新增
- O(1) 预计算 `strings.xml` 缓存

---

## [6.0.16] - 2026-01-14 23:38

### 新增
- **ResourceCacheManager** 统一资源缓存
- 大型 APK 后台预加载

---

## [6.0.15] - 2026-01-14 23:24

### 新增
- 大型 APK 的 `get_strings` 后台缓存

---

## [6.0.14] - 2026-01-14 23:04

### 修复
- `get_strings` 超时问题，采用流式分页

---

## [6.0.13] - 2026-01-14 21:22

### 新增
- 完整的 Docker 和本地部署文档
- 数据卷参考指南

---

## [6.0.12] - 2026-01-14 20:45

### 新增
- 快速失败搜索锁与重试提示
- 并发搜索操作返回 `BUSY` 响应

---

## [6.0.11] - 2026-01-14 20:37

### 新增
- **全局 JadxSearchLock** 用于线程安全搜索操作
- 防止并发请求导致搜索结果损坏

---

## [6.0.10] - 2026-01-14 20:15

### 修复
- 移除 `searchByCode` 的 MAX_SCAN 限制

### 新增
- JADX 插件 UI 显示版本号

---

## [6.0.9] - 2026-01-14 19:51

### 变更
- 版本号使用 'dev' 占位符（CI 构建时替换）

---

## [6.0.7] - 2026-01-14 17:09

### 变更
- 拆分 Docker 基础镜像加速 CI 构建
- 构建时间减少 60%

---

## [6.0.6] - 2026-01-13 18:03

### 修复
- Maven shade 插件警告抑制
- 过滤 `module-info.class` 和签名文件
- 使用 `ServicesResourceTransformer` 合并 SPI

---

## [6.0.5] - 2026-01-13 17:40

### 新增
- **批量获取工具**：
  - `batch_get_class_source`
  - `batch_get_method_by_name`

---

## [6.0.4] - 2026-01-13 16:28

### 新增
- Docker 部署环境变量支持
- `JADX_HOST`, `JADX_PORT`, `JADX_MCP_AUTH_TOKEN`

---

## [6.0.3] - 2026-01-13 11:15

### 变更
- 文档清理与整合
- 所有代码注释翻译为英文
- 统一 `.gitignore` 配置

---

## [6.0.2] - 2026-01-12 21:45

### 新增
- **多实例 JADX 支持** - 连接多个 JADX 实例
- **统一设置面板** 在 JADX GUI 中配置插件
- 所有 MCP 工具支持 `instance_id` 参数
- 实例管理工具：`list_jadx_instances`, `add_jadx_instance` 等

---

## [6.0.1] - 2026-01-12 16:59

### 修复
- CI 从 git tag 同步版本号到 `pom.xml`

### 变更
- 从 [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp) fork
- 版本号升级到 6.0.x 系列

---

## Fork 前历史

v6.0.1 之前的变更请查看 [原始仓库](https://github.com/zinja-coder/jadx-ai-mcp)。
