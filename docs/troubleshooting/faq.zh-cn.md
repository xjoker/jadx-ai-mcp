# 常见问题

[English](faq.md) | **简体中文**

---

## 🔧 安装问题

### Q: 插件安装命令提示 "Can't find compatible version"
**A:** 手动下载安装：
```bash
wget https://github.com/xjoker/jadx-ai-mcp/releases/latest/download/jadx-ai-mcp.jar
jadx plugins --install-jar jadx-ai-mcp.jar
```

### Q: `jadx_mcp_server` 命令找不到
**A:** 确保安装路径在 PATH 中：
```bash
# 使用完整路径
~/.local/bin/jadx_mcp_server

# 或添加到 PATH
export PATH="$HOME/.local/bin:$PATH"
```

### Q: Python 版本不兼容
**A:** MCP Server 需要 Python 3.10+：
```bash
python3 --version  # 检查版本
pyenv install 3.11.0  # 可选：使用 pyenv 安装新版本
```

---

## 🔌 连接问题

### Q: Claude 提示 "无法连接到 MCP Server"
**A:** 检查清单：
1. 确保 JADX GUI 已打开并加载了 APK/JAR
2. 确保 `jadx_mcp_server` 正在运行
3. 检查端口未被占用：`lsof -i :8651`

### Q: JADX 插件未启动
**A:** 检查插件是否启用：
1. JADX GUI → Plugins → JADX AI MCP Server → Settings
2. 确保 "Auto Start" 已勾选
3. 手动点击 "Start Server"

### Q: Docker 容器无法访问
**A:** 检查端口映射：
```bash
docker ps  # 确认容器运行中
docker logs jadx  # 查看日志
```

---

## ⚡ 性能问题

### Q: 首次搜索很慢
**A:** 正常现象。JADX 需要先反编译代码：
- 首次搜索：30-60 秒
- 后续搜索：<1 秒（有缓存）

**建议：** 使用 Docker 并挂载缓存卷：
```bash
-v jadx-cache:/root/.cache
```

### Q: 搜索超时
**A:** 使用更精确的搜索：
```python
# 不推荐
search_classes_by_keyword("password")  # 全量搜索

# 推荐
search_classes_by_keyword("password", package="com.example", search_in="class")
```

### Q: 返回 "INSTANCE_BUSY"
**A:** 另一个搜索正在进行，等待几秒后重试。

---

## 📱 APK/JAR 问题

### Q: Docker 中如何打开 APK？
**A:** 
1. 将 APK 放入本地 `./apks/` 目录
2. 在 JADX 中 File → Open → `/apks/your-app.apk`

### Q: APK 无法反编译
**A:** 可能是加壳/混淆 APK，尝试：
1. 使用 Frida 脱壳
2. 检查 JADX 日志错误信息

---

## 🔐 认证问题

### Q: 如何设置访问密码？
**A:** 在 `jadx-config.toml` 中配置：
```toml
[[users]]
name = "alice"
token = "your-secret-token"
```

Claude 配置：
```json
{
  "mcpServers": {
    "jadx": {
      "type": "http",
      "url": "http://localhost:8651/mcp",
      "headers": { "Authorization": "Bearer your-secret-token" }
    }
  }
}
```

---

## 🔗 更多帮助

- [GitHub Issues](https://github.com/xjoker/jadx-ai-mcp/issues)
- [快速开始](../getting-started/quickstart.zh-cn.md)
- [AI 集成指南](../guides/ai-integration.zh-cn.md)
