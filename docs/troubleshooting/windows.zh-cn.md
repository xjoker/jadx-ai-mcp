[English](windows.md) | **简体中文**

---

### Windows 常见问题

#### 1. `$(pwd)` 不工作

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

#### 2. Docker 卷权限问题

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

#### 3. `python3` 命令找不到

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

#### 4. Windows 上安装 JADX

**步骤：**
1. 从 [JADX Releases](https://github.com/skylot/jadx/releases) 下载 `jadx-x.x.x.zip`
2. 解压到文件夹（如 `C:\jadx`）
3. 添加到 PATH：
   - Windows 搜索 "环境变量"
   - 编辑 `Path` 变量
   - 添加 `C:\jadx\bin`
4. 重启终端

---

#### 5. 端口已被占用

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

## Related / 相关

- [Docker Deployment](../deployment/docker.md)
- [FAQ](faq.md)
