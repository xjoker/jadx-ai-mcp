# JADX-AI-MCP Docker Compose 快速部署

## 📦 一键启动

```bash
# 1. 进入 docker 目录
cd docker

# 2. 启动所有服务
docker compose up -d

# 3. 查看服务状态
docker compose ps
```

## 🌐 访问地址

| 服务 | 地址 | 说明 |
|:-----|:-----|:-----|
| **MCP Server** | http://localhost:8651/mcp | 连接 Claude/LLM |
| **JADX #1** | http://localhost:6080 | noVNC 桌面 |
| **JADX #2** | http://localhost:6081 | noVNC 桌面 |
| **JADX #3** | http://localhost:6082 | noVNC 桌面 |

## 📱 加载 APK

1. 将 APK 文件放入 `apks/` 目录
2. 访问任意 JADX 的 noVNC 页面
3. 在 JADX GUI 中: File → Open → `/apks/your-app.apk`

## 🤖 连接 Claude

```bash
# Claude CLI
claude mcp add --transport http jadx http://localhost:8651/mcp
```

或在 `claude_desktop_config.json` 中添加:

```json
{
  "mcpServers": {
    "jadx": {
      "type": "http",
      "url": "http://localhost:8651/mcp"
    }
  }
}
```

## 📊 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose                            │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐                                           │
│  │  MCP Server  │◀────── Claude / LLM Client                │
│  │   :8651      │                                           │
│  └──────┬───────┘                                           │
│         │ jadx-network                                      │
│  ┌──────┴──────┬───────────────┬───────────────┐           │
│  ▼             ▼               ▼               │           │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐       │           │
│  │ JADX #1 │   │ JADX #2 │   │ JADX #3 │       │           │
│  │ :6080   │   │ :6081   │   │ :6082   │       │           │
│  │ :8650   │   │ :8660   │   │ :8670   │       │           │
│  └─────────┘   └─────────┘   └─────────┘       │           │
│                                                 │           │
│  ┌─────────────────────────────────────────────┴───────┐   │
│  │                  ./apks/ (共享)                       │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 🎯 使用场景

### 场景 1: 比较 APP 版本
```
将 app-v1.apk 在 JADX #1 打开
将 app-v2.apk 在 JADX #2 打开
让 AI: "比较 jadx-1 和 jadx-2 中 MainActivity 的差异"
```

### 场景 2: 团队协作
```
Alice 用 JADX #1 分析登录模块
Bob 用 JADX #2 分析支付模块
Admin 用 JADX #3 做整体审计
```

## 🛑 停止服务

```bash
# 停止所有服务
docker compose down

# 停止并删除数据卷（清理缓存）
docker compose down -v
```

## ⚙️ 自定义配置

编辑 `config/jadx-config.toml` 可以:
- 添加用户认证
- 修改超时时间
- 添加更多 JADX 实例
