# Layer 3 Integration Tests

Real integration tests against JADX container with actual JAR and APK files.

## Test Coverage

**Total: 26+ test cases**

### JAR Tests (11 cases)
- Upload and load JAR file
- List classes (expect 5)
- Get class source code
- Get methods and fields
- Code search (API_KEY, encrypt)
- Get JAR manifest
- Get entry points
- Get bytecode

### APK Tests (11 cases)  
- Upload and load APK file
- List classes (expect 5)
- Get AndroidManifest.xml
- Get main activity
- Get class source code
- Get methods and fields
- Code search (SQL, API domain)
- Get string resources
- Get Smali code

### Instance Management (4 cases)
- Add instance (real)
- Health check (real)
- Get instance info
- Concurrent requests

## Running Tests

### Local

```bash
# Start JADX container with fixtures mounted
docker run -d --name jadx-test \
  -p 8650:8650 \
  -p 8651:8651 \
  -v $(pwd)/tests/fixtures:/fixtures:ro \
  xjoker/jadx-ai-mcp:latest

# Wait for container to be ready
sleep 30

# Run integration tests
cd jadx-mcp-server
python -m pytest tests/integration/ -v --tb=short

# Cleanup
docker stop jadx-test && docker rm jadx-test
```

### CI (GitHub Actions)

1. Go to Actions → Test workflow
2. Click "Run workflow"
3. Select `test_layer: layer3` or `all`
4. View detailed test summary in workflow output

## Fixtures

Tests use pre-built fixtures from `/tests/fixtures/`:
- `jadx-test-library-1.0.0.jar` (6.5KB, 5 classes)
- `jadx-test-app-1.0.0.apk` (3.6KB, 5 classes)
