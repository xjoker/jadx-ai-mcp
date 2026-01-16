# MCP 工具列表 / MCP Tools Reference

[English](#english) | [简体中文](#简体中文)

---

## 简体中文

### 🔍 代码分析工具

| 工具 | 说明 |
|:-----|:-----|
| `get_class_source(class_name)` | 获取类源码 |
| `get_method_by_name(class_name, method_name)` | 获取方法源码 |
| `get_class_info(class_name)` | 获取类结构（继承、接口、成员数） |
| `get_method_signature(class_name, method_name)` | 获取方法签名（返回类型、参数） |
| `get_methods_of_class(class_name)` | 列出类的所有方法 |
| `get_fields_of_class(class_name)` | 列出类的所有字段 |
| `get_smali_of_class(class_name)` | 获取类的 Smali 代码 |
| `search_native_methods(package?)` | 🆕 搜索所有 native 方法 |

### 🔎 搜索工具

| 工具 | 说明 |
|:-----|:-----|
| `search_classes_by_keyword(keyword, package?, search_in?)` | 按关键字搜索类 |
| `search_method_by_name(method_name)` | 按方法名搜索 |
| `get_xrefs_to_class(class_name)` | 查找类的引用 |
| `get_xrefs_to_method(class_name, method_name)` | 查找方法的引用 |
| `get_method_callees(class_name, method_name)` | 查找方法调用的其他方法 |

### 📦 批量工具

| 工具 | 说明 |
|:-----|:-----|
| `batch_get_class_source(class_names)` | 批量获取类源码（最多 20 个） |
| `batch_get_method_by_name(methods)` | 批量获取方法（格式：class:method） |
| `batch_get_xrefs(targets)` | 批量查找引用 |

### 📄 资源工具

| 工具 | 说明 |
|:-----|:-----|
| `get_android_manifest()` | 获取 AndroidManifest.xml |
| `get_strings(mode?, query?)` | 获取字符串资源 |
| `get_main_activity_class()` | 获取主 Activity |
| `get_all_classes()` | 列出所有类 |
| `get_all_resource_file_names()` | 列出所有资源文件 |

### ✏️ 重命名工具

| 工具 | 说明 |
|:-----|:-----|
| `rename_class(class_name, new_name)` | 重命名类 |
| `rename_method(method_name, new_name)` | 重命名方法 |
| `rename_field(class_name, field_name, new_name)` | 重命名字段 |

### 🔗 实例管理工具

| 工具 | 说明 |
|:-----|:-----|
| `list_jadx_instances()` | 列出所有 JADX 实例 |
| `add_jadx_instance(host, port, name?)` | 添加新实例 |
| `set_default_jadx_instance(name)` | 设置默认实例 |
| `health_check_jadx_instances()` | 健康检查 |

---

## English

### 🔍 Code Analysis

| Tool | Description |
|:-----|:------------|
| `get_class_source(class_name)` | Get class source code |
| `get_method_by_name(class_name, method_name)` | Get method source |
| `get_class_info(class_name)` | Get class structure |
| `get_method_signature(class_name, method_name)` | Get method signature |
| `search_native_methods(package?)` | 🆕 Search all native methods |

### 🔎 Search

| Tool | Description |
|:-----|:------------|
| `search_classes_by_keyword(keyword, ...)` | Search classes by keyword |
| `get_xrefs_to_method(class_name, method_name)` | Find method references |

### 📦 Batch

| Tool | Description |
|:-----|:------------|
| `batch_get_class_source(class_names)` | Batch get sources (max 20) |
| `batch_get_method_by_name(methods)` | Batch get methods |

### 📄 Resources

| Tool | Description |
|:-----|:------------|
| `get_android_manifest()` | Get AndroidManifest.xml |
| `get_strings(mode?, query?)` | Get string resources |
| `get_main_activity_class()` | Get main Activity |

---

## 🔗 Related

- [完整 API 文档](MCP_CONFIG.md)
- [性能优化建议](FAQ.md#性能问题)
