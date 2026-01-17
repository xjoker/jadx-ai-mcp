FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY jadx_mcp_server.py ./

# Install dependencies
RUN uv sync --frozen

# Create config directory
RUN mkdir -p data/config

# Expose MCP port
EXPOSE 8651

# Run MCP server with config file
ENV JADX_MCP_HOST=0.0.0.0
ENV JADX_MCP_PORT=8651
CMD ["uv", "run", "python", "jadx_mcp_server.py", "--http", "--host", "0.0.0.0", "--port", "8651", "--config", "/app/data/config/jadx-config.toml"]
