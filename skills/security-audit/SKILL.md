---
name: security-audit
description: Perform security audits on Android APKs to find vulnerabilities and risks. Use this skill when asked to "security audit", "find vulnerabilities", "security check", "OWASP analysis", "pentest", "risk analysis", "hardcoded secrets", "insecure code", "privacy leak", "SDK behavior analysis", "malware analysis", or any security-related code review of Android applications.
---

# Android Security Audit Guide

Systematic security audit workflow for Android APKs using JADX-AI-MCP tools.

## Severity Classification

| Severity | Description | Examples |
|:---------|:------------|:---------|
| CRITICAL | Immediate exploitation risk | Hardcoded API keys, SQL injection, RCE |
| HIGH | Significant security impact | Insecure data storage, weak crypto, path traversal |
| MEDIUM | Potential security concern | Missing certificate pinning, debug enabled |
| LOW | Best practice violation | Verbose logging, unused permissions |

## Vulnerability Categories

| Category | Focus Areas | MCP Tools |
|:---------|:------------|:----------|
| Manifest | Exported components, permissions, backup flags | `get_android_manifest` |
| Secrets | API keys, passwords, tokens, credentials | `search_classes_by_keyword(search_in="code")` |
| Network | HTTP usage, certificate pinning, SSL/TLS | `search_classes_by_keyword(search_in="code")`, `get_method_by_name` |
| Crypto | Weak algorithms, hardcoded keys, insecure random | `search_classes_by_keyword(search_in="code")`, `get_class_source` |
| Injection | SQL, command, path traversal, intent redirect | `search_classes_by_keyword(search_in="code")`, `get_method_by_name` |
| Storage | SharedPrefs, SQLite, file permissions | `search_classes_by_keyword(search_in="code")`, `get_fields_of_class` |

## Audit Workflow

### Step 1: Manifest Analysis

```
1. Get AndroidManifest.xml using get_android_manifest tool
2. Check for:
   - android:debuggable="true"
   - android:allowBackup="true"
   - android:exported="true" on activities/services/receivers
   - Dangerous permissions (READ_SMS, READ_CONTACTS, etc.)
   - Custom permissions with weak protectionLevel
```

### Step 2: Hardcoded Secrets Search

Search patterns for common secrets using `search_classes_by_keyword(search_in="code")`:

```python
# API Keys and Tokens
search_classes_by_keyword("api_key", search_in="code")
search_classes_by_keyword("secret_key", search_in="code")
search_classes_by_keyword("access_token", search_in="code")
search_classes_by_keyword("bearer", search_in="code")

# Credentials
search_classes_by_keyword("password", search_in="code")
search_classes_by_keyword("credential", search_in="code")

# Cloud Services
search_classes_by_keyword("firebase", search_in="code")
search_classes_by_keyword("aws", search_in="code")
```

> **Note**: Check `get_decompile_status()` first. Use `search_in="code"` only when `cached_percentage > 20%`.

### Step 3: Network Security

```python
# Insecure HTTP
search_classes_by_keyword("http://", search_in="code")
search_classes_by_keyword("setHostnameVerifier", search_in="code")
search_classes_by_keyword("TrustAllCerts", search_in="code")
search_classes_by_keyword("ALLOW_ALL_HOSTNAME", search_in="code")

# Certificate Pinning Bypass
search_classes_by_keyword("X509TrustManager", search_in="code")
search_classes_by_keyword("checkServerTrusted", search_in="code")
```

### Step 4: Cryptographic Issues

```python
# Weak Algorithms
search_classes_by_keyword("DES", search_in="code")
search_classes_by_keyword("MD5", search_in="code")
search_classes_by_keyword("ECB", search_in="code")

# Insecure Random
search_classes_by_keyword("java.util.Random", search_in="code")

# Hardcoded Crypto Keys
search_classes_by_keyword("SecretKeySpec", search_in="code")
search_classes_by_keyword("IvParameterSpec", search_in="code")
```

### Step 5: Injection Vulnerabilities

```python
# SQL Injection
search_classes_by_keyword("rawQuery", search_in="code")
search_classes_by_keyword("execSQL", search_in="code")

# Path Traversal
search_classes_by_keyword("getExternalStorage", search_in="code")
search_classes_by_keyword("openFileInput", search_in="code")

# Intent Redirect
search_classes_by_keyword("getParcelableExtra", search_in="code")
```

### Step 6: Data Storage

```python
# Insecure SharedPreferences
search_classes_by_keyword("MODE_WORLD_READABLE", search_in="code")
search_classes_by_keyword("MODE_WORLD_WRITEABLE", search_in="code")
search_classes_by_keyword("getSharedPreferences", search_in="code")

# SQLite without encryption
search_classes_by_keyword("SQLiteDatabase", search_in="code")
search_classes_by_keyword("openOrCreateDatabase", search_in="code")
```

## Report Format

```markdown
## Security Audit Report

### Summary
- Total Issues: X
- Critical: X | High: X | Medium: X | Low: X

### Findings

#### [CRITICAL] Finding Title
- **Location**: com.example.Class:method:line
- **Description**: What was found
- **Impact**: Security impact
- **Recommendation**: How to fix

#### [HIGH] Finding Title
...
```

## Common Pitfalls

- **False positives**: Verify findings in decompiled code context before reporting
- **Obfuscated code**: Use `get_class_source` to understand obfuscated class relationships
- **Native libraries**: Note that .so files require separate analysis
- **Third-party SDKs**: Distinguish app code from SDK vulnerabilities
- **ProGuard mapping**: Check if mapping file available for better analysis

## OWASP Mobile Top 10 Checklist

| Risk | Check |
|:-----|:------|
| M1: Improper Platform Usage | Manifest permissions, exported components |
| M2: Insecure Data Storage | SharedPrefs, SQLite, file storage |
| M3: Insecure Communication | HTTP, certificate pinning |
| M4: Insecure Authentication | Hardcoded credentials, weak auth |
| M5: Insufficient Cryptography | Weak algorithms, hardcoded keys |
| M6: Insecure Authorization | Intent extras, content providers |
| M7: Client Code Quality | Input validation, error handling |
| M8: Code Tampering | Debug flags, root detection |
| M9: Reverse Engineering | Obfuscation, anti-tampering |
| M10: Extraneous Functionality | Debug logs, test endpoints |
