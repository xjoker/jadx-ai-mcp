---
name: crypto-analysis
description: Analyze cryptographic algorithms, encryption/decryption routines, malware behavior, and protection mechanisms in decompiled code. Use this skill when the user asks about encryption, decryption, algorithm, crypto, cipher, malware, obfuscation, evasion, packer, anti-debug, license check, key generation, activation, serial validation, or any security-related code analysis.
---

# Cryptographic & Malware Analysis Guide

Specialized analysis techniques for identifying and understanding cryptographic implementations, malware behaviors, and software protection mechanisms in decompiled Android/Java code.

## When to Use This Skill

- Identifying encryption/decryption algorithms (AES, RSA, DES, etc.)
- Analyzing malware samples for evasion techniques
- Reverse engineering license/activation mechanisms
- Detecting anti-debugging and anti-tampering code
- Understanding obfuscation and packing techniques
- Analyzing native (JNI) cryptographic functions

## Cryptographic Pattern Recognition

### Common Algorithm Signatures

| Algorithm | Key Identifiers | Typical Usage |
|:----------|:----------------|:--------------|
| AES | `Cipher.getInstance("AES")`, `SecretKeySpec`, 16/24/32 byte keys | Data encryption, secure storage |
| RSA | `KeyPairGenerator`, `Cipher.getInstance("RSA")`, public/private keys | Key exchange, signatures |
| DES/3DES | `Cipher.getInstance("DES")`, 8/24 byte keys | Legacy encryption |
| MD5 | `MessageDigest.getInstance("MD5")`, 32 char hex output | Checksums (insecure) |
| SHA-1/256 | `MessageDigest.getInstance("SHA-256")` | Integrity verification |
| Base64 | `Base64.encode/decode`, `android.util.Base64` | Encoding (not encryption) |
| HMAC | `Mac.getInstance("HmacSHA256")` | Message authentication |

### Code Pattern Examples

```java
// AES encryption pattern
Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
SecretKeySpec keySpec = new SecretKeySpec(keyBytes, "AES");
IvParameterSpec ivSpec = new IvParameterSpec(ivBytes);
cipher.init(Cipher.ENCRYPT_MODE, keySpec, ivSpec);

// RSA signature pattern
Signature signature = Signature.getInstance("SHA256withRSA");
signature.initVerify(publicKey);
signature.update(data);
boolean valid = signature.verify(signatureBytes);
```

## Malware Analysis Techniques

### Evasion Detection Patterns

| Technique | Detection Method | Code Indicators |
|:----------|:-----------------|:----------------|
| Emulator Detection | Check build properties | `Build.FINGERPRINT`, `Build.MODEL`, "generic", "sdk" |
| Root Detection | Check for su binary | `/system/bin/su`, `which su`, SuperUser.apk |
| Debugger Detection | Check debug flags | `Debug.isDebuggerConnected()`, `android:debuggable` |
| Hook Detection | Check for Xposed/Frida | `de.robv.android.xposed`, `/data/local/tmp/frida` |
| VM Detection | Hardware checks | `Build.HARDWARE`, sensor availability |

### Dynamic Loading Indicators

```java
// Suspicious dynamic loading patterns
DexClassLoader loader = new DexClassLoader(dexPath, ...);
Class<?> clazz = loader.loadClass("com.hidden.Payload");

// Reflection-based execution
Method method = clazz.getDeclaredMethod("execute");
method.setAccessible(true);
method.invoke(instance);

// Runtime command execution
Runtime.getRuntime().exec("sh -c " + command);
```

### Network Communication Red Flags

- Hardcoded IP addresses or suspicious domains
- Custom encryption before network transmission
- Certificate pinning bypass attempts
- Data exfiltration to unknown servers

## License/Activation Analysis

### Common Protection Patterns

| Pattern | Indicators | Analysis Approach |
|:--------|:-----------|:------------------|
| Serial Validation | String comparison, checksum | Trace validation logic |
| Time-based Trial | `System.currentTimeMillis()`, SharedPreferences | Find time checks |
| Server Validation | Network calls, license API | Identify validation endpoints |
| Hardware Binding | `Build.SERIAL`, IMEI, Android ID | Find device ID usage |
| Feature Flags | Boolean checks, premium status | Locate flag storage |

### Key Generation Analysis

```java
// Look for key derivation patterns
SecretKeyFactory factory = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256");
KeySpec spec = new PBEKeySpec(password, salt, iterations, keyLength);
SecretKey key = factory.generateSecret(spec);

// Static key patterns (vulnerable)
private static final byte[] KEY = {0x12, 0x34, ...};
private static final String SECRET = "hardcoded_key";
```

## Native Code Analysis (JNI)

### Identifying Native Crypto

```java
// Java side declaration
public native byte[] encrypt(byte[] data);
public native boolean verifyLicense(String serial);

static {
    System.loadLibrary("crypto");  // Look for libcrypto.so
}
```

### Native Library Investigation

1. Extract `.so` files from APK (`lib/` directory)
2. Use JADX to identify native method declarations
3. Cross-reference with native function exports
4. Look for OpenSSL, mbedtls, or custom crypto symbols

## Step-by-Step Analysis Workflow

### 1. Initial Reconnaissance

- Search for crypto-related imports: `javax.crypto`, `java.security`
- Identify string constants: "AES", "RSA", hardcoded keys
- Locate native library loading

### 2. Algorithm Identification

- Trace `Cipher.getInstance()` calls for algorithm names
- Check key lengths to confirm algorithm
- Identify encryption modes (CBC, GCM, ECB)

### 3. Key Management Analysis

- Find key storage locations (SharedPreferences, KeyStore)
- Trace key derivation from user input
- Identify hardcoded keys or predictable generation

### 4. Data Flow Tracing

- Follow encrypted data from source to destination
- Identify what data is being protected
- Map encryption/decryption call sites

### 5. Vulnerability Assessment

- Check for insecure algorithms (DES, MD5 for security)
- Look for ECB mode usage (pattern leakage)
- Identify key reuse or weak IV generation

## Best Practices

1. **Document all findings** with class names and line numbers
2. **Trace complete data flows** before drawing conclusions
3. **Check for obfuscation** - names may be meaningless but patterns reveal intent
4. **Cross-reference native code** when Java layer seems incomplete
5. **Look for multiple protection layers** - apps often combine techniques

## Safety Considerations

**CRITICAL**: When analyzing potentially malicious samples:

- Never execute suspicious code outside controlled environments
- Do not connect analyzed apps to production networks
- Document indicators of compromise (IoCs) for threat intelligence
- Report findings through appropriate disclosure channels
- Maintain chain of custody for forensic samples
