#!/bin/sh
set -eu

# Extract nexus-main.jar from the Nexus3 Docker image for integration testing.
# The JAR serves as a realistic, publicly available test fixture for JADX decompilation.

mkdir -p temp
CONTAINER=$(docker create sonatype/nexus3:3.68.0)
docker cp "$CONTAINER:/opt/sonatype/nexus/lib/boot/nexus-main.jar" temp/nexus-main.jar
docker rm "$CONTAINER" >/dev/null
echo "Extracted nexus-main.jar to temp/"
