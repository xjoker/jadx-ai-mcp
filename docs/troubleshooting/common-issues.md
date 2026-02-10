# Common Issues & Troubleshooting

**English** | [简体中文](common-issues.zh-cn.md)

---

> 💡 This document consolidates FAQ and platform-specific issues (Windows, etc.).

## 🔧 Installation Issues

### Q: Plugin install says "Can't find compatible version"
**A:** Manual install:
```bash
wget https://github.com/xjoker/jadx-ai-mcp/releases/latest/download/jadx-ai-mcp.jar
jadx plugins --install-jar jadx-ai-mcp.jar
```

### Q: `jadx_mcp_server` command not found
**A:** Ensure PATH includes install directory:
```bash
~/.local/bin/jadx_mcp_server
# or
export PATH="$HOME/.local/bin:$PATH"
```

### Q: Python version not compatible
**A:** MCP Server requires Python 3.10+:
```bash
python3 --version  # Check version
pyenv install 3.11.0  # Optional: use pyenv
```

---

## 🔌 Connection Issues

### Q: Claude can't connect to MCP Server
**A:** Checklist:
1. JADX GUI is open with an APK/JAR loaded
2. `jadx_mcp_server` is running
3. Port 8651 is not blocked: `lsof -i :8651`

### Q: JADX plugin not starting
**A:** Check plugin is enabled:
1. JADX GUI → Plugins → JADX AI MCP Server → Settings
2. Ensure "Auto Start" is checked
3. Manually click "Start Server"

### Q: Docker container not accessible
**A:** Check port mapping:
```bash
docker ps  # Confirm container is running
docker logs jadx  # View logs
```

### Q: MCP Server shows "Connection refused"
**A:** Check health status:
```bash
curl http://localhost:8651/health
# Expected output: {"status":"ok"}

# If inside container, use
docker exec jadx curl http://localhost:8651/health
```

---

## ⚡ Performance

### Q: First search is slow
**A:** Normal - JADX needs to decompile first:
- First search: 30-60 seconds
- Subsequent: <1 second (cached)

**Tip:** Use Docker with cache volume:
```bash
-v jadx-cache:/root/.cache
```

### Q: Search timeout
**A:** Use more specific search:
```python
# Not recommended
search_classes_by_keyword("password")  # Full search

# Recommended
search_classes_by_keyword("password", package="com.example", search_in="class")
```

### Q: Returns "INSTANCE_BUSY"
**A:** Another search is in progress. Wait a few seconds and retry.

---

## 📱 APK/JAR Issues

### Q: How to open APK in Docker?
**A:**
1. Put APK in `./apks/` directory
2. In JADX: File → Open → `/apks/your-app.apk`

**Or use auto-load**:
```bash
cp your-app.apk ~/apks/target.apk
# JADX will open it automatically on startup
```

### Q: APK fails to decompile
**A:** May be packed/obfuscated APK:
1. Try using Frida to unpack
2. Check JADX logs for error messages
3. Try a different JADX version

---

## 🔐 Authentication

### Q: How to set access password?
**A:** Configure in `jadx-config.toml`:
```toml
[[users]]
name = "alice"
token = "your-secret-token"
```

Claude configuration:
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

### Q: 401 Unauthorized error
**A:** Check token correctness:
1. Verify token value in config file
2. Ensure token matches in Claude config
3. Check `Authorization: Bearer ` format (note the space)

---

## 🪟 Windows-Specific Issues

### Q: `$(pwd)` doesn't work
**Problem:** PowerShell/CMD doesn't recognize `$(pwd)` syntax.

**Solution:**

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

### Q: Docker volume permission issues
**Problem:** "Access denied" when mounting volumes.

**Solutions:**
1. **Enable WSL2 backend** (recommended):
   - Docker Desktop → Settings → General → "Use the WSL 2 based engine"

2. **Share drive in Docker settings**:
   - Docker Desktop → Settings → Resources → File Sharing
   - Add your drive (e.g., C:)

3. **Use named volumes** (always works):
   ```powershell
   docker run -d --name jadx `
     -p 6080:6080 -p 8651:8651 `
     -v jadx-apks:/apks `
     xjoker/jadx-ai-mcp:latest
   ```

---

### Q: `python3` command not found
**Problem:** Windows uses `python` not `python3`.

**Solutions:**
```powershell
# Check Python version
python --version

# Or use py launcher
py -3 --version

# Install with pip
pip install "git+https://github.com/xjoker/jadx-ai-mcp#subdirectory=jadx-mcp-server"
```

---

### Q: JADX installation on Windows
**Steps:**
1. Download `jadx-x.x.x.zip` from [JADX Releases](https://github.com/skylot/jadx/releases)
2. Extract to a folder (e.g., `C:\jadx`)
3. Add to PATH:
   - Search "Environment Variables" in Windows
   - Edit `Path` variable
   - Add `C:\jadx\bin`
4. Restart terminal

---

### Q: Port already in use (Windows)
**Problem:** Port 6080 or 8651 already in use.

**Solutions:**
```powershell
# Find process using port
netstat -ano | findstr :6080

# Kill process by PID
taskkill /PID <pid> /F

# Or use different ports
docker run -d --name jadx `
  -p 7080:6080 -p 9651:8651 `
  -v ${PWD}/apks:/apks `
  xjoker/jadx-ai-mcp:latest
```

---

### Q: Line ending issues (CRLF vs LF)
**Problem:** Git converts line endings, causing script failures.

**Solution:**
```bash
# Configure git (once)
git config --global core.autocrlf false

# Or in .gitattributes
* text=auto eol=lf
```

---

## 🐧 Linux-Specific Issues

### Q: Permission denied accessing Docker socket
**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Re-login or execute
newgrp docker
```

---

## 🍎 macOS-Specific Issues

### Q: M1/M2 Mac architecture issues
**A:** Ensure using `--platform linux/amd64`:
```bash
docker run --platform linux/amd64 -d --name jadx \
  -p 6080:6080 -p 8651:8651 \
  -v ~/apks:/apks \
  xjoker/jadx-ai-mcp:latest
```

---

## 🔍 Debugging Tips

### View Detailed Logs
```bash
# Docker logs
docker logs -f jadx

# Access shell
docker exec -it jadx bash

# Check services (All-in-One)
docker exec jadx supervisorctl status
```

### Health Checks
```bash
# Check MCP Server
curl http://localhost:8651/health

# Check JADX Plugin (only after loading a file)
curl http://localhost:8650/health
```

### Network Diagnostics
```bash
# Check port listening
netstat -tuln | grep 8651  # Linux
lsof -i :8651              # macOS

# Test connectivity
telnet localhost 8651
```

---

## 🔗 More Help

- [GitHub Issues](https://github.com/xjoker/jadx-ai-mcp/issues)
- [System Architecture](../overview/architecture.md) - Understand ports and communication
- [Quick Start Guide](../getting-started/quickstart.md)
- [AI Client Configuration](../guides/ai-clients.md)
- [Docker Deployment](../deployment/docker.md)
