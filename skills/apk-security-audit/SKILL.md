---
name: apk-security-audit
description: Comprehensive security audit for Android APK files using JADX decompilation and analysis
allowed-tools:
  - mcp__jadx__get_android_manifest
  - mcp__jadx__search_classes_by_keyword
  - mcp__jadx__search_native_methods
  - mcp__jadx__get_class_source
  - mcp__jadx__get_xrefs
  - mcp__jadx__list_classes
  - mcp__jadx__get_method_code
---

# APK Security Audit

Perform a comprehensive security audit of an Android APK using JADX MCP tools. This skill guides you through systematic analysis of common vulnerability patterns and security misconfigurations.

## Audit Workflow

Execute the following security checks in order. Document all findings with severity levels (CRITICAL, HIGH, MEDIUM, LOW, INFO).

### 1. AndroidManifest.xml Analysis

Use `get_android_manifest` to retrieve and analyze the manifest for:

**Dangerous Permissions:**
- `android.permission.READ_SMS` / `RECEIVE_SMS` / `SEND_SMS`
- `android.permission.READ_CONTACTS` / `WRITE_CONTACTS`
- `android.permission.READ_CALL_LOG` / `WRITE_CALL_LOG`
- `android.permission.CAMERA`
- `android.permission.RECORD_AUDIO`
- `android.permission.ACCESS_FINE_LOCATION` / `ACCESS_COARSE_LOCATION`
- `android.permission.READ_EXTERNAL_STORAGE` / `WRITE_EXTERNAL_STORAGE`
- `android.permission.INTERNET` (combined with storage permissions)
- `android.permission.SYSTEM_ALERT_WINDOW`
- `android.permission.REQUEST_INSTALL_PACKAGES`

**Exported Components (check for missing permission guards):**
- `<activity android:exported="true">` without `android:permission`
- `<service android:exported="true">` without `android:permission`
- `<receiver android:exported="true">` without `android:permission`
- `<provider android:exported="true">` without `android:permission` or `android:readPermission`/`android:writePermission`

**Security Flags:**
- `android:debuggable="true"` - CRITICAL if present in release
- `android:allowBackup="true"` - Data extraction risk
- `android:usesCleartextTraffic="true"` - Insecure network traffic
- Missing `android:networkSecurityConfig` - No certificate pinning

**Intent Filters on Exported Components:**
- Deep links with sensitive actions
- Custom schemes that could be hijacked

### 2. Hardcoded Secrets Detection

Use `search_classes_by_keyword` with `search_in='code'` to find:

**API Keys and Tokens:**
```
Search patterns:
- "api_key"
- "apikey"
- "api-key"
- "secret_key"
- "secretkey"
- "access_token"
- "auth_token"
- "bearer"
- "AIza" (Google API keys)
- "AKIA" (AWS Access Keys)
- "sk-" (OpenAI keys)
- "ghp_" (GitHub tokens)
```

**Passwords and Credentials:**
```
Search patterns:
- "password"
- "passwd"
- "pwd"
- "credentials"
- "private_key"
- "BEGIN RSA"
- "BEGIN PRIVATE"
```

**URLs with Embedded Credentials:**
```
Search patterns:
- "://.*:.*@" (basic auth in URLs)
- "jdbc:" (database connection strings)
```

**Firebase/Cloud Configurations:**
```
Search patterns:
- "firebase"
- ".firebaseio.com"
- "google-services"
```

For each finding, use `get_class_source` to examine the full context and confirm if the secret is actually sensitive.

### 3. Native Code Analysis

Use `search_native_methods` to identify JNI calls:

**High-Risk Native Patterns:**
- Methods handling encryption/decryption
- Methods processing user input
- Methods accessing files or network
- Methods with names suggesting security operations (e.g., `decrypt`, `verify`, `authenticate`)

**For each native method found:**
1. Use `get_xrefs` to find all callers
2. Use `get_class_source` to understand the calling context
3. Note if native libraries are obfuscated or packed

**Common Native Vulnerabilities:**
- Buffer overflow potential in string handling
- Insecure random number generation
- Hardcoded keys in native code (check for base64 strings)
- Anti-tampering/root detection bypass opportunities

### 4. Network Security Analysis

Use `search_classes_by_keyword` with `search_in='code'` to find:

**Insecure HTTP Usage:**
```
Search patterns:
- "http://"
- "HttpURLConnection"
- "OkHttpClient"
- "Retrofit"
```

**SSL/TLS Issues:**
```
Search patterns:
- "TrustManager"
- "X509TrustManager"
- "checkServerTrusted"
- "SSLContext"
- "HostnameVerifier"
- "ALLOW_ALL"
- "setHostnameVerifier"
```

