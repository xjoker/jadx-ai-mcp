# JADX-AI-MCP Docker 部署指南

**简体中文** | [English](README.md)

提供两种 Docker 镜像以满足不同场景需求。

## 镜像

| 镜像 | 描述 | 大小 |
|------|------|------|
| `xjoker/jadx-ai-mcp` | All-in-One (JADX GUI + noVNC + MCP Server) | ~800MB |
| `xjoker/jadx-mcp-server` | 独立 MCP Server | ~100MB |

## 架构 (All-in-One)

```mermaid
flowchart LR
    subgraph Docker["Docker 容器"]
        Xvfb["Xvfb :99"]
        VNC["x11vnc :5900"]
        noVNC["noVNC :6080"]
        JADX["jadx-gui + Plugin"]
        MCP["MCP Server :8651"]
        API["Plugin API :8650"]
        
        Xvfb --> VNC --> noVNC
        Xvfb --> JADX
        JADX --> API
        MCP --> API
    end
    
    Browser["🌐 浏览器"] --> noVNC
    LLM["🤖 LLM 客户端"] --> MCP
```

## 快速开始

### All-in-One 镜像

**标准模式（图形界面 + AI）- 推荐：**

```bash
docker pull xjoker/jadx-ai-mcp:latest
docker run -d --name jadx-ai-mcp \
  -p 6080:6080 \
  -p 8651:8651 \
  -v $(pwd)/apks:/apks \
  -v jadx-cache:/root/.cache \
  xjoker/jadx-ai-mcp

# 访问地址
# - noVNC 图形界面: http://localhost:6080
# - MCP Server: http://localhost:8651/mcp
```

> **前提条件**：JADX 插件 API 端口 (8650) 仅在加载文件后才会启动。请先通过自动加载或 GUI 打开 APK/JAR 文件，再连接 MCP Server。

**无头模式（仅 AI，无图形界面）：**

```bash
docker run -d --name jadx-ai-mcp \
  -p 8651:8651 \
  -v $(pwd)/apks:/apks \
  -v jadx-cache:/root/.cache \
  xjoker/jadx-ai-mcp

# 访问地址
# - MCP Server: http://localhost:8651/mcp
```

**开发 / 多容器模式（所有端口 + 配置）：**

```bash
docker run -d --name jadx-ai-mcp \
  -p 6080:6080 \
  -p 8650:8650 \
  -p 8651:8651 \
  -v $(pwd)/apks:/apks \
  -v $(pwd)/config:/app/data/config \
  -v jadx-cache:/root/.cache \
  -v jadx-gui-cache:/root/.jadx-gui \
  xjoker/jadx-ai-mcp

# 访问地址
# - noVNC 图形界面: http://localhost:6080
# - Plugin API: http://localhost:8650
# - MCP Server: http://localhost:8651/mcp
```

### 卷挂载说明

| 卷 | 路径 | 用途 |
|----|------|------|
| APK 文件 | `/apks` | 挂载待分析的 APK 文件 |
| 配置 | `/app/data/config` | 配置文件 (jadx-config.toml) |
| 缓存 | `/root/.cache` | JADX 反编译缓存 (提速 10-50 倍) |
| GUI 设置 | `/root/.jadx-gui` | GUI 偏好设置持久化 |

> **提示**：首次对大型 APK 进行代码搜索会触发反编译（较慢），后续搜索会利用缓存快速响应。

### 环境变量参考

#### JADX 插件 (Java)

| 变量 | 说明 | 默认值 |
|:-----|:-----|:-------|
| `JADX_MCP_BIND_ADDRESS` | HTTP 服务绑定地址 | `127.0.0.1` |
| `JADX_MCP_PORT` | HTTP 服务端口 | `8650` |
| `JADX_MCP_AUTH_TOKEN` | 认证 Token | (无) |
| `JADX_MCP_AUTH_ENABLED` | 启用认证 | `false` |

> **重要**：多容器部署时需设置 `JADX_MCP_BIND_ADDRESS=0.0.0.0`。

#### MCP Server (Python)

