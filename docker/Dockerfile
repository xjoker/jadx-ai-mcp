# JADX-AI-MCP Docker Image with noVNC Support
# Uses pre-built base image for faster builds
#
# Build: docker build -t jadx-ai-mcp -f docker/Dockerfile .
# Run:   docker run -d -p 6080:6080 -p 8650:8650 -v ./apks:/apks jadx-ai-mcp

# ============================================================================
# Use pre-built base image with system dependencies
# Build base image separately when system deps change:
#   docker build -t xjoker/jadx-ai-mcp-base:1.0 -f docker/Dockerfile.base .
# ============================================================================
ARG BASE_VERSION=1.2
FROM xjoker/jadx-ai-mcp-base:${BASE_VERSION}

LABEL maintainer="xjoker"
LABEL description="JADX-AI-MCP with noVNC for headless server deployment"

# Additional environment variables
ENV JADX_API_PORT=8650

# ============================================================================
# Layer 1: Download JADX (changes only when JADX_VERSION changes)
# This layer can be updated independently by changing JADX_VERSION
# ============================================================================
ARG JADX_VERSION=1.5.3
RUN wget -q "https://github.com/skylot/jadx/releases/download/v${JADX_VERSION}/jadx-${JADX_VERSION}.zip" -O /tmp/jadx.zip \
    && unzip -q /tmp/jadx.zip -d /opt/jadx \
    && rm /tmp/jadx.zip \
    && chmod +x /opt/jadx/bin/*

# ============================================================================
# Layer 2: Install plugin using official jadx command
# Change PLUGIN_VERSION to force re-download of plugin when building
# ============================================================================
ARG PLUGIN_VERSION=6.0.7
RUN /opt/jadx/bin/jadx plugins --install "github:xjoker:jadx-ai-mcp" \
    && echo "Plugin version: ${PLUGIN_VERSION}"

# ============================================================================
# Layer 3: MCP Server (local copy instead of runtime pull)
# ============================================================================
COPY jadx-mcp-server /opt/jadx/jadx-mcp-server
RUN cd /opt/jadx/jadx-mcp-server && uv sync --frozen

# ============================================================================
# Layer 4: Startup scripts (changes occasionally)
# ============================================================================
COPY docker/scripts/start.sh /start.sh
COPY docker/scripts/jadx-gui-wrapper.sh /opt/jadx/bin/jadx-gui-wrapper.sh
COPY docker/scripts/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chmod +x /start.sh /opt/jadx/bin/jadx-gui-wrapper.sh

# ============================================================================
# Security: Create non-root user and set permissions
# ============================================================================
# Note: Use UID 1001 because base image (eclipse-temurin:25-jre-noble) has ubuntu user at UID 1000
RUN useradd -m -u 1001 jadx && \
    mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix && \
    chown -R jadx:jadx /opt/jadx /var/log/supervisor /apks
USER jadx

# Expose ports
# 6080: noVNC web interface
# 8650: JADX Plugin HTTP API (internal)
# 8651: MCP Server HTTP endpoint (external, connect LLMs here)
EXPOSE 6080 8650 8651

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${JADX_API_PORT}/health || exit 1

# Start services
CMD ["/start.sh"]
