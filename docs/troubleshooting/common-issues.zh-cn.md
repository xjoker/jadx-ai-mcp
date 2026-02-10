# 常见问题与故障排查

[English](common-issues.md) | **简体中文**

---

> 💡 本文档整合了常见问题（FAQ）和平台专项问题（Windows 等）。

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

### Q: MCP Server 显示 "Connection refused"
**A:** 检查健康状态：
```bash
curl http://localhost:8651/health
# 预期输出: {"status":"ok"}

# 如果容器内部访问，使用
docker exec jadx curl http://localhost:8651/health
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

**或使用自动加载**：
```bash
cp your-app.apk ~/apks/target.apk
# JADX 启动时自动打开
```

### Q: APK 无法反编译
**A:** 可能是加壳/混淆 APK，尝试：
1. 使用 Frida 脱壳
2. 检查 JADX 日志错误信息
3. 尝试使用不同的 JADX 版本

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

### Q: 401 Unauthorized 错误
**A:** 检查 token 是否正确：
1. 确认配置文件中的 token 值
2. 确认 Claude 配置中的 token 匹配
3. 检查 `Authorization: Bearer ` 格式（注意空格）

---

## 🪟 Windows 专项问题

### Q: `$(pwd)` 不工作
**问题：** PowerShell/CMD 不识别 `$(pwd)` 语法。

**解决方案：**

**PowerShell:**
```powershell
docker run -d --name jadx `
  -p 6080:6080 -p 8651:8651 `
  -v ${PWD}/apks:/apks `
  xjoker/jadx-ai-mcp:latest
```

**CMD:**
```cmd
docker run -d --name jadx ^
  -p 6080:6080 -p 8651:8651 ^
  -v %cd%/apks:/apks ^
  xjoker/jadx-ai-mcp:latest
```

---

### Q: Docker 卷权限问题
**问题：** 挂载卷时提示 "Access denied"。

**解决方案：**
1. **启用 WSL2 后端**（推荐）：
   - Docker Desktop → 设置 → 常规 → "Use the WSL 2 based engine"

2. **在 Docker 设置中共享驱动器**：
   - Docker Desktop → 设置 → 资源 → 文件共享
   - 添加你的驱动器（如 C:）

3. **使用命名卷**（始终有效）：
   ```powershell
   docker run -d --name jadx `
     -p 6080:6080 -p 8651:8651 `
     -v jadx-apks:/apks `
     xjoker/jadx-ai-mcp:latest
   ```

---

### Q: `python3` 命令找不到
**问题：** Windows 使用 `python` 而不是 `python3`。

**解决方案：**
```powershell
# 检查 Python 版本
python --version

# 或使用 py 启动器
py -3 --version

# 用 pip 安装
pip install "git+https://github.com/xjoker/jadx-ai-mcp#subdirectory=jadx-mcp-server"
```

---

### Q: Windows 上安装 JADX
**步骤：**
1. 从 [JADX Releases](https://github.com/skylot/jadx/releases) 下载 `jadx-x.x.x.zip`
2. 解压到文件夹（如 `C:\jadx`）
3. 添加到 PATH：
   - Windows 搜索 "环境变量"
   - 编辑 `Path` 变量
   - 添加 `C:\jadx\bin`
4. 重启终端

---

### Q: 端口已被占用（Windows）
**问题：** 端口 6080 或 8651 已被占用。

**解决方案：**
```powershell
# 查找使用端口的进程
netstat -ano | findstr :6080

# 通过 PID 结束进程
taskkill /PID <pid> /F

# 或使用其他端口
docker run -d --name jadx `
  -p 7080:6080 -p 9651:8651 `
  -v ${PWD}/apks:/apks `
  xjoker/jadx-ai-mcp:latest
```

---

### Q: 行尾符问题（CRLF vs LF）
**问题：** Git 转换行尾符，导致脚本失败。

**解决方案：**
```bash
# 配置 git（一次性）
git config --global core.autocrlf false

# 或在 .gitattributes 中
* text=auto eol=lf
```

---

## 🐧 Linux 专项问题

### Q: Permission denied 访问 Docker socket
**解决方案：**
```bash
# 将用户添加到 docker 组
sudo usermod -aG docker $USER

# 重新登录或执行
newgrp docker
```

---

## 🍎 macOS 专项问题

### Q: M1/M2 Mac 架构问题
**A:** 确保使用 `--platform linux/amd64`：
```bash
docker run --platform linux/amd64 -d --name jadx \
  -p 6080:6080 -p 8651:8651 \
  -v ~/apks:/apks \
  xjoker/jadx-ai-mcp:latest
```

---

## 🔍 调试技巧

### 查看详细日志
```bash
# Docker 日志
docker logs -f jadx

# 进入容器
docker exec -it jadx bash

# 检查服务状态（All-in-One）
docker exec jadx supervisorctl status
```

### 健康检查
```bash
# 检查 MCP Server
curl http://localhost:8651/health

# 检查 JADX Plugin（仅在加载文件后）
curl http://localhost:8650/health
```

### 网络诊断
```bash
# 检查端口监听
netstat -tuln | grep 8651  # Linux
lsof -i :8651              # macOS

# 测试连通性
telnet localhost 8651
```

---

## 🔗 更多帮助

- [GitHub Issues](https://github.com/xjoker/jadx-ai-mcp/issues)
- [系统架构](../overview/architecture.zh-cn.md) - 理解端口和通信
- [快速开始](../getting-started/quickstart.zh-cn.md)
- [AI 客户端配置](../guides/ai-clients.zh-cn.md)
- [Docker 部署](../deployment/docker.zh-cn.md)
