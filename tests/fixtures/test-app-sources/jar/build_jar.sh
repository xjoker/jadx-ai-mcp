#!/bin/bash
# Build test JAR file
# Usage: ./build_jar.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$SCRIPT_DIR/src"
OUT_DIR="$SCRIPT_DIR/out"
JAR_NAME="jadx-test-library-1.0.0.jar"

echo "=== Building JADX Test Library JAR ==="

# Clean and create output directory
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR/classes"

# Compile Java files
echo "Compiling Java sources..."
find "$SRC_DIR" -name "*.java" -print0 | xargs -0 javac -d "$OUT_DIR/classes" -source 11 -target 11 2>/dev/null || {
    echo "Note: Some Android-specific imports may fail, using basic compilation"
    find "$SRC_DIR" -name "*.java" -print0 | xargs -0 javac -d "$OUT_DIR/classes" -source 11 -target 11 -Xlint:none 2>&1 || true
}

# Create JAR
echo "Creating JAR file..."
cd "$OUT_DIR/classes"
jar cvf "../$JAR_NAME" . > /dev/null

# Copy to fixtures
cp "$OUT_DIR/$JAR_NAME" "$SCRIPT_DIR/../../$JAR_NAME"

echo ""
echo "=== Build Complete ==="
echo "Output: tests/fixtures/$JAR_NAME"
echo ""
echo "JAR Contents:"
jar tf "$OUT_DIR/$JAR_NAME" | head -20