| 变量 | 说明 | 默认值 |
|:-----|:-----|:-------|
| `JADX_MCP_HOST` | MCP Server 绑定地址 | `0.0.0.0` |
| `JADX_HOST` | 默认 JADX 插件主机 | `127.0.0.1` |
| `JADX_PORT` | 默认 JADX 插件端口 | `8650` |

### 独立 MCP Server

用于生产环境连接外部 JADX 实例：

**方式 1：使用配置文件**

```bash
# 创建配置
mkdir -p config
cat > config/jadx-config.toml << 'EOF'
[server]
host = "0.0.0.0"
port = 8651

[[jadx_instances]]
name = "jadx-1"
host = "192.168.1.10"
port = 8650
enabled = true
EOF

# 运行
docker run -d --name jadx-mcp-server \
  -p 8651:8651 \
  -v $(pwd)/config:/app/data/config \
  xjoker/jadx-mcp-server
```

> **Docker 网络说明**：当 MCP Server 容器需要连接宿主机上的 JADX 时，使用 `host.docker.internal` 作为主机地址。Linux 上需在 `docker run` 命令中添加 `--add-host=host.docker.internal:host-gateway`。在 `docker-compose.yaml` 中使用 `extra_hosts: ["host.docker.internal:host-gateway"]`。

**方式 2：使用环境变量**

```bash
docker run -d --name jadx-mcp-server \
  -p 8651:8651 \
  -e JADX_HOST=192.168.1.10 \
  -e JADX_PORT=8650 \
  -e JADX_MCP_AUTH_TOKEN=your-token \
  xjoker/jadx-mcp-server
```

**方式 3：命令行参数**

```bash
docker run -d --name jadx-mcp-server \
  -p 8651:8651 \
  xjoker/jadx-mcp-server \
  jadx_mcp_server --http --host 0.0.0.0 \
    --jadx-instances "192.168.1.10:8650:app-v1,192.168.1.11:8650:app-v2"
```

## 端口说明

| 端口 | 服务 | 是否必需？ | 访问来源 | 描述 |
|:----:|:-----|:---------:|:---------|:-----|
| **6080** | noVNC | 可选 | 浏览器 | Web VNC 桌面（仅 All-in-One）。无头模式可省略。 |
| **8650** | Plugin API | 否* | 容器内部 | JADX 插件 HTTP API。仅多容器或调试时暴露。 |
| **8651** | MCP Server | **必需** | AI 客户端 | **主要端点**，供 LLM 客户端（Claude、ChatGPT 等）访问。 |

> **\* 端口 8650** 仅在 MCP Server 独立容器运行时需要。单容器模式（All-in-One）中，MCP Server 通过内部 `localhost:8650` 连接。

## 配置

### 多用户认证

创建 `config/jadx-config.toml`：

```toml
[server]
host = "0.0.0.0"
port = 8651

[[users]]
name = "alice"
token = "token-alice-xxxxx"

[[users]]
name = "admin"
token = "token-admin-zzzzz"
is_admin = true

[defaults]
jadx_token = ""

[[jadx_instances]]
name = "local"
host = "127.0.0.1"
port = 8650
```

运行：

```bash
docker run -d -p 8651:8651 \
  -v $(pwd)/config:/app/data/config \
  xjoker/jadx-mcp-server \
  uv run jadx_mcp_server --http --host 0.0.0.0 --config /app/data/config/jadx-config.toml
```

### 权限与安全

设置了 `is_admin = true` 的用户拥有更高权限：

| 能力 | 管理员 | 普通用户 |
|------|--------|----------|
| 使用所有分析工具 | 是 | 是 |
| 查看自己的 JADX 实例 | 是 | 是 |
| 查看所有 JADX 实例 | 是 | 否 |
| 通过 AI 动态添加/移除实例 | 是 | 需要 `can_add_instances` |

如需允许普通用户动态管理实例，在配置中添加：

```toml
[security]
allow_dynamic_instances = true

[[users]]
name = "alice"
token = "token-alice-xxxxx"
can_add_instances = true
```

