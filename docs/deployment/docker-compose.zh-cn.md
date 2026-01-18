# Docker Compose 多实例部署

[English](docker-compose.md) | **简体中文**

---

> 🏗️ 多实例 JADX 部署，支持并行分析

## 概述

Docker Compose 支持：
- **并行 APK 分析**：同时分析多个 APK
- **团队协作**：每个成员有专用实例
- **版本对比**：比较不同版本的应用

---

## 架构

```mermaid
flowchart TB
    MCP[MCP Server :8651] --> J1[JADX #1 :8650<br/>app-v1.apk]
    MCP --> J2[JADX #2 :8660<br/>app-v2.apk]
    MCP --> J3[JADX #3 :8670<br/>dev.apk]
```

---

## 快速开始

```bash
# 克隆并进入目录
git clone https://github.com/xjoker/jadx-ai-mcp.git
cd jadx-ai-mcp/docker

# 创建 APK 目录
mkdir -p apks/jadx-1 apks/jadx-2 apks/jadx-3
mkdir -p config

# 启动所有服务
docker compose up -d
```

---

## 访问地址

| 服务 | 地址 |
|:-----|:-----|
| **JADX #1** | http://localhost:6080 |
| **JADX #2** | http://localhost:6081 |
| **JADX #3** | http://localhost:6082 |
| **MCP Server** | http://localhost:8651/mcp |

---

## 配置

创建 `config/jadx-config.toml`:

```toml
[[jadx_instances]]
name = "jadx-1"
host = "jadx-1"  # Docker 容器名
port = 8650
default = true

[[jadx_instances]]
name = "jadx-2"
host = "jadx-2"
port = 8650

[[jadx_instances]]
name = "jadx-3"
host = "jadx-3"
port = 8650
```

---

## 端口参考

| 组件 | noVNC | 插件 API |
|:-----|:------|:---------|
| JADX #1 | 6080 | 8650 |
| JADX #2 | 6081 | 8660 |
| JADX #3 | 6082 | 8670 |
| MCP Server | - | 8651 |

---

## 常用命令

```bash
# 查看所有日志
docker compose logs -f

# 查看特定服务
docker compose logs -f mcp-server

# 重启所有
docker compose restart

# 停止所有
docker compose down

# 停止并删除卷
docker compose down -v
```

---

## 扩展实例

添加更多 JADX 实例：

```yaml
jadx-4:
  image: xjoker/jadx-ai-mcp:latest
  ports:
    - "6083:6080"
    - "8680:8650"
  volumes:
    - ./apks/jadx-4:/apks:ro
    - jadx-4-cache:/root/.cache
```

---

## 🔗 相关文档

- [配置参考](../reference/configuration.zh-cn.md)
- [工具参考](../reference/tools.zh-cn.md)
