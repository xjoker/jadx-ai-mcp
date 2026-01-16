# 更新日志

JADX-AI-MCP 的所有重要变更都记录在此文件中。

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 和 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 规范。

> 🔱 本更新日志涵盖从 [zinja-coder/jadx-ai-mcp](https://github.com/zinja-coder/jadx-ai-mcp) fork 后的所有变更。

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