> **SSRF 风险警告**：启用 `allow_dynamic_instances` 后，用户可指示 AI 连接任意主机。请仅在可信环境中启用。管理员用户不受此设置限制，始终可以管理实例。

### 客户端认证连接

配置了 `[[users]]` 后，客户端必须携带 Bearer token。

**Claude Code CLI：**

```bash
claude mcp add --transport http jadx http://localhost:8651/mcp \
  --header "Authorization: Bearer token-alice-xxxxx"
```

**Claude Desktop**（`claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "jadx": {
      "type": "http",
      "url": "http://localhost:8651/mcp",
      "headers": {
        "Authorization": "Bearer token-alice-xxxxx"
      }
    }
  }
}
```

**OpenAI Codex**（`~/.codex/config.toml`）：

```toml
[mcp_servers.jadx]
url = "http://localhost:8651/mcp"
bearer_token_env_var = "JADX_MCP_TOKEN"
```

> Codex 不支持直接写入 token 值，必须通过 `bearer_token_env_var` 引用环境变量：
> ```bash
> export JADX_MCP_TOKEN="token-alice-xxxxx"
> ```

## 从源码构建

### 基础镜像（系统依赖）

All-in-One 镜像使用预构建的基础镜像以加速 CI 构建：

```bash
# 构建基础镜像（仅在系统依赖变更时需要）
docker build -t xjoker/jadx-ai-mcp-base:1.0 -f docker/Dockerfile.base .

# 推送到仓库（仅维护者）
docker push xjoker/jadx-ai-mcp-base:1.0
```

### 应用镜像

```bash
# All-in-One（使用基础镜像）
docker build -t jadx-ai-mcp -f docker/Dockerfile .

# 仅 MCP Server（独立构建，不需要基础镜像）
docker build -t jadx-mcp-server -f docker/Dockerfile.mcp .
```

---

## 多实例部署

部署多个 JADX 实例实现并行分析：

```mermaid
flowchart TB
    MCP[MCP Server :8651] --> J1[JADX #1 :8650<br/>app-v1.apk]
    MCP --> J2[JADX #2 :8660<br/>app-v2.apk]
    MCP --> J3[JADX #3 :8670<br/>dev.apk]
```

### 示例配置

```bash
# 终端 1: app-v1 的 JADX 实例
docker run -d --name jadx-v1 -p 8650:8650 -p 6080:6080 \
  -v $(pwd)/app-v1.apk:/apks/app.apk \
  xjoker/jadx-ai-mcp

# 终端 2: app-v2 的 JADX 实例
docker run -d --name jadx-v2 -p 8660:8650 -p 6081:6080 \
  -v $(pwd)/app-v2.apk:/apks/app.apk \
  xjoker/jadx-ai-mcp

# 终端 3: 连接两个实例的 MCP Server
docker run -d --name mcp -p 8651:8651 \
  -v $(pwd)/config:/app/data/config \
  xjoker/jadx-mcp-server

# 在 config/jadx-config.toml 中配置实例
```

**config/jadx-config.toml:**

```toml
[[jadx_instances]]
name = "app-v1"
host = "host.docker.internal"  # 或容器 IP
port = 8650

[[jadx_instances]]
name = "app-v2"
host = "host.docker.internal"
port = 8660
```

## 故障排查

```bash
# 查看日志
docker logs jadx-ai-mcp

# 进入容器
docker exec -it jadx-ai-mcp bash

# 检查服务状态 (All-in-One)
docker exec jadx-ai-mcp supervisorctl status
```

### 常见问题

| 症状 | 原因 | 解决方案 |
|------|------|----------|
| MCP Server 无法连接 JADX | JADX 未加载文件 | 先在 JADX GUI 中打开 APK/JAR |
| Docker 容器连接被拒绝 | 使用了 `127.0.0.1` 连接宿主机 JADX | 改用 `host.docker.internal` |
| 401 未授权 | Token 缺失或错误 | 检查配置中 `[[users]]` 的 token |
| 插件 API 端口无响应 | JADX GUI 尚未完全启动 | 等待 JADX GUI 完成加载 |
