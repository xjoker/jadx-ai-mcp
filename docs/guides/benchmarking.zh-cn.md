# 性能基准测试

使用基准测试运行器在优化前采集基线数据，并在重构后进行对比。

## 测量指标

- 插件 HTTP API 吞吐量、延迟、繁忙率和错误率
- MCP 工具层吞吐量、延迟、繁忙率和错误率
- 冷启动、热缓存和降级压力场景
- 轻量级前/后状态快照，来源于：
  - `/health`
  - `/apk-info`
  - `/decompile-status`
  - `/status.json`

## 默认工作流

所有基准测试都通过 Docker 执行。

```bash
benchmarks/run_in_container.sh --build --image jadx-ai-mcp:local-benchmark --label baseline-dev
```

默认假设：

- APK 从 `temp/` 目录挂载
- `temp/target.apk` 会被一体化容器自动加载
- 结果写入 `temp/benchmark-results/`

## 与历史运行对比

使用之前运行的 JSON 输出作为对比基线。

```bash
benchmarks/run_in_container.sh \
  --image jadx-ai-mcp:local-benchmark \
  --label after-optimization \
  --compare /results/20260311-120000_baseline-dev.json
```

如果启用了 MCP 认证，传入 token：

```bash
benchmarks/run_in_container.sh --mcp-auth-token your-token
```

如需专门调优代码搜索，使用 `benchmarks/code_search_focus.json` 中的精简矩阵：

```bash
benchmarks/run_in_container.sh \
  --image jadx-ai-mcp:local-benchmark \
  --config benchmarks/code_search_focus.json \
  --label code-search-focus
```

## 输出内容

每次运行生成：

- 包含完整指标和状态快照的原始 JSON 报告
- 当提供 `--compare` 时包含 JSON `compare` 部分
- Markdown 摘要表格
- 当提供 `--compare` 时包含 Markdown 对比报告

主要字段：

- `ok_rps`
- `latency_ms.p50/p95/p99`
- `busy_rate`
- `error_rate`
- 每个用例的状态码计数
- 前/后插件和 MCP 状态快照
- 基于 `ok_rps`、`p95`、`busy_rate` 和 `error_rate` 的对比 `verdict`（`pass` 或 `regression`）

负载名称：

- `metadata`：快速元数据查询
- `decompile`：源码/smali 获取
- `code_search_only`：仅 `search_in=code` 搜索
- `xref_only`：仅交叉引用端点
- `search_xref`：混合搜索 + 交叉引用负载
- `mixed`：模拟 AI 请求的代表性混合负载

## 固定样本模式

进行优化前后对比时，建议使用固定样本覆盖，确保两次运行命中相同的类和方法目标。

```json
{
  "sample_discovery": {
    "sample_override": {
      "primary_class": "com.example.MainActivity",
      "secondary_class": "com.example.Helper",
      "primary_method": "onCreate",
      "primary_field": "INSTANCE",
      "search_term": "onCreate",
      "package_filter": "com.example",
      "class_source_hint": "MainActivity"
    }
  }
}
```

仅 `primary_class` 和 `primary_method` 为必填项。未提供覆盖配置时，运行器会回退到自动发现模式，优先选择 APK 的主 Activity，然后再扫描更广泛的类列表。

## 注意事项

- `cold_start` 在预热场景开始前，对新启动的基准测试容器进行测量。
- `warm_cache` 和 `degraded_pressure` 有意复用同一个运行中的实例，以反映真实的稳态行为。
- 基准测试运行器会自动从已加载的文件中发现可用的类/方法对，因此既适用于仓库固定测试文件，也适用于 `temp/target.apk` 等大型真实 APK。
- MCP `INSTANCE_BUSY` 负载即使在客户端传输层报告结构化成功信封时，也会被归类为 `busy`。
