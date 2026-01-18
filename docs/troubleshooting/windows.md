# Windows Troubleshooting

**English** | [简体中文](windows.zh-cn.md)

---

### Common Windows Issues

#### 1. `$(pwd)` doesn't work

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

#### 2. Docker volume permission issues

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

#### 3. `python3` command not found

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

#### 4. JADX installation on Windows

**Steps:**
1. Download `jadx-x.x.x.zip` from [JADX Releases](https://github.com/skylot/jadx/releases)
2. Extract to a folder (e.g., `C:\jadx`)
3. Add to PATH:
   - Search "Environment Variables" in Windows
   - Edit `Path` variable
   - Add `C:\jadx\bin`
4. Restart terminal

---

#### 5. Port already in use

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

#### 6. Line ending issues (CRLF vs LF)

**Problem:** Git converts line endings, causing script failures.

**Solution:**
```bash
# Configure git (once)
git config --global core.autocrlf false

# Or in .gitattributes
* text=auto eol=lf
```
