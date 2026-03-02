# JADX MCP Server AI 自动化测试提示词

[English](ai-prompts.md) | **简体中文**

---

本文档提供用于 AI 辅助测试 JADX MCP Server 的完整提示词模板。

## 使用方法

将下方提示词复制到 AI 对话中，即可开始自动化测试流程。

## ❗ 测试前环境准备（重要）

为确保测试结果准确，**必须在无缓存状态下启动 JADX**：

### 清除 JADX 缓存的方法：

```bash
# macOS/Linux
rm -rf ~/.cache/jadx-gui/

# Windows
rmdir /s /q %USERPROFILE%\.cache\jadx-gui
```

### 测试启动流程：

1. 关闭所有 JADX-GUI 实例
2. 执行上述命令清除缓存
3. 重新启动 JADX-GUI 并打开目标 APK
4. **不要等待反编译完成**，立即开始测试
5. 通过 `get_decompile_status` 监控反编译进度

> ➡️ 这样可以测试无缓存和有缓存两种场景的性能差异

---

## 测试提示词

```
请对 JADX MCP Server 项目进行完整严格的测试，需要达到100%通过率。

## 测试目标
1. 所有MCP工具的功能正确性验证（排除debug_*工具）
2. 边界条件测试（offset/count极限值）
3. 异常输入测试（不存在的类/方法/字段、空输入等）
4. 翻页机制完整性验证（首页、中间页、最后一页）
5. 批量操作正确性验证（部分成功、全部失败等）
6. 性能基准验证（class/method/field搜索<1秒，code搜索<60秒）
7. 结果一致性验证（相同输入多次调用结果一致）
8. 缓存机制验证（无缓存冷启动 vs 有缓存热启动）
9. 缓存清除和失效验证（clear_class_cache、重命名后自动失效）

## 测试阶段

### 阶段1：搜索类工具测试（约25个用例）
需要测试的工具：
- search_classes_by_keyword
  - search_in参数：class, method, field, code, comment, 组合
  - count边界：1, 10, 50, 100, 200
  - offset翻页：首页, 中间, 末页, 超出范围
  - 过滤器：package, exclude, 组合
  - 特殊输入：单字符, 特殊字符, 中文, 不存在的词
  - 超时测试：code/comment搜索的60秒超时验证
  - Early Exit验证：常见词是否触发早期退出
  - 重复测试：相同输入3次验证一致性
- search_method_by_name
  - 不同方法名：onClick, get, init, setup, parse
  - 完整翻页到最后
  - 边界和空结果测试

### 阶段2：P0/P1核心功能测试（约25个用例）
需要测试的工具：
- get_class_source：正常类, 不存在的类, 系统类
- batch_get_class_source：正常批量, 全部不存在, 部分存在, 空列表
- get_method_by_name：成功获取, 构造函数<init>, 不存在的方法
- get_android_manifest：获取完整Manifest
- get_class_info：验证继承关系、方法数、字段数
- get_xrefs_to_class：交叉引用和翻页
- get_xrefs_to_method：成功获取引用
- get_xrefs_to_field：字段引用测试
- get_all_classes：翻页测试（首页、末页）
- get_strings：所有模式（summary, list, search, get）和locale切换
- get_methods_of_class, get_fields_of_class：完整列表
- get_decompile_status：状态检查

### 阶段3：P2功能测试（约10个用例）
需要测试的工具：
- get_smali_of_class：小类, 中类, 大类, 不存在的类
- get_method_signature：签名获取
- get_method_callees：有调用和无调用的方法
- get_main_activity_class：主Activity
- get_main_application_classes_names
- get_all_resource_file_names：翻页测试
- get_resource_file：正常资源, 不存在的资源

### 阶段4：批量操作和翻页系统验证（约10个用例）
- batch_get_method_by_name：正常批量, 边界(1个/20个), 超限, 部分存在, 空列表
- batch_get_xrefs：混合类型(class+method+field), 全部不存在, 单个target
- 系统性翻页：3个工具的最后一页验证
  - get_all_classes最后一页
  - get_all_resource_file_names最后一页
  - get_xrefs_to_class最后一页

### 阶段5：并发和极限测试（约10个用例）
- check_instance_status：实例状态
- count极限值：count=200, count=500（超出限制）
- offset极限值：offset超出total
- 空输入测试：空字符串search_term

### 阶段6：缓存测试（约15个用例）

#### 6.1 无缓存测试（冷启动）
- 清除JADX缓存后重新启动
- 测试 search_classes_by_keyword(search_in=code)：预期60秒超时
- 测试 search_classes_by_keyword(search_in=class)：预期0秒
- 记录首次code搜索的执行时间
- 验证 get_decompile_status：应显示loading状态和进度

#### 6.2 有缓存测试（热启动）
- 不清除缓存，使用已反编译的APK
- 测试 search_classes_by_keyword(search_in=code)：预期比无缓存快
- 测试同一类源码多次获取：验证缓存命中
- 重复3次相同搜索：验证结果100%一致

#### 6.3 缓存清除功能测试
- 调用 clear_class_cache
- 验证30秒全局冷却机制
- 在30秒内再次调用：应返回cooldown_remaining_seconds
- 30秒后再次调用：应成功清除

#### 6.4 资源缓存测试
- 首次调用 get_strings：触发资源缓存加载
- 验证 status=loading_started 或 status=loading
- 等待加载完成后再次调用：应立即返回结果
- 验证不同locale的缓存独立性

#### 6.5 缓存一致性验证
- 使用 rename_class 重命名一个类
- 验证缓存是否自动失效
- 获取重命名后的类源码：应反映新名称
- 验证 xrefs 是否更新

## 缓存测试环境准备

### 无缓存测试步骤：
1. 关闭JADX-GUI
2. 删除 ~/.cache/jadx-gui/ 目录（或等效路径）
3. 重新打开APK
4. 立即开始测试（不等待反编译完成）

### 有缓存测试步骤：
1. 确保JADX-GUI已完全反编译APK
2. 验证 get_decompile_status 显示 status=ready
3. 然后开始测试

## 缓存测试验证标准

| 场景 | 无缓存预期 | 有缓存预期 |
|------|----------|----------|
| class搜索 | 0秒 | 0秒 |
| method搜索 | 0秒 | 0秒 |
| field搜索 | 0秒 | 0秒 |
| code搜索 | 60秒超时 | 更快（取决于缓存） |
| comment搜索 | 60秒超时 | 更快（取决于缓存） |
| get_class_source | 可能较慢 | <1秒 |
| get_strings首次 | 触发加载 | 立即返回 |

## 验证标准

### 每个测试用例必须明确记录：
1. 测试工具名称
2. 输入参数
3. 预期结果
4. 实际结果
5. 通过/失败状态
6. **执行时间**（必须记录，单位：毫秒或秒）
7. 响应大小（如适用）

### 通过条件：
- ✅ 功能正确：返回预期数据
- ✅ 错误处理正确：返回明确的错误信息（404/400等）
- ✅ 翻页正确：has_more, next_offset, total等字段准确
- ✅ 响应完整：所有必需字段存在

### 失败条件：
- ❌ 功能异常：返回错误数据
- ❌ 程序崩溃：请求超时或无响应
- ❌ 字段缺失：响应缺少必需字段
- ❌ 逻辑错误：has_more/offset等计算错误

## 输出要求

### 为每个阶段生成：
1. 测试用例列表（表格形式，包含执行时间列）
2. 通过/失败统计
3. **执行时间统计**（最小/最大/平均）
4. 关键发现

### 最终汇总报告：
1. 总测试用例数
2. 总通过率
3. 工具覆盖率
4. 质量评估（A+/A/B/C）
5. 待改进项（如有）

## 注意事项

1. 每个阶段完成后才进入下一阶段
2. 发现失败用例时，优先深度测试相关功能
3. 所有测试结果必须是明确的成功或失败，不接受“待测试”状态
4. 相同测试重复3次验证稳定性
5. 记录所有边界情况的行为
6. **每个测试必须记录执行时间**

## 排除的工具（不需测试）

以下工具不在测试范围内：
- `debug_get_stack_frames` - 需要调试会话
- `debug_get_threads` - 需要调试会话
- `debug_get_variables` - 需要调试会话
- `fetch_current_class` - 依赖UI状态
- `get_selected_text` - 依赖UI状态

## 重要工具（必须深度测试）

以下工具为核心功能，需要最严格的测试：

### P0 核心工具（必测）
- `search_classes_by_keyword` - 搜索核心功能
- `search_method_by_name` - 搜索核心功能
- `get_class_source` - 反编译核心功能
- `get_method_by_name` - 方法获取核心功能
- `get_android_manifest` - APK分析入口
- `get_xrefs_to_class` - 交叉引用核心功能

### P1 高优先级工具（必测）
- `batch_get_class_source` - 批量操作
- `batch_get_method_by_name` - 批量操作
- `batch_get_xrefs` - 批量操作
- `get_class_info` - 类信息分析
- `get_strings` - 资源分析
- `get_all_classes` - 类列表功能

## 缓存相关工具多次测试要求

以下工具涉及缓存机制，**必须进行多次测试**：

| 工具 | 测试次数 | 测试要点 |
|------|---------|----------|
| `search_classes_by_keyword` (code/comment) | ×3 | 验证缓存命中后速度提升 |
| `get_class_source` | ×3 | 第1次可能较慢，后续应<1s |
| `get_strings` | ×3 | 首次触发加载，后续即时返回 |
| `get_smali_of_class` | ×2 | 缓存后应更快 |
| `get_decompile_status` | ×5 | 监控进度变化 |
| `clear_class_cache` | ×2 | 验证30秒冷却机制 |

### 缓存测试验证点

1. **首次调用**：记录执行时间作为基准
2. **第二次调用**：应明显快于首次（缓存命中）
3. **第三次调用**：应与第二次时间接近（稳定性）
4. **结果一致性**：所有调用结果必须100%一致

## 执行时间基准

| 操作类型 | 预期时间 | 警告阈值 |
|---------|---------|----------|
| search_in=class | <100ms | >500ms |
| search_in=method | <100ms | >500ms |
| search_in=field | <100ms | >500ms |
| search_in=code | <60s | 超时正常 |
| search_in=comment | <60s | 超时正常 |
| get_class_source | <1s | >3s |
| get_method_by_name | <1s | >3s |
| get_xrefs_to_* | <1s | >3s |
| batch_get_* | <3s | >10s |
| get_smali_of_class | <5s | >30s |
| 其他工具 | <1s | >3s |
```

---

## 测试用例预估

| 阶段 | 用例数 | 说明 |
|------|-------|------|
| 阶段1：搜索类 | 25 | 搜索功能全覆盖 |
| 阶段2：P0/P1 | 25 | 核心功能测试 |
| 阶段3：P2 | 10 | 次要功能测试 |
| 阶段4：批量翻页 | 10 | 系统性验证 |
| 阶段5：极限 | 10 | 边界条件 |
| 阶段6：缓存 | 15 | 缓存机制验证 |
| **总计** | **~95** | 完整覆盖 |

## 预期通过率

- **目标通过率**：100%
- **可接受通过率**：95%（允许边缘场景失败）
