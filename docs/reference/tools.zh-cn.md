# MCP 工具完整参考

[English](tools.md) | **简体中文**

---

## 📊 工具可用性矩阵

> ✅ 完全支持 | ⚠️ 部分支持 | ❌ 不适用 | 🔄 返回 NOT_APPLICABLE

| 工具 | APK | JAR | AAR | DEX | 说明 |
|:-----|:---:|:---:|:---:|:---:|:-----|
| **通用分析工具** |
| `get_file_info` | ✅ | ✅ | ✅ | ✅ | 推荐首先调用，自动识别文件类型 |
| `get_class_source` | ✅ | ✅ | ✅ | ✅ | 获取类源码 |
| `get_method_by_name` | ✅ | ✅ | ✅ | ✅ | 获取方法源码 |
| `get_class_info` | ✅ | ✅ | ✅ | ✅ | 类结构（继承、接口、成员数） |
| `get_method_signature` | ✅ | ✅ | ✅ | ✅ | 方法签名（Frida 兼容） |
| `get_methods_of_class` | ✅ | ✅ | ✅ | ✅ | 列出类的所有方法 |
| `get_fields_of_class` | ✅ | ✅ | ✅ | ✅ | 列出类的所有字段 |
| `get_method_callees` | ✅ | ✅ | ✅ | ✅ | 方法调用的其他方法 |
| `get_all_classes` | ✅ | ✅ | ✅ | ✅ | 列出所有类（分页） |
| `get_package_classes` | ✅ | ✅ | ✅ | ✅ | 按包前缀获取类 |
| `fetch_current_class` | ✅ | ✅ | ✅ | ✅ | 获取当前选中的类 |
| `get_selected_text` | ✅ | ✅ | ✅ | ✅ | 获取选中的文本 |
| **搜索工具** |
| `search_classes_by_keyword` | ✅ | ✅ | ✅ | ✅ | 按关键字搜索类 |
| `search_method_by_name` | ✅ | ✅ | ✅ | ✅ | 按方法名搜索 |
| `search_native_methods` | ✅ | ❌ | ✅ | ✅ | 搜索 native 方法（JNI） |
| **交叉引用工具** |
| `get_xrefs` | ✅ | ✅ | ✅ | ✅ | 查找引用（类/方法/字段），通过 `target_type` 参数指定 |
| `batch_get_xrefs` | ✅ | ✅ | ✅ | ✅ | 批量查找引用（最多 10 个） |
| **批量工具** |
| `batch_get_class_source` | ✅ | ✅ | ✅ | ✅ | 批量获取类源码（最多 20 个） |
| `batch_get_method_by_name` | ✅ | ✅ | ✅ | ✅ | 批量获取方法（最多 20 个） |
| **Android 专用工具** |
| `get_android_manifest` | ✅ | 🔄 | ✅ | ❌ | 获取 AndroidManifest.xml |
| `get_main_activity_class` | ✅ | 🔄 | ✅ | ❌ | 获取主 Activity |
| `get_main_application_classes_names` | ✅ | 🔄 | ✅ | ❌ | 主应用类名列表 |
| `get_main_application_classes_code` | ✅ | 🔄 | ✅ | ❌ | 主应用类源码 |
| `get_strings` | ✅ | 🔄 | ✅ | ❌ | 字符串资源（strings.xml） |
| `get_smali_of_class` | ✅ | ❌ | ✅ | ✅ | Smali 字节码 |
| **JAR 专用工具** |
| `jar_get_manifest` | 🔄 | ✅ | 🔄 | 🔄 | 读取 MANIFEST.MF |
| `jar_get_services` | 🔄 | ✅ | 🔄 | 🔄 | 读取 SPI 服务 |
| `jar_get_entry_points` | 🔄 | ✅ | 🔄 | 🔄 | 发现入口点 |
| `jar_get_dependencies` | 🔄 | ✅ | 🔄 | 🔄 | 分析嵌入依赖 |
| `jar_get_bytecode` | ✅ | ✅ | ✅ | ✅ | 类字节码（类似 javap） |
| **统一配置工具** |
| `get_config_strings` | ✅ | ✅ | ✅ | ❌ | APK: strings.xml 概要, JAR: properties 文件 |
| **资源工具** |
| `get_all_resource_file_names` | ✅ | ✅ | ✅ | ❌ | 列出所有资源文件 |
| `get_resource_file` | ✅ | ✅ | ✅ | ❌ | 获取资源文件内容 |
| **重命名工具** |
| `rename_class` | ✅ | ✅ | ✅ | ✅ | 重命名类（全局生效） |
| `rename_method` | ✅ | ✅ | ✅ | ✅ | 重命名方法并更新所有调用点 |
| `rename_field` | ✅ | ✅ | ✅ | ✅ | 重命名字段并更新所有引用 |
| `rename_package` | ✅ | ✅ | ✅ | ✅ | 重命名包及其包含的所有类 |
| **实例管理工具** |
| `list_jadx_instances` | ✅ | ✅ | ✅ | ✅ | 列出所有实例 |
| `add_jadx_instance` | ✅ | ✅ | ✅ | ✅ | 添加新实例 |
| `remove_jadx_instance` | ✅ | ✅ | ✅ | ✅ | 移除实例 |
| `set_default_jadx_instance` | ✅ | ✅ | ✅ | ✅ | 设置默认实例 |
| `get_jadx_instance_info` | ✅ | ✅ | ✅ | ✅ | 获取实例详情 |
| `health_check_jadx_instances` | ✅ | ✅ | ✅ | ✅ | 健康检查 |
| `clear_class_cache` | ✅ | ✅ | ✅ | ✅ | 清除类缓存 |
| **状态与传输工具** |
| `get_decompile_status` | ✅ | ✅ | ✅ | ✅ | 获取反编译状态和指标 |
| `create_transfer_token` | ✅ | ✅ | ✅ | ✅ | 创建 HTTP 下载令牌，绕过 MCP 大小限制 |

