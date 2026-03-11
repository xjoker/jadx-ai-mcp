#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

IMAGE_TAG="jadx-ai-mcp:local-benchmark"
CONTAINER_NAME="jadx-benchmark"
LABEL="baseline"
APK_DIR="$REPO_ROOT/temp"
RESULTS_DIR="$REPO_ROOT/temp/benchmark-results"
CONFIG_PATH="$REPO_ROOT/benchmarks/default_matrix.json"
PLUGIN_PORT="8650"
MCP_PORT="8651"
KEEP_CONTAINER="0"
BUILD_IMAGE="0"
PLUGIN_AUTH_TOKEN=""
MCP_AUTH_TOKEN=""
COMPARE_ARG=""

resolve_host_path() {
  case "$1" in
    "")
      printf '%s' ""
      ;;
    /*)
      printf '%s' "$1"
      ;;
    *)
      printf '%s/%s' "$REPO_ROOT" "$1"
      ;;
  esac
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --build)
      BUILD_IMAGE="1"
      shift
      ;;
    --keep-container)
      KEEP_CONTAINER="1"
      shift
      ;;
    --image)
      IMAGE_TAG="$2"
      shift 2
      ;;
    --container-name)
      CONTAINER_NAME="$2"
      shift 2
      ;;
    --label)
      LABEL="$2"
      shift 2
      ;;
    --apk-dir)
      APK_DIR="$2"
      shift 2
      ;;
    --results-dir)
      RESULTS_DIR="$2"
      shift 2
      ;;
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --plugin-port)
      PLUGIN_PORT="$2"
      shift 2
      ;;
    --mcp-port)
      MCP_PORT="$2"
      shift 2
      ;;
    --plugin-auth-token)
      PLUGIN_AUTH_TOKEN="$2"
      shift 2
      ;;
    --mcp-auth-token)
      MCP_AUTH_TOKEN="$2"
      shift 2
      ;;
    --compare)
      COMPARE_ARG="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

APK_DIR=$(resolve_host_path "$APK_DIR")
RESULTS_DIR=$(resolve_host_path "$RESULTS_DIR")
CONFIG_PATH=$(resolve_host_path "$CONFIG_PATH")
if [ -n "$COMPARE_ARG" ]; then
  COMPARE_ARG=$(resolve_host_path "$COMPARE_ARG")
fi

mkdir -p "$RESULTS_DIR"

HOST_GIT_COMMIT=$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo "unknown")
HOST_GIT_BRANCH=$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

to_container_path() {
  case "$1" in
    "$RESULTS_DIR"/*)
      printf '/results/%s' "${1#"$RESULTS_DIR"/}"
      ;;
    "$REPO_ROOT"/*)
      printf '/workspace/%s' "${1#"$REPO_ROOT"/}"
      ;;
    /workspace/*|/results/*)
      printf '%s' "$1"
      ;;
    *)
      printf '%s' "$1"
      ;;
  esac
}

cleanup() {
  if [ "$KEEP_CONTAINER" = "0" ]; then
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

if [ "$BUILD_IMAGE" = "1" ]; then
  docker build -t "$IMAGE_TAG" -f "$REPO_ROOT/docker/Dockerfile.local" "$REPO_ROOT"
fi

docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

docker run -d \
  --name "$CONTAINER_NAME" \
  -p "$PLUGIN_PORT:8650" \
  -p "$MCP_PORT:8651" \
  -v "$APK_DIR:/apks:ro" \
  -v "$REPO_ROOT:/workspace:ro" \
  -v "$RESULTS_DIR:/results" \
  "$IMAGE_TAG" >/dev/null

echo "Waiting for plugin API..."
ATTEMPTS=0
until docker exec "$CONTAINER_NAME" sh -lc 'curl -fsS http://127.0.0.1:8650/health >/dev/null'; do
  ATTEMPTS=$((ATTEMPTS + 1))
  if [ "$ATTEMPTS" -ge 120 ]; then
    echo "Plugin API did not become ready in time" >&2
    exit 1
  fi
  sleep 2
done

CONTAINER_CONFIG_PATH=$(to_container_path "$CONFIG_PATH")
CONTAINER_COMPARE_PATH=""
if [ -n "$COMPARE_ARG" ]; then
  CONTAINER_COMPARE_PATH=$(to_container_path "$COMPARE_ARG")
fi

RUN_CMD="/opt/jadx/jadx-mcp-server/.venv/bin/python /workspace/benchmarks/run_benchmark.py \
  --config \"$CONTAINER_CONFIG_PATH\" \
  --label \"$LABEL\" \
  --results-dir /results \
  --plugin-base-url http://127.0.0.1:8650 \
  --mcp-base-url http://127.0.0.1:8651 \
  --image-tag \"$IMAGE_TAG\" \
  --git-commit \"$HOST_GIT_COMMIT\" \
  --git-branch \"$HOST_GIT_BRANCH\""

if [ -n "$PLUGIN_AUTH_TOKEN" ]; then
  RUN_CMD="$RUN_CMD --plugin-auth-token \"$PLUGIN_AUTH_TOKEN\""
fi

if [ -n "$MCP_AUTH_TOKEN" ]; then
  RUN_CMD="$RUN_CMD --mcp-auth-token \"$MCP_AUTH_TOKEN\""
fi

if [ -n "$CONTAINER_COMPARE_PATH" ]; then
  RUN_CMD="$RUN_CMD --compare \"$CONTAINER_COMPARE_PATH\""
fi

docker exec "$CONTAINER_NAME" sh -lc "$RUN_CMD"

echo "Results written to: $RESULTS_DIR"
