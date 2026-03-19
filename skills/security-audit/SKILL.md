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
| Manifest | Exported components, permissions, backup flags | `get_android_manifest`, `get_strings` |
| Secrets | API keys, passwords, tokens, credentials | `get_strings`, `get_fields_of_class` |
| Network | HTTP usage, certificate pinning, SSL/TLS | `get_class_source`, `get_method_by_name` |
| Crypto | Weak algorithms, hardcoded keys, insecure random | `get_class_source`, `search_classes_by_keyword` |
| Injection | SQL, command, path traversal, intent redirect | `get_class_source`, `get_method_by_name` |
| Storage | SharedPrefs, SQLite, file permissions | `get_class_source`, `search_classes_by_keyword` |

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

Search patterns for common secrets:

```
# API Keys and Tokens
search_code: "api[_-]?key"
search_code: "secret[_-]?key"
search_code: "access[_-]?token"
search_code: "bearer"
search_code: "authorization"

# Credentials
search_code: "password"
search_code: "passwd"
search_code: "credential"

# Cloud Services
search_code: "aws[_-]?"
search_code: "firebase"
search_code: "google[_-]?api"
```

### Step 3: Network Security

```
# Insecure HTTP
search_code: "http://"
search_code: "setHostnameVerifier"
search_code: "TrustAllCerts"
search_code: "ALLOW_ALL_HOSTNAME"

# Certificate Pinning Bypass
search_code: "X509TrustManager"
search_code: "checkServerTrusted"
```

### Step 4: Cryptographic Issues

```
# Weak Algorithms
search_code: "DES"
search_code: "MD5"
search_code: "SHA1"
search_code: "ECB"

# Insecure Random
search_code: "java.util.Random"
search_code: "setSeed"

# Hardcoded Crypto Keys
search_code: "SecretKeySpec"
search_code: "IvParameterSpec"
```

### Step 5: Injection Vulnerabilities

```
# SQL Injection
search_code: "rawQuery"
search_code: "execSQL"

# Path Traversal
search_code: "getExternalStorage"
search_code: "openFileInput"
search_code: "../"

# Intent Redirect
search_code: "getParcelableExtra"
search_code: "startActivity.*getIntent"
```

### Step 6: Data Storage

```
# Insecure SharedPreferences
search_code: "MODE_WORLD_READABLE"
search_code: "MODE_WORLD_WRITEABLE"
search_code: "getSharedPreferences"

# SQLite without encryption
search_code: "SQLiteDatabase"
search_code: "openOrCreateDatabase"
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