---

## 🔍 工具详细说明

#### 通用分析工具

| 工具 | 参数 | 说明 |
|:-----|:-----|:-----|
| `get_file_info()` | `instance_id?` | **推荐首先调用**。返回文件类型、类数量、推荐使用的工具 |
| `fetch_current_class()` | `chunk=0`, `instance_id?` | 获取 JADX-GUI 当前活动类。**大响应自动分片** |
| `get_selected_text()` | `instance_id?` | 获取 JADX-GUI 代码视图中选中的文本 |
| `get_class_source(class_name)` | `class_name`, `chunk=0`, `instance_id?` | 获取完整类源码。**大响应自动分片** |
| `get_method_by_name(class_name, method_name)` | `class_name`, `method_name`, `instance_id?` | 获取方法源码 |
| `get_class_info(class_name)` | `class_name`, `instance_id?` | 类结构：继承、接口、方法数、字段数、native 方法列表 |
| `get_method_signature(class_name, method_name)` | `class_name`, `method_name`, `instance_id?` | 返回 Frida 兼容签名 (`frida_overload`) |
| `get_methods_of_class(class_name)` | `class_name`, `instance_id?` | 返回 JSON：`is_static`, `is_native`, `overload_count` |
| `get_fields_of_class(class_name)` | `class_name`, `instance_id?` | 返回 JSON：`type_frida` 字段 |
| `get_method_callees(class_name, method_name)` | `class_name`, `method_name`, `instance_id?` | 该方法调用的所有方法 |
| `get_all_classes(offset, count)` | `offset=0`, `count=0`, `instance_id?` | 分页列出所有类 |
| `get_package_classes(package, auto)` | `package?`, `auto=false`, `include_inner=true`, `offset=0`, `count=100`, `instance_id?` | `auto=true` 自动检测主包 |

#### 搜索工具

| 工具 | 参数 | 说明 |
|:-----|:-----|:-----|
| `search_classes_by_keyword(keyword)` | `search_term`, `package=""`, `exclude=""`, `search_in="code"`, `offset=0`, `count=20`, `instance_id?` | `search_in`: `class`/`method`/`field`/`code`/`comment` |
| `search_method_by_name(method_name)` | `method_name`, `offset=0`, `count=50`, `instance_id?` | 全局方法搜索 |
| `search_native_methods(package)` | `package=""`, `offset=0`, `count=50`, `instance_id?` | 搜索 JNI native 方法 |

#### 交叉引用工具

| 工具 | 参数 | 说明 |
|:-----|:-----|:-----|
| `get_xrefs(target_type, class_name)` | `target_type`（`class`/`method`/`field`），`class_name`，`member_name?`，`offset=0`，`count=20`，`instance_id?` | 查找类、方法或字段的所有引用 |
| `batch_get_xrefs(targets)` | `targets[]` (格式: `type:class:member`), `instance_id?` | 最多 10 个目标 |

**`get_xrefs` 调用示例：**

```python
# 查找类的所有使用位置
get_xrefs(target_type="class", class_name="com.example.Helper")

# 查找方法的所有调用者
get_xrefs(target_type="method", class_name="com.example.MyClass", member_name="myMethod")

# 查找字段的所有引用
get_xrefs(target_type="field", class_name="com.example.MyClass", member_name="secretKey")
```

**`batch_get_xrefs` 目标格式：** `"type:class_name:member_name"`（class 类型省略 member_name）

```python
batch_get_xrefs(targets=[
    "class:com.example.Helper",
    "method:com.example.Auth:login",
    "field:com.example.Config:API_KEY"
])
```

#### 批量工具

