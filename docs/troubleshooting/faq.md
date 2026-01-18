# FAQ / Frequently Asked Questions

**English** | [简体中文](faq.zh-cn.md)

---

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

### Q: APK fails to decompile
**A:** May be packed/obfuscated APK:
1. Try using Frida to unpack
2. Check JADX logs for error messages

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

---

## 🔗 More Help

- [GitHub Issues](https://github.com/xjoker/jadx-ai-mcp/issues)
- [Quick Start Guide](../getting-started/quickstart.md)
- [AI Integration](../guides/ai-integration.md)
