# JAR/Spring Boot Analysis

A skill for analyzing JAR files and Spring Boot applications using JADX-AI-MCP tools.

## Overview

This skill guides systematic analysis of JAR files, including standard Java libraries, executable JARs, and Spring Boot fat JARs. It leverages JAR-specific tools that are distinct from APK analysis tools.

## Analysis Workflow

### Step 1: Identify File Type

Always start by identifying the file type to ensure correct tool selection.

```python
file_info = get_file_info()
```

Expected response for JAR files:
```json
{
  "file_type": "jar",
  "file_category": "java",
  "recommended_tools": ["jar_get_manifest", "jar_get_entry_points", "jar_get_services", "get_class_source"]
}
```

**Important**: If `file_type` is `apk`, `aar`, or `dex`, use Android-specific tools instead. JAR tools will return `NOT_APPLICABLE` for non-JAR files.

### Step 2: Read Manifest

Extract metadata from `META-INF/MANIFEST.MF`.

```python
manifest = jar_get_manifest()
```

Key attributes to examine:
- **Main-Class**: Entry point for executable JARs
- **Start-Class**: Actual application class for Spring Boot
- **Implementation-Title/Version**: Library identification
- **Spring-Boot-Version**: Indicates Spring Boot packaging
- **Bundle-SymbolicName**: OSGi bundle identifier

### Step 3: Discover Entry Points

Find all possible entry points in the JAR.

```python
entry_points = jar_get_entry_points()
```

This tool discovers:
1. **Main-Class** from MANIFEST.MF (standard executable JAR)
2. **Start-Class** for Spring Boot (actual application class)
3. **@SpringBootApplication** annotated classes
4. **public static void main(String[])** methods

The `primary_entry` field recommends the best starting point for analysis.

### Step 4: Analyze Dependencies

Discover embedded dependencies and library versions.

```python
dependencies = jar_get_dependencies()
```

Sources analyzed:
- `META-INF/maven/*/pom.properties` - Maven coordinates
- `MANIFEST.MF Class-Path` entries
- `BOOT-INF/lib/*.jar` - Spring Boot nested dependencies

### Step 5: Discover SPI Services

Find Java Service Provider Interface implementations.

```python
services = jar_get_services()
```

Common SPI patterns:
- `java.sql.Driver` - JDBC drivers
- `org.slf4j.spi.SLF4JServiceProvider` - Logging frameworks
- `javax.servlet.ServletContainerInitializer` - Servlet containers

### Step 6: Analyze Class Bytecode

For low-level analysis of specific classes.

```python
bytecode = jar_get_bytecode("com.example.Main")
```

Returns JVM class structure similar to `javap` output, including:
- Field declarations with types
- Method signatures
- Access modifiers

## Spring Boot Fat JAR Analysis

Spring Boot fat JARs have a special structure requiring focused analysis.

### Structure Overview

```
my-app.jar
├── META-INF/
│   └── MANIFEST.MF          # Contains Start-Class, Spring-Boot-Version
├── BOOT-INF/
│   ├── classes/             # Application classes
│   └── lib/                 # Nested dependency JARs
└── org/springframework/boot/loader/  # Spring Boot launcher
```

### Spring Boot Workflow

```
1. jar_get_manifest()
   └── Look for: Start-Class, Spring-Boot-Version, Spring-Boot-Lib

2. jar_get_entry_points()
   └── Find @SpringBootApplication class (priority 1)

3. jar_get_dependencies()
   └── Examine BOOT-INF/lib/ for all dependencies

4. get_class_source(primary_entry)
   └── Analyze the main application class

5. list_classes()
   └── Browse classes under BOOT-INF/classes/
```

### Identifying Spring Boot Applications

Indicators of a Spring Boot JAR:
- Manifest contains `Spring-Boot-Version`
- Manifest contains `Start-Class` (different from Main-Class)
- Has `BOOT-INF/` directory structure
- Main-Class is `org.springframework.boot.loader.JarLauncher`

## Common Analysis Patterns

### Library JAR Analysis

For analyzing third-party libraries:

```
1. jar_get_manifest() → Get version, vendor info
2. jar_get_services() → Discover SPI extensions
3. list_classes() → Browse public API classes
4. get_class_source() → Examine specific classes
```

### Executable JAR Analysis

For analyzing runnable applications:

```
1. jar_get_entry_points() → Find main() method
2. get_class_source(main_class) → Analyze entry point
3. get_xrefs(main_class) → Trace execution flow
4. search_code("Pattern") → Find specific functionality
```

### Security Audit

For security-focused analysis:

```
1. jar_get_dependencies() → Check for vulnerable versions
2. search_code("password|secret|key") → Find sensitive data
3. jar_get_services() → Check custom providers
4. jar_get_bytecode() → Low-level verification
```

## Tool Reference

| Tool | Purpose | JAR Only |
|------|---------|:--------:|
| `get_file_info` | Identify file type and get recommendations | No |
| `jar_get_manifest` | Read MANIFEST.MF metadata | Yes |
| `jar_get_entry_points` | Find Main-Class, Spring Boot, main() | Yes |
| `jar_get_services` | Discover SPI service providers | Yes |
| `jar_get_dependencies` | Analyze embedded dependencies | Yes |
| `jar_get_bytecode` | Get class structure (javap-like) | No* |
| `get_class_source` | Decompiled Java source code | No |
| `list_classes` | Browse all classes | No |

*`jar_get_bytecode` works for both JAR and APK but returns different formats.

## NOT_APPLICABLE Responses

When using JAR-specific tools on APK/AAR/DEX files:

```json
{
  "status": "NOT_APPLICABLE",
  "reason": "JAR Manifest is only available for JAR files",
  "file_type": "apk",
  "alternatives": [{"tool": "apk_get_manifest", "description": "..."}]
}
```

Always check the `alternatives` field for appropriate tools.

## Example Session

Complete analysis of a Spring Boot application:

```
User: Analyze this JAR file

1. get_file_info()
   → file_type: "jar", Spring Boot detected

2. jar_get_manifest()
   → Start-Class: com.example.Application
   → Spring-Boot-Version: 3.2.0

3. jar_get_entry_points()
   → primary_entry: com.example.Application
   → @SpringBootApplication found

4. jar_get_dependencies()
   → 150 nested JARs in BOOT-INF/lib/
   → spring-core, spring-web, jackson, etc.

5. get_class_source("com.example.Application")
   → Decompiled main application class
   → Identifies @ComponentScan, @EnableAutoConfiguration

6. list_classes(filter="com.example")
   → Browse application packages

7. search_code("@RestController")
   → Find API endpoints

8. Analyze each controller class...
```

## Best Practices

1. **Always start with `get_file_info()`** to confirm file type
2. **Use `jar_get_entry_points()`** to find the best starting point
3. **Check dependencies** for known vulnerabilities
4. **Follow the `primary_entry`** recommendation for efficient analysis
5. **Use `get_class_source()`** after identifying target classes
6. **Combine with `search_code()`** for pattern-based discovery