| 工具 | 参数 | 说明 |
|:-----|:-----|:-----|
| `batch_get_class_source(class_names)` | `class_names[]`, `chunk=0`, `force=False`, `instance_id?` | 最多 20 个类。智能大小管理，支持分片 |
| `batch_get_method_by_name(methods)` | `methods[]` (格式: `class:method`), `chunk=0`, `force=False`, `instance_id?` | 最多 20 个方法。智能大小管理，支持分片 |

#### JAR 专用工具

| 工具 | 参数 | 说明 |
|:-----|:-----|:-----|
| `jar_get_manifest()` | `instance_id?` | 读取 META-INF/MANIFEST.MF，返回 Main-Class、版本等 |
| `jar_get_services()` | `instance_id?` | 读取 META-INF/services/*，发现 SPI 服务 |
| `jar_get_entry_points()` | `instance_id?` | 发现入口点：Main-Class、@SpringBootApplication、main() |
| `jar_get_dependencies()` | `instance_id?` | 分析依赖：pom.properties、Class-Path、BOOT-INF/lib |
| `jar_get_bytecode(class_name)` | `class_name`, `instance_id?` | 类字节码结构（类似 javap） |

#### Android 专用工具

| 工具 | 参数 | 说明 |
|:-----|:-----|:-----|
| `get_android_manifest()` | `instance_id?` | 获取 AndroidManifest.xml |
| `get_main_activity_class()` | `instance_id?` | 从 Manifest 获取主 Activity |
| `get_main_application_classes_names()` | `instance_id?` | 列出主应用类名（排除库类） |
| `get_main_application_classes_code()` | `offset=0`, `count=0`, `instance_id?` | 主应用类源码（建议 count=1-5 避免超时） |
| `get_strings(mode, query, key)` | `mode="summary"`, `query?`, `key?`, `locale="values"`, `offset=0`, `limit=50`, `instance_id?` | 模式: `summary`/`list`/`search`/`get` |
| `get_smali_of_class(class_name)` | `class_name`, `chunk=0`, `instance_id?` | Dalvik 字节码。**大响应自动分片** |

#### 重命名工具

所有重命名操作都会触发 30 秒 ClassCacheManager 冷却，连续快速重命名会被防抖处理。

| 工具 | 参数 | 说明 |
|:-----|:-----|:-----|
| `rename_class(class_name, new_name)` | `class_name`, `new_name`, `instance_id?` | 重命名类（全局生效） |
| `rename_method(class_name, method_name, new_name)` | `class_name`, `method_name`, `new_name`, `instance_id?` | 重命名方法并更新所有调用点 |
| `rename_field(class_name, field_name, new_name)` | `class_name`, `field_name`, `new_name`, `instance_id?` | 重命名字段并更新所有引用 |
| `rename_package(old_package_name, new_package_name)` | `old_package_name`, `new_package_name`, `instance_id?` | 重命名整个包结构 |

#### 实例管理工具

| 工具 | 参数 | 说明 |
|:-----|:-----|:-----|
| `list_jadx_instances()` | - | 列出所有连接的实例 |
| `add_jadx_instance(host, port)` | `host`, `port`, `name?`, `token?` | 动态添加实例 |
| `remove_jadx_instance(name)` | `name` | 移除实例 |
| `set_default_jadx_instance(name)` | `name` | 设置默认实例 |
| `get_jadx_instance_info(name)` | `name` | 获取实例详情 |
| `health_check_jadx_instances()` | - | 检查所有实例健康状态 |
| `clear_class_cache()` | `instance_id?` | 清除类缓存（30秒冷却） |

#### 状态与传输工具

| 工具 | 参数 | 说明 |
|:-----|:-----|:-----|
| `get_decompile_status()` | `instance_id?` | 获取缓存命中率、内存、线程指标 |
| `create_transfer_token()` | `operation="download"`, `resource_type="batch_classes"`, `timeout_seconds=120`, `params?`, `instance_id?` | 创建 HTTP 下载令牌，绕过 MCP 大小限制 |

---

## ⚡ 性能建议

| 场景 | 推荐做法 |
|:-----|:---------|
| 首次分析 | 先调用 `get_file_info()` 了解文件类型 |
| 搜索代码 | 优先使用 `search_in="class"` 或 `"method"`，避免 `"code"` |
| 大量类 | 使用 `batch_get_class_source` 减少请求次数 |
| 检查状态 | 调用 `get_decompile_status()` 检查缓存命中率 |

---

## 🧩 响应分片

大响应（>8KB）会自动分片，防止 MCP 客户端截断。

| 场景 | 行为 |
|:-----|:-----|
| 响应 ≤8KB | 直接返回完整内容 |
| 响应 >8KB | 返回首片 + `_chunking` 元数据 |

**分片元数据示例：**
```json
{
  "content": "...前 8KB...",
  "_chunking": {
    "enabled": true,
    "total_size": 45000,
    "total_chunks": 6,
    "current_chunk": 1,
    "has_more": true,
    "next_chunk": 2
  }
}
```

**获取剩余分片：**
```python
# 如果 _chunking.has_more == true，使用 chunk=N 继续调用
result = get_smali_of_class(class_name="...", chunk=2)
result = batch_get_class_source(class_names=["..."], chunk=2)
```

**受影响的工具：** `get_class_source`, `get_smali_of_class`, `get_android_manifest`, `fetch_current_class`, `get_main_activity_class`, `get_resource_file`, `batch_get_class_source`, `batch_get_method_by_name`

---

## 🚦 智能批量大小管理

`batch_get_class_source` 和 `batch_get_method_by_name` 包含智能大小管理，防止过大响应。

### 分层策略

| 响应大小 | 行为 | 操作 |
|:---------|:-----|:-----|
| <20KB | 直接执行 | 无警告 |
| 20-50KB | 执行并警告 | 返回 `_performance_warning` 字段 |
| >50KB | 预检失败 | 返回 `BATCH_TOO_LARGE` 错误 |

### BATCH_TOO_LARGE 错误响应

当批量请求过大时，会收到：

**`batch_get_class_source` 错误示例：**
```json
{
  "error": "BATCH_TOO_LARGE",
  "estimated_size_bytes": 128000,
  "estimated_size_kb": 125.0,
  "classes_count": 15,
  "class_summaries": [
    {
      "class_name": "com.example.LargeClass",
      "method_count": 150,
      "field_count": 80,
      "is_abstract": false
    }
  ],
  "suggestions": {
    "option1": "将批量大小减少到最多 2-3 个类",
    "option2": "使用 get_class_info + get_method_by_name 进行有针对性的分析",
    "option3": "使用 get_class_source 单独获取类（支持分片）",
    "option4": "添加 force=True 强制执行: batch_get_class_source(class_names=['...'], force=True)"
  }
}
```

**`batch_get_method_by_name` 错误示例：**
```json
{
  "error": "BATCH_TOO_LARGE",
  "estimated_size_bytes": 95000,
  "estimated_size_kb": 92.8,
  "methods_count": 12,
  "method_summaries": [
    {
      "class_name": "com.example.Service",
      "method_name": "processData",
      "line_count": 450
    }
  ],
  "suggestions": {
    "option1": "将批量大小减少到最多 2-3 个方法",
    "option2": "使用 get_method_by_name 单独获取方法",
    "option3": "添加 force=True 强制执行: batch_get_method_by_name(methods=['...'], force=True)"
  }
}
```

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|:-----|:-----|:-------|:-----|
| `class_names` | list[str] | 必需 | 类名列表（最多 20 个） |
| `chunk` | int | 0 | 续传分片编号（0=首次请求） |
| `force` | bool | False | 绕过大小检查，强制执行 |
| `instance_id` | str | None | 目标 JADX 实例 |

### 使用示例

**示例 1: 批量获取类源码**
```python
# 正常批量请求
result = batch_get_class_source(["com.example.A", "com.example.B"])

# 处理 BATCH_TOO_LARGE 错误
result = batch_get_class_source(["Large1", "Large2", "Large3"])
if result.get("error") == "BATCH_TOO_LARGE":
    # 选项1: 查看类摘要
    for summary in result["class_summaries"]:
        print(f"{summary['class_name']}: {summary['method_count']} 个方法")

    # 选项2: 减少批量大小
    result = batch_get_class_source(["Large1"])

    # 选项3: 强制执行
    result = batch_get_class_source(["Large1", "Large2"], force=True)

# 处理分片响应
if result.get("_chunking", {}).get("has_more"):
    next_result = batch_get_class_source(
        class_names=["com.example.A"],
        chunk=result["_chunking"]["next_chunk"]
    )
```

**示例 2: 批量获取方法源码**
```python
# 批量请求多个方法
methods = [
    "com.example.Auth:login",
    "com.example.Auth:logout",
    "com.example.Network:sendRequest"
]
result = batch_get_method_by_name(methods)

# 处理 BATCH_TOO_LARGE 错误
if result.get("error") == "BATCH_TOO_LARGE":
    print(f"预估大小: {result['estimated_size_kb']} KB")
    # 减少批量或强制执行
    result = batch_get_method_by_name(methods[:2], force=True)

# 处理结果
for method in result.get("methods", []):
    if method["found"]:
        print(f"{method['class_name']}:{method['method_name']}")
        # 分析 method["code"]

# 处理分片
if result.get("_chunking", {}).get("has_more"):
    next_result = batch_get_method_by_name(
        methods=methods,
        chunk=result["_chunking"]["next_chunk"]
    )
```

---
