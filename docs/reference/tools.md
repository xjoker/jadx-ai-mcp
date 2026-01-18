# MCP Tools Reference

**English** | [简体中文](tools.zh-cn.md)

---
### 📊 Tool Availability Matrix

> ✅ Full support | ⚠️ Partial | ❌ Not available | 🔄 Returns NOT_APPLICABLE

| Tool | APK | JAR | AAR | DEX | Description |
|:-----|:---:|:---:|:---:|:---:|:------------|
| **Universal Tools** |
| `get_file_info` | ✅ | ✅ | ✅ | ✅ | Recommended first call |
| `get_class_source` | ✅ | ✅ | ✅ | ✅ | Get class source |
| `get_method_by_name` | ✅ | ✅ | ✅ | ✅ | Get method source |
| `get_class_info` | ✅ | ✅ | ✅ | ✅ | Class structure |
| `get_method_signature` | ✅ | ✅ | ✅ | ✅ | Frida-compatible signature |
| **Android-specific** |
| `get_android_manifest` | ✅ | 🔄 | ✅ | ❌ | AndroidManifest.xml |
| `get_smali_of_class` | ✅ | ❌ | ✅ | ✅ | Dalvik bytecode |
| **JAR-specific** |
| `jar_get_manifest` | 🔄 | ✅ | 🔄 | 🔄 | MANIFEST.MF |
| `jar_get_services` | 🔄 | ✅ | 🔄 | 🔄 | SPI services |
| `jar_get_entry_points` | 🔄 | ✅ | 🔄 | 🔄 | Entry points |
| `jar_get_dependencies` | 🔄 | ✅ | 🔄 | 🔄 | Dependencies |
| `jar_get_bytecode` | ✅ | ✅ | ✅ | ✅ | Class bytecode |

> See Chinese section above for complete 47-tool matrix.

---

### 🔗 Related Documentation

- [Quick Start Guide](../getting-started/quickstart.md)
- [AI Integration](../guides/ai-integration.md)
- [FAQ / Troubleshooting](../troubleshooting/faq.md)
- [Docker Deployment](../deployment/docker.md)
