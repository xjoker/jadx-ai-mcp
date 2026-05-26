# JADX-AI-MCP Docker Image with noVNC Support
# Uses pre-built base image for faster builds
#
# Build: docker build --platform=linux/amd64 -t jadx-ai-mcp -f docker/Dockerfile .
# Run:   docker run -d -p 6080:6080 -p 8650:8650 -v ./apks:/apks jadx-ai-mcp

# ============================================================================
# Global build arguments
# ============================================================================
ARG BASE_VERSION=1.2
ARG JADX_VERSION=1.5.5
ARG PLUGIN_VERSION=6.5.4
ARG DOCKER_PLATFORM=linux/amd64

# ============================================================================
# Stage 1: Build plugin JAR from current source for deterministic installs
# ============================================================================
FROM --platform=${DOCKER_PLATFORM} maven:3.9.9-eclipse-temurin-11 AS plugin-builder

ARG JADX_VERSION
ARG PLUGIN_VERSION
ARG DOCKER_PLATFORM

ENV TZ=UTC

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends unzip wget \
    && rm -rf /var/lib/apt/lists/*

COPY pom.xml .
COPY src ./src

# Install the exact JADX dependency expected by pom.xml before packaging.
RUN wget -q "https://github.com/skylot/jadx/releases/download/v${JADX_VERSION}/jadx-${JADX_VERSION}.zip" -O /tmp/jadx.zip \
    && unzip -q /tmp/jadx.zip -d /tmp/jadx \
    && JADX_JAR="$(find /tmp/jadx/lib -name 'jadx-*-all.jar' | head -1)" \
    && test -n "${JADX_JAR}" \
    && mvn -B install:install-file \
        -Dfile="${JADX_JAR}" \
        -DgroupId=io.github.skylot \
        -DartifactId=jadx-all \
        -Dversion="${JADX_VERSION}" \
        -Dpackaging=jar \
    && rm -rf /tmp/jadx.zip /tmp/jadx

RUN set -e; \
    for attempt in 1 2 3; do \
        mvn -B -Dmaven.wagon.http.retryHandler.count=3 -DskipTests clean package && break; \
        if [ "${attempt}" -eq 3 ]; then \
            exit 1; \
        fi; \
        echo "mvn package failed on attempt ${attempt}, retrying..." >&2; \
        sleep 5; \
    done \
    && BUILT_JAR=$(ls target/jadx-ai-mcp-*.jar 2>/dev/null | grep -v '\-shaded\.' | grep -v '\-sources\.' | head -1) \
    && test -n "${BUILT_JAR}" \
    && echo "Built plugin JAR: ${BUILT_JAR}" \
    && cp "${BUILT_JAR}" /build/jadx-ai-mcp.jar

# ============================================================================
# Stage 2: Runtime image
# Use pre-built base image with system dependencies
# Build base image separately when system deps change:
#   docker build --platform=linux/amd64 -t xjoker/jadx-ai-mcp-base:1.0 -f docker/Dockerfile.base .
# ============================================================================
ARG BASE_VERSION
FROM --platform=${DOCKER_PLATFORM} xjoker/jadx-ai-mcp-base:${BASE_VERSION}

ARG JADX_VERSION
ARG PLUGIN_VERSION
ARG DOCKER_PLATFORM

LABEL maintainer="xjoker"
LABEL description="JADX-AI-MCP with noVNC for headless server deployment"

# Additional environment variables
ENV JADX_API_PORT=8650 \
    JADX_MCP_PORT=8651 \
    JADX_MCP_AUTH_TOKEN=jadx-plugin-secret-token \
    JADX_MCP_AUTH_ENABLED=true \
    TZ=UTC

# ============================================================================
# Layer 1: Download JADX (changes only when JADX_VERSION changes)
# This layer can be updated independently by changing JADX_VERSION
# ============================================================================
RUN wget -q "https://github.com/skylot/jadx/releases/download/v${JADX_VERSION}/jadx-${JADX_VERSION}.zip" -O /tmp/jadx.zip \
    && unzip -q /tmp/jadx.zip -d /opt/jadx \
    && rm /tmp/jadx.zip \
    && chmod +x /opt/jadx/bin/*

# ============================================================================
# Layer 2: Create non-root user BEFORE plugin installation
# This ensures plugin is installed in /home/jadx/.jadx/plugins/
# ============================================================================
# Note: Use UID 1001 because base image (eclipse-temurin:25-jre-noble) has ubuntu user at UID 1000
RUN useradd -m -u 1001 jadx && \
    mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix && \
    mkdir -p /var/log/supervisor /apks && \
    chown -R jadx:jadx /opt/jadx /var/log/supervisor /apks

# Switch to jadx user for plugin installation
USER jadx

# ============================================================================
# Layer 3: Install plugin as jadx user from the builder stage artifact
# ============================================================================
# Copy the freshly built JAR from the deterministic builder stage.
COPY --from=plugin-builder --chown=jadx:jadx /build/jadx-ai-mcp.jar /tmp/jadx-ai-mcp.jar

RUN /opt/jadx/bin/jadx plugins --install-jar /tmp/jadx-ai-mcp.jar \
    && rm /tmp/jadx-ai-mcp.jar \
    && echo "Plugin version: ${PLUGIN_VERSION}" \
    && /opt/jadx/bin/jadx plugins --list

# ============================================================================
# Layer 4: MCP Server (need root for uv sync, then fix permissions)
# ============================================================================
USER root

# Reinstall pinned uv in the runtime image
# ARG CACHE_BUST forces this layer to rebuild when value changes
ARG CACHE_BUST=1
RUN PIP_BREAK_SYSTEM_PACKAGES=1 pip3 install --no-cache-dir --upgrade uv==0.10.9 && \
    uv --version

COPY jadx-mcp-server /opt/jadx/jadx-mcp-server
RUN cd /opt/jadx/jadx-mcp-server && uv sync --frozen \
    && chown -R jadx:jadx /opt/jadx/jadx-mcp-server

# ============================================================================
# Layer 5: Startup scripts (changes occasionally)
# ============================================================================
COPY docker/scripts/start.sh /start.sh
COPY docker/scripts/jadx-gui-wrapper.sh /opt/jadx/bin/jadx-gui-wrapper.sh
COPY docker/scripts/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chmod +x /start.sh /opt/jadx/bin/jadx-gui-wrapper.sh

# Switch back to jadx user for runtime
USER jadx

# Expose ports
# 6080: noVNC web interface
# 8650: JADX Plugin HTTP API (internal)
# 8651: MCP Server HTTP endpoint (external, connect LLMs here)
EXPOSE 6080 8650 8651

# Health check for both JADX Plugin API and MCP Server
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:${JADX_API_PORT}/health >/dev/null \
    && curl -fsS http://localhost:${JADX_MCP_PORT}/health >/dev/null \
    || exit 1

# Start services
CMD ["/start.sh"]
