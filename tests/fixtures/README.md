# JADX Test Fixtures

This directory contains **pre-built** test applications for integration testing.

## Files

| File | Type | Size | Description |
|------|------|------|-------------|
| `jadx-test-library-1.0.0.jar` | JAR | 6.4KB | Pure Java library (5 classes, 3 packages) |
| `jadx-test-app-1.0.0.apk` | APK | 3.5KB | Android application (4 classes + manifest) |

> **Note**: Both files are pre-compiled and checked into git. No build step required.

## Test Coverage

These files are designed to test all JADX MCP tools:

### JAR (Pure Java)

| Class | Tests |
|-------|-------|
| `Calculator` | get_methods, get_fields |
| `StringUtils` | get_strings, search_by_code |
| `FileProcessor` | get_imports, get_class_source |
| `HttpClient` | list_packages, get_cross_references |
| `User` | POJO field detection |

### APK (Android)

| Component | Tests |
|-----------|-------|
| `AndroidManifest.xml` | get_manifest, permissions |
| `MainActivity` | Activity detection, get_class_source |
| `ApiManager` | API key detection, network code |
| `DatabaseHelper` | SQL query search |
| `JadxTestApplication` | Application class detection |

## Expected Test Results

### list_classes
- JAR: 5 classes in `com.jadxtest.library.*`
- APK: 5 classes in `com.jadxtest.app.*`

### get_strings
- JAR: "JADX Test Library", "sk_test_12345678", etc.
- APK: "jadxtest.db", "api.jadxtest.com", etc.

### search_by_code
- Query "API_KEY" → finds ApiManager, HttpClient
- Query "CREATE TABLE" → finds DatabaseHelper
- Query "encrypt" → finds StringUtils

## Building from Source

```bash
# Build JAR
cd test-app-sources/jar
./build_jar.sh

# Build APK (requires Android SDK)
cd test-app-sources/apk
./build_apk.sh
```

## Note

Pre-built binaries are checked into git for CI convenience.
Source files are provided for reference and rebuilding.
