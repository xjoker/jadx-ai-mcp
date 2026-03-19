# 多实例管理

[English](multi-instance.md) | **简体中文**

---

> 🔄 管理多个 JADX 实例，实现并行 APK 分析

## 概述

JADX MCP Server 支持同时连接多个 JADX 实例：

- **并行分析**：同时分析不同的 APK
- **版本对比**：比较同一应用的不同版本
- **团队协作**：每个成员使用独立实例

---

## 实例管理工具

| 工具 | 描述 |
|:-----|:-----|
| `list_jadx_instances` | 列出所有已连接实例 |
| `add_jadx_instance` | 动态添加新实例 |
| `remove_jadx_instance` | 移除实例 |
| `set_default_jadx_instance` | 设置默认实例 |
| `get_jadx_instance_info` | 获取实例详情 |
| `health_check_jadx_instances` | 检查所有实例健康状态 |

---

## 配置方式

### 静态实例（配置文件）

```toml
# jadx-config.toml
[[jadx_instances]]
name = "app-v1"
host = "192.168.1.10"
port = 8650
default = true

[[jadx_instances]]
name = "app-v2"
host = "192.168.1.11"
port = 8650
```

### 动态实例（运行时）

```python
# 运行时添加实例
add_jadx_instance(host="192.168.1.12", port=8650, name="dev-build")

# 切换默认实例
set_default_jadx_instance(name="dev-build")
```

---

## 指定实例

大多数工具支持 `instance_id` 参数：

```python
# 通过名称指定实例
get_class_source(class_name="com.example.Main", instance_id="app-v2")

# 跨实例对比
source_v1 = get_class_source(class_name="com.example.Main", instance_id="app-v1")
source_v2 = get_class_source(class_name="com.example.Main", instance_id="app-v2")
```

### 模糊匹配（v6.1.6+）

`instance_id` 支持模糊匹配 — 不需要精确的实例名称：

```python
# 通过 APK 包名匹配
get_class_source(class_name="...", instance_id="com.xingin.xhs")

# 通过部分包名匹配
get_class_source(class_name="...", instance_id="xingin")

# 通过应用显示名称匹配
get_class_source(class_name="...", instance_id="小红书")

# 通过部分实例名匹配
get_class_source(class_name="...", instance_id="xhs")
```

**匹配优先级：** 精确名称 → 精确包名 → 精确 JADX 名 → 精确应用名 → 部分匹配 → 文件名 → 版本号。

> **注意：** 模糊匹配仅返回已连接的实例。每个实例加载不同的应用 — 不存在跨实例自动切换。

---

## 实例状态

| 状态 | 说明 |
|:-----|:-----|
| `connected` | 健康，可接收请求 |
| `pending` | 已注册但尚未连接（启动中） |
| `disconnected` | 曾连接但已失联 |
| `degraded` | 已连接但内存不足或检测到 OOM |
| `auth_failed` | JADX 插件返回 401 — 检查 token 配置 |
| `error` | 其他错误状态 |

---

## 使用场景

### 版本差异分析

```
1. 在实例 "v1" 中加载 app-v1.apk
2. 在实例 "v2" 中加载 app-v2.apk
3. 让 AI："对比 v1 和 v2 中 MainActivity 的差异"
```

### 团队协作

```
Alice → jadx-1: 登录模块
Bob   → jadx-2: 支付模块
Carol → jadx-3: 网络层
```

---

## 相关文档

- [Docker Compose 部署](../deployment/docker-compose.zh-cn.md)
- [配置参考](../reference/configuration.zh-cn.md)
