# 🚀 Deployment

**English** | [简体中文](index.zh-cn.md)

---

### Deployment Options

| Method | Use Case | Time | Guide |
|:-------|:---------|:----:|:------|
| **Docker** | Single user, quick start | 5 min | [docker.md](docker.md) |
| **Docker Compose** | Multi-instance, team use | 10 min | [docker-compose.md](docker-compose.md) |
| **Local** | Development, customization | 15 min | [local.md](local.md) |
| **All-in-One** | Production, with auth | 15 min | [allinone.md](allinone.md) |

### Port Reference

| Port | Service | Description |
|:----:|:--------|:------------|
| 6080 | noVNC | JADX GUI web access |
| 8650 | JADX Plugin | Internal API (usually not exposed) |
| 8651 | MCP Server | AI client connection point |
