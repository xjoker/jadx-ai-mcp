# All-in-One 部署

[English](allinone.md) | **简体中文**

---

> 🐳 生产就绪的单容器部署，包含 JADX GUI、noVNC 和 MCP Server

## 概述

All-in-One 镜像包含：
- **JADX GUI** 及 MCP 插件
- **noVNC** 浏览器桌面访问
- **MCP Server** AI 客户端连接

---

## 快速启动

```bash
docker run -d --name jadx-ai-mcp \
  -p 6080:6080 \
  -p 8650:8650 \
  -p 8651:8651 \
  -v $(pwd)/apks:/apks \
  -v $(pwd)/config:/app/data/config \
  -v jadx-cache:/root/.cache \
  xjoker/jadx-ai-mcp:latest
```

---

## 端口说明

| 端口 | 服务 | 描述 |
|:-----|:-----|:-----|
| 6080 | noVNC | 浏览器桌面访问 |
| 8650 | Plugin API | JADX 插件 HTTP API |
| 8651 | MCP Server | LLM 客户端端点 |

---

## 访问地址

- **JADX 桌面**：http://localhost:6080
- **MCP 端点**：http://localhost:8651/mcp

---

## 卷挂载

| 卷 | 容器路径 | 用途 |
|:---|:---------|:-----|
| APK 文件 | `/apks` | 待分析的 APK |
| 配置 | `/app/data/config` | 配置文件 |
| 缓存 | `/root/.cache` | 反编译缓存 |
| GUI 设置 | `/root/.jadx-gui` | GUI 偏好 |

---

## 认证配置

生产环境建议启用认证：

```toml
# config/jadx-config.toml
[[users]]
name = "admin"
token = "your-secure-token"
is_admin = true
```

详见 [安全策略](../security/security.zh-cn.md)。

---

## 相关文档

- [Docker 部署](docker.zh-cn.md)
- [Docker Compose](docker-compose.zh-cn.md)
- [配置参考](../reference/configuration.zh-cn.md)
