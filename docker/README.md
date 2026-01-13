# JADX-AI-MCP Docker Deployment

This Docker image enables running JADX-AI-MCP on headless Linux servers with browser-based access via noVNC.

## Architecture

```
┌─────────────────────────────────── Docker Container ────────────────────────────────┐
│   Xvfb (:99) ──► x11vnc (:5900) ──► noVNC (:6080) ──► Browser (Remote Desktop)     │
│       └──► jadx-gui + AI-MCP Plugin (:8650 HTTP API)                                │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Build Plugin

```bash
cd /path/to/jadx-ai-mcp
mvn clean package -DskipTests
```

### 2. Build Docker Image

```bash
docker build -t jadx-ai-mcp -f docker/Dockerfile .
```

### 3. Run Container

```bash
docker run -d \
  --name jadx-ai-mcp \
  -p 6080:6080 \
  -p 8650:8650 \
  -v $(pwd)/apks:/apks \
  jadx-ai-mcp
```

### 4. Access

- **Web Desktop**: http://localhost:6080
- **API Endpoint**: http://localhost:8650/jadx/api/v1/

## Ports

| Port | Service | Description |
|------|---------|-------------|
| 6080 | noVNC | Web-based VNC interface |
| 8650 | HTTP API | JADX AI-MCP plugin API |

## Volumes

| Path | Description |
|------|-------------|
| `/apks` | Mount your APK files here |
| `/root/.jadx` | JADX configuration and plugins |

## Usage with MCP Server

```bash
# Start the container
docker run -d -p 6080:6080 -p 8650:8650 -v ./apks:/apks jadx-ai-mcp

# Connect MCP server to container
python jadx-mcp-server/jadx_mcp_server.py --jadx-host localhost --jadx-port 8650
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JADX_MCP_BIND_ADDRESS` | 127.0.0.1 | Server bind address (set to `0.0.0.0` for Docker) |
| `JADX_MCP_PORT` | 8650 | Plugin HTTP API port |
| `JADX_MCP_AUTH_TOKEN` | (auto-generated) | Authentication token |
| `JADX_MCP_AUTH_ENABLED` | false | Enable authentication (`true`/`false`) |
| `VNC_PORT` | 5900 | Internal VNC port |
| `NOVNC_PORT` | 6080 | noVNC web port |

### Example with Authentication

```bash
docker run -d \
  --name jadx-ai-mcp \
  -p 6080:6080 \
  -p 8650:8650 \
  -e JADX_MCP_BIND_ADDRESS=0.0.0.0 \
  -e JADX_MCP_AUTH_ENABLED=true \
  -e JADX_MCP_AUTH_TOKEN=your-secret-token-here \
  -v $(pwd)/apks:/apks \
  jadx-ai-mcp
```

## Troubleshooting

### Check container logs
```bash
docker logs jadx-ai-mcp
```

### Access container shell
```bash
docker exec -it jadx-ai-mcp bash
```

### Check service status
```bash
docker exec jadx-ai-mcp supervisorctl status
```
