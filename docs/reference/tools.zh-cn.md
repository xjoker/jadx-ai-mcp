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
| `get_xrefs_to_class` | ✅ | ✅ | ✅ | ✅ | 查找类的引用 |
| `get_xrefs_to_method` | ✅ | ✅ | ✅ | ✅ | 查找方法的引用 |
| `get_xrefs_to_field` | ✅ | ✅ | ✅ | ✅ | 查找字段的引用 |
| **批量工具** |
| `batch_get_class_source` | ✅ | ✅ | ✅ | ✅ | 批量获取类源码（最多 20 个） |
| `batch_get_method_by_name` | ✅ | ✅ | ✅ | ✅ | 批量获取方法（最多 20 个） |
| `batch_get_xrefs` | ✅ | ✅ | ✅ | ✅ | 批量查找引用（最多 10 个） |
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
| `rename_class` | ✅ | ✅ | ✅ | ✅ | 重命名类 |
| `rename_method` | ✅ | ✅ | ✅ | ✅ | 重命名方法 |
| `rename_field` | ✅ | ✅ | ✅ | ✅ | 重命名字段 |
| `rename_package` | ✅ | ✅ | ✅ | ✅ | 重命名包 |
| **调试工具** |
| `debug_get_stack_frames` | ✅ | ❌ | ✅ | ✅ | 获取堆栈帧 |
| `debug_get_threads` | ✅ | ❌ | ✅ | ✅ | 获取线程信息 |
| `debug_get_variables` | ✅ | ❌ | ✅ | ✅ | 获取变量 |
| **实例管理工具** |
| `list_jadx_instances` | ✅ | ✅ | ✅ | ✅ | 列出所有实例 |
| `add_jadx_instance` | ✅ | ✅ | ✅ | ✅ | 添加新实例 |
| `remove_jadx_instance` | ✅ | ✅ | ✅ | ✅ | 移除实例 |
| `set_default_jadx_instance` | ✅ | ✅ | ✅ | ✅ | 设置默认实例 |
| `get_jadx_instance_info` | ✅ | ✅ | ✅ | ✅ | 获取实例详情 |
| `health_check_jadx_instances` | ✅ | ✅ | ✅ | ✅ | 健康检查 |
| `check_instance_status` | ✅ | ✅ | ✅ | ✅ | 检查实例忙碌状态 |
| `clear_class_cache` | ✅ | ✅ | ✅ | ✅ | 清除类缓存 |
| **状态监控工具** |
| `get_decompile_status` | ✅ | ✅ | ✅ | ✅ | 获取反编译状态和指标 |

---

## 🔍 工具详细说明

#### 通用分析工具

| 工具 | 参数 | 说明 |
|:-----|:-----|:-----|
| `get_file_info()` | `instance_id?` | **推荐首先调用**。返回文件类型、类数量、推荐使用的工具 |
| `get_class_source(class_name)` | `class_name`, `instance_id?` | 获取完整类源码 |
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

#### 批量工具

| 工具 | 参数 | 说明 |
|:-----|:-----|:-----|
| `batch_get_class_source(class_names)` | `class_names[]`, `instance_id?` | 最多 20 个类 |
| `batch_get_method_by_name(methods)` | `methods[]` (格式: `class:method`), `instance_id?` | 最多 20 个方法 |
| `batch_get_xrefs(targets)` | `targets[]` (格式: `type:class:member`), `instance_id?` | 最多 10 个目标 |

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
| `get_strings(mode, query, key)` | `mode="summary"`, `query?`, `key?`, `locale="values"`, `offset=0`, `limit=50`, `instance_id?` | 模式: `summary`/`list`/`search`/`get` |
| `get_smali_of_class(class_name)` | `class_name`, `instance_id?` | Dalvik 字节码 |

#### 重命名工具

| 工具 | 参数 | 说明 |
|:-----|:-----|:-----|
| `rename_class(class_name, new_name)` | `class_name`, `new_name`, `instance_id?` | 重命名类 |
| `rename_method(method_name, new_name)` | `method_name`, `new_name`, `instance_id?` | 重命名方法 |
| `rename_field(class_name, field_name, new_name)` | `class_name`, `field_name`, `new_name`, `instance_id?` | 重命名字段 |
| `rename_package(old_name, new_name)` | `old_package_name`, `new_package_name`, `instance_id?` | 重命名包 |

#### 实例管理工具

| 工具 | 参数 | 说明 |
|:-----|:-----|:-----|
| `list_jadx_instances()` | - | 列出所有连接的实例 |
| `add_jadx_instance(host, port)` | `host`, `port`, `name?`, `token?` | 动态添加实例 |
| `remove_jadx_instance(name)` | `name` | 移除实例 |
| `set_default_jadx_instance(name)` | `name` | 设置默认实例 |
| `get_jadx_instance_info(name)` | `name` | 获取实例详情 |
| `health_check_jadx_instances()` | - | 检查所有实例健康状态 |
| `check_instance_status(instance_name)` | `instance_name?` | 检查实例是否忙碌 |
| `clear_class_cache()` | `instance_id?` | 清除类缓存（30秒冷却） |
| `get_decompile_status()` | `instance_id?` | 获取缓存、内存、线程指标 |

---

## ⚡ 性能建议

| 场景 | 推荐做法 |
|:-----|:---------|
| 首次分析 | 先调用 `get_file_info()` 了解文件类型 |
| 搜索代码 | 优先使用 `search_in="class"` 或 `"method"`，避免 `"code"` |
| 大量类 | 使用 `batch_get_class_source` 减少请求次数 |
| 检查状态 | 调用 `get_decompile_status()` 检查缓存命中率 |

---