**Look for dangerous patterns:**
- Custom TrustManager that accepts all certificates
- HostnameVerifier that returns true for all hostnames
- SSLSocketFactory modifications

**Certificate Pinning:**
```
Search patterns:
- "CertificatePinner"
- "sha256/"
- "NetworkSecurityConfig"
```

For each network-related class, use `get_class_source` to verify implementation security.

### 5. Cryptography Implementation

Use `search_classes_by_keyword` with `search_in='code'` to find:

**Weak Algorithms:**
```
Search patterns:
- "DES"
- "MD5"
- "SHA1" (for signatures)
- "ECB" (insecure block mode)
- "RC4"
- "Blowfish"
```

**Insecure Random:**
```
Search patterns:
- "Random()" (java.util.Random - predictable)
- "Math.random"
- "setSeed"
```

**Key Management Issues:**
```
Search patterns:
- "SecretKeySpec"
- "getBytes" (near encryption code)
- "KeyStore"
- "PBKDF"
- "PBEKeySpec"
```

**Check for:**
- Hardcoded encryption keys
- Static IVs (Initialization Vectors)
- Insufficient key derivation iterations
- Keys stored in SharedPreferences

### 6. Data Storage Security

Use `search_classes_by_keyword` with `search_in='code'` to find:

**SharedPreferences:**
```
Search patterns:
- "SharedPreferences"
- "getSharedPreferences"
- "MODE_WORLD_READABLE"
- "MODE_WORLD_WRITEABLE"
```

**Database Security:**
```
Search patterns:
- "SQLiteDatabase"
- "execSQL"
- "rawQuery"
- "Room"
- "getWritableDatabase"
```

**File Storage:**
```
Search patterns:
- "FileOutputStream"
- "openFileOutput"
- "getExternalStorage"
- "Environment.getExternal"
```

### 7. Injection Vulnerabilities

Use `search_classes_by_keyword` with `search_in='code'` to find:

**SQL Injection:**
```
Search patterns:
- "rawQuery"
- "execSQL"
- String concatenation near SQL operations
```

**Command Injection:**
```
Search patterns:
- "Runtime.getRuntime().exec"
- "ProcessBuilder"
- "/bin/sh"
- "/system/bin"
```

**WebView Vulnerabilities:**
```
Search patterns:
- "WebView"
- "setJavaScriptEnabled"
- "addJavascriptInterface"
- "loadUrl"
- "loadData"
- "evaluateJavascript"
```

**Path Traversal:**
```
Search patterns:
- "new File("
- "getPath"
- "../"
```

### 8. Authentication & Session Management

Use `search_classes_by_keyword` with `search_in='code'` to find:

**Authentication Patterns:**
```
Search patterns:
- "login"
- "authenticate"
- "OAuth"
- "JWT"
- "session"
- "BiometricPrompt"
- "FingerprintManager"
```

**Session Storage:**
```
Search patterns:
- "cookie"
- "session_id"
- "token"
- "refresh_token"
```

For sensitive authentication classes, use `get_xrefs` to trace the authentication flow.

## Output Format

Generate a security audit report with the following structure:

```markdown
# APK Security Audit Report

## Executive Summary
- Total findings: X
- Critical: X | High: X | Medium: X | Low: X | Info: X

## 1. Manifest Security
[Findings with severity and remediation]

## 2. Hardcoded Secrets
[Findings with affected classes and line references]

## 3. Native Code Risks
[Native method analysis results]

## 4. Network Security
[SSL/TLS and HTTP findings]

## 5. Cryptography Issues
[Weak crypto and key management findings]

## 6. Data Storage
[Insecure storage findings]

## 7. Injection Vulnerabilities
[SQL, command, XSS findings]

## 8. Authentication
[Auth flow vulnerabilities]

## Remediation Priorities
1. [Most critical items first]
2. ...
```

## Severity Guidelines

- **CRITICAL**: Immediate exploitation possible, data breach risk
  - Hardcoded production API keys/secrets
  - Disabled SSL verification in production
  - SQL injection with user input
  - Exported components with sensitive data access

- **HIGH**: Significant security weakness
  - Weak encryption algorithms
  - Predictable random number usage for security
  - Missing authentication on sensitive endpoints
  - WebView with JavaScript interface on untrusted content

- **MEDIUM**: Security best practice violation
  - Debuggable flag enabled
  - Backup allowed without encryption
  - Cleartext traffic permitted
  - Overly broad permissions

- **LOW**: Minor security concern
  - Information disclosure in logs
  - Missing certificate pinning
  - Outdated security configurations

- **INFO**: Observations for security awareness
  - Third-party SDK usage
  - Permission usage patterns
  - Architecture observations
