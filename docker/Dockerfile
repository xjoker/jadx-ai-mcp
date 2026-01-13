# JADX-AI-MCP Docker Image with noVNC Support
# Enables browser-based access to jadx-gui on headless Linux servers
#
# Build: docker build -t jadx-ai-mcp -f docker/Dockerfile .
# Run:   docker run -d -p 6080:6080 -p 8650:8650 -v ./apks:/apks jadx-ai-mcp

# ============================================================================
# Layer Optimization Strategy:
# 1. Base image + apt packages (rarely changes)
# 2. JADX download (changes only when JADX_VERSION changes)
# 3. Plugin installation (changes when plugin version changes)
# 4. Scripts (changes occasionally - placed last for flexibility)
# ============================================================================

# Use JRE instead of JDK to reduce image size (~200MB smaller)
FROM eclipse-temurin:21-jre-jammy

LABEL maintainer="xjoker"
LABEL description="JADX-AI-MCP with noVNC for headless server deployment"

# Environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 \
    VNC_PORT=5900 \
    NOVNC_PORT=6080 \
    JADX_API_PORT=8650 \
    JADX_VERSION=1.5.3 \
    TZ=UTC

# ============================================================================
# Layer 1: System dependencies (rarely changes)
# ============================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # X11 and VNC
    xvfb \
    x11vnc \
    fluxbox \
    # Terminal + system monitor
    xterm \
    btop \
    # noVNC dependencies
    novnc \
    websockify \
    # Lightweight CJK font (instead of fonts-noto-cjk ~150MB)
    fonts-dejavu \
    fonts-liberation \
    fonts-wqy-zenhei \
    # Utilities
    wget \
    unzip \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# ============================================================================
# Layer 2: Create directories (rarely changes)
# ============================================================================
WORKDIR /opt/jadx
RUN mkdir -p /apks /var/log/supervisor

# ============================================================================
# Layer 3: Download JADX (changes only when JADX_VERSION changes)
# ============================================================================
RUN wget -q "https://github.com/skylot/jadx/releases/download/v${JADX_VERSION}/jadx-${JADX_VERSION}.zip" -O /tmp/jadx.zip \
    && unzip -q /tmp/jadx.zip -d /opt/jadx \
    && rm /tmp/jadx.zip \
    && chmod +x /opt/jadx/bin/*

# ============================================================================
# Layer 4: Install plugin using official jadx command
# ============================================================================
RUN /opt/jadx/bin/jadx plugins --install "github:xjoker:jadx-ai-mcp"

# ============================================================================
# Layer 5: Startup scripts (changes occasionally)
# ============================================================================
COPY docker/scripts/start.sh /start.sh
COPY docker/scripts/jadx-gui-wrapper.sh /opt/jadx/bin/jadx-gui-wrapper.sh
COPY docker/scripts/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chmod +x /start.sh /opt/jadx/bin/jadx-gui-wrapper.sh

# Expose ports
# 6080: noVNC web interface
# 8650: JADX AI-MCP HTTP API
EXPOSE 6080 8650

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${JADX_API_PORT}/health || exit 1

# Start services
CMD ["/start.sh"]
