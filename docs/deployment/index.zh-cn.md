[English](README.md) | **简体中文**

---

### 部署方式

| 方式 | 适用场景 | 时间 | 指南 |
|:-----|:---------|:----:|:-----|
| **Docker** | 个人使用，快速体验 | 5 分钟 | [docker.zh-cn.md](docker.zh-cn.md) |
| **Docker Compose** | 多实例，团队使用 | 10 分钟 | [docker-compose.zh-cn.md](docker-compose.zh-cn.md) |
| **本地部署** | 开发调试，定制修改 | 15 分钟 | [local.zh-cn.md](local.zh-cn.md) |
| **All-in-One** | 生产环境，带认证 | 15 分钟 | [allinone.zh-cn.md](allinone.zh-cn.md) |

### 端口说明

| 端口 | 服务 | 说明 |
|:----:|:-----|:-----|
| 6080 | noVNC | JADX GUI 网页访问 |
| 8650 | JADX 插件 | 内部 API（通常不暴露） |
| 8651 | MCP Server | AI 客户端连接点 |
