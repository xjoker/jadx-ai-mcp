# JADX-AI-MCP Docker Image with noVNC Support
# Enables browser-based access to jadx-gui on headless Linux servers
#
# Build: docker build -t jadx-ai-mcp -f docker/Dockerfile .
# Run:   docker run -d -p 6080:6080 -p 8650:8650 -v ./apks:/apks jadx-ai-mcp

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

# Install dependencies in single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    # X11 and VNC
    xvfb \
    x11vnc \
    fluxbox \
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

# Create working directories
WORKDIR /opt/jadx
RUN mkdir -p /apks /root/.jadx/plugins/dropins /var/log/supervisor

# Download and extract JADX
RUN wget -q "https://github.com/skylot/jadx/releases/download/v${JADX_VERSION}/jadx-${JADX_VERSION}.zip" -O /tmp/jadx.zip \
    && unzip -q /tmp/jadx.zip -d /opt/jadx \
    && rm /tmp/jadx.zip \
    && chmod +x /opt/jadx/bin/*

# Copy the AI-MCP plugin (will be built and copied during build)
# Note: You need to build the plugin first: mvn clean package
COPY target/jadx-ai-mcp-*.jar /root/.jadx/plugins/dropins/

# Copy startup scripts
COPY docker/scripts/start.sh /start.sh
COPY docker/scripts/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chmod +x /start.sh

# Expose ports
# 6080: noVNC web interface
# 8650: JADX AI-MCP HTTP API
EXPOSE 6080 8650

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${JADX_API_PORT}/jadx/api/v1/apk/info || exit 1

# Start services
CMD ["/start.sh"]
