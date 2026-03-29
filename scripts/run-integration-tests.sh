#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.test.yaml"
PYTEST_DIR="${PROJECT_ROOT}/jadx-mcp-server"
PYTEST_BIN="${PYTEST_DIR}/.venv/bin/pytest"

DEFAULT_JADX_BASE_URL="http://127.0.0.1:8650"
DEFAULT_MCP_BASE_URL="http://127.0.0.1:8651"
JADX_BASE_URL="${JADX_BASE_URL:-${DEFAULT_JADX_BASE_URL}}"
MCP_BASE_URL="${MCP_BASE_URL:-${DEFAULT_MCP_BASE_URL}}"

TEST_IMAGE="${TEST_IMAGE:-jadx-ai-mcp:test}"
DOCKER_PLATFORM="${DOCKER_PLATFORM:-linux/amd64}"
PRIMARY_MCP_TOKEN="${MCP_AUTH_TOKEN:-token-viewer-xxxxx}"
SECONDARY_MCP_TOKEN="${MCP_SECONDARY_AUTH_TOKEN:-token-admin-zzzzz}"
JADX_PLUGIN_AUTH_TOKEN="${JADX_PLUGIN_AUTH_TOKEN:-test-plugin-token}"
TARGET="jar"
BUILD_IMAGE=0
KEEP_CONTAINERS=0

TMP_CONFIG_DIR=""
TEST_CONFIG_PATH=""
ACTIVE_PROJECT=""
ACTIVE_KEEP=0

if [[ -t 1 ]]; then
  RED=$'\033[0;31m'
  GREEN=$'\033[0;32m'
  YELLOW=$'\033[0;33m'
  BLUE=$'\033[0;34m'
  BOLD=$'\033[1m'
  RESET=$'\033[0m'
else
  RED=""
  GREEN=""
  YELLOW=""
  BLUE=""
  BOLD=""
  RESET=""
fi

RESULT_TARGETS=()
RESULT_CODES=()

usage() {
  cat <<'EOF'
Usage: scripts/run-integration-tests.sh [--target jar|apk|all] [--build] [--keep]

Options:
  --target  Test target to run. Default: jar
  --build   Rebuild the Docker image before running tests
  --keep    Keep the final test container running after pytest completes
EOF
}

log_info() {
  printf '%s[INFO]%s %s\n' "${BLUE}" "${RESET}" "$*"
}

log_warn() {
  printf '%s[WARN]%s %s\n' "${YELLOW}" "${RESET}" "$*"
}

log_error() {
  printf '%s[ERROR]%s %s\n' "${RED}" "${RESET}" "$*" >&2
}

log_success() {
  printf '%s[SUCCESS]%s %s\n' "${GREEN}" "${RESET}" "$*"
}

extract_host_from_url() {
  local url="$1"
  if [[ "${url}" =~ ^[a-zA-Z][a-zA-Z0-9+.-]*://\[([0-9A-Fa-f:]+)\](:[0-9]+)?(/.*)?$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return
  fi
  if [[ "${url}" =~ ^[a-zA-Z][a-zA-Z0-9+.-]*://([^/:]+)(:[0-9]+)?(/.*)?$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return
  fi
  printf '%s\n' ""
}

extract_port_from_url() {
  local url="$1"
  local default_port="$2"
  if [[ "${url}" =~ ^[a-zA-Z][a-zA-Z0-9+.-]*://\[[0-9A-Fa-f:]+\]:([0-9]+)(/.*)?$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return
  fi
  if [[ "${url}" =~ ^[a-zA-Z][a-zA-Z0-9+.-]*://[^/:]+:([0-9]+)(/.*)?$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return
  fi
  printf '%s\n' "${default_port}"
}

assert_local_url() {
  local name="$1"
  local url="$2"
  local host
  host="$(extract_host_from_url "${url}")"
  case "${host}" in
    localhost|127.0.0.1|::1)
      ;;
    "")
      log_error "${name} must be an absolute URL, got: ${url}"
      exit 1
      ;;
    *)
      log_error "${name} must point to localhost/127.0.0.1/::1 for local Docker tests, got host: ${host}"
      exit 1
      ;;
  esac
}

require_commands() {
  local cmd
  for cmd in docker curl; do
    if ! command -v "${cmd}" >/dev/null 2>&1; then
      log_error "Required command not found: ${cmd}"
      exit 1
    fi
  done

  if ! docker compose version >/dev/null 2>&1; then
    log_error "docker compose is required"
    exit 1
  fi

  if [[ ! -x "${PYTEST_BIN}" ]]; then
    log_error "pytest executable not found: ${PYTEST_BIN}"
    exit 1
  fi
}

ensure_image() {
  if [[ "${BUILD_IMAGE}" -eq 1 ]] || ! docker image inspect "${TEST_IMAGE}" >/dev/null 2>&1; then
    log_info "Building image ${TEST_IMAGE} from docker/Dockerfile"
    docker build \
      --platform "${DOCKER_PLATFORM}" \
      -t "${TEST_IMAGE}" \
      -f "${PROJECT_ROOT}/docker/Dockerfile" \
      "${PROJECT_ROOT}"
  else
    log_info "Using existing image ${TEST_IMAGE}"
  fi
}

prepare_test_config() {
  if [[ -n "${TEST_CONFIG_PATH}" ]]; then
    return
  fi

  TMP_CONFIG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/jadx-ai-mcp-integration.XXXXXX")"
  TEST_CONFIG_PATH="${TMP_CONFIG_DIR}/jadx-config.toml"

  cat > "${TEST_CONFIG_PATH}" <<EOF
[defaults]
request_timeout = 120
busy_timeout = 300
jadx_token = ""

[security]
allow_dynamic_instances = true

[[jadx_instances]]
name = "local"
host = "127.0.0.1"
port = 8650
default = true
enabled = true

[[users]]
name = "viewer"
token = "${PRIMARY_MCP_TOKEN}"
is_admin = false

[[users]]
name = "admin"
token = "${SECONDARY_MCP_TOKEN}"
is_admin = true
EOF
}

cleanup_active_project() {
  if [[ -z "${ACTIVE_PROJECT}" ]]; then
    return
  fi

  if [[ "${ACTIVE_KEEP}" -eq 1 ]]; then
    return
  fi

  docker compose \
    -p "${ACTIVE_PROJECT}" \
    -f "${COMPOSE_FILE}" \
    down -v --remove-orphans >/dev/null 2>&1 || true

  ACTIVE_PROJECT=""
}

cleanup_temp_config() {
  if [[ -n "${TMP_CONFIG_DIR}" && "${KEEP_CONTAINERS}" -eq 0 ]]; then
    rm -rf "${TMP_CONFIG_DIR}"
  fi
}

on_exit() {
  cleanup_active_project
  cleanup_temp_config
}

show_logs() {
  local project="$1"
  docker compose -p "${project}" -f "${COMPOSE_FILE}" logs --tail 200 || true
}

wait_for_health() {
  local project="$1"
  local deadline
  deadline=$(( $(date +%s) + 120 ))

  while (( $(date +%s) < deadline )); do
    if curl -fsS --max-time 5 "${JADX_BASE_URL%/}/health" >/dev/null 2>&1 \
      && curl -fsS --max-time 5 "${MCP_BASE_URL%/}/health" >/dev/null 2>&1; then
      log_success "Health checks passed for ${project}"
      return 0
    fi
    sleep 2
  done

  log_error "Timed out waiting for health checks: ${JADX_BASE_URL%/}/health and ${MCP_BASE_URL%/}/health"
  show_logs "${project}"
  return 1
}

run_pytest() {
  local target="$1"
  log_info "Running pytest for target=${target}"
  (
    cd "${PYTEST_DIR}"
    JADX_BASE_URL="${JADX_BASE_URL}" \
    MCP_BASE_URL="${MCP_BASE_URL}" \
    MCP_AUTH_TOKEN="${PRIMARY_MCP_TOKEN}" \
    MCP_SECONDARY_AUTH_TOKEN="${SECONDARY_MCP_TOKEN}" \
    "${PYTEST_BIN}" tests/integration -m integration -v --tb=short
  )
}

start_stack() {
  local target="$1"
  local project="$2"
  local host_jadx_port="$3"
  local host_mcp_port="$4"

  ACTIVE_PROJECT="${project}"

  docker compose -p "${project}" -f "${COMPOSE_FILE}" down -v --remove-orphans >/dev/null 2>&1 || true

  log_info "Starting test container for target=${target}"
  TEST_TARGET="${target}" \
  TEST_IMAGE="${TEST_IMAGE}" \
  TEST_CONTAINER_NAME="${project}" \
  TEST_CONFIG_PATH="${TEST_CONFIG_PATH}" \
  DOCKER_PLATFORM="${DOCKER_PLATFORM}" \
  HOST_JADX_PORT="${host_jadx_port}" \
  HOST_MCP_PORT="${host_mcp_port}" \
  HOST_JADX_BIND="127.0.0.1" \
  HOST_MCP_BIND="127.0.0.1" \
  JADX_PLUGIN_AUTH_TOKEN="${JADX_PLUGIN_AUTH_TOKEN}" \
  MCP_SERVER_URL="${MCP_BASE_URL}" \
  docker compose -p "${project}" -f "${COMPOSE_FILE}" up -d
}

record_result() {
  local target="$1"
  local exit_code="$2"
  RESULT_TARGETS+=("${target}")
  RESULT_CODES+=("${exit_code}")
}

print_summary() {
  local i
  printf '\n%sIntegration Test Summary%s\n' "${BOLD}" "${RESET}"
  for (( i=0; i<${#RESULT_TARGETS[@]}; i++ )); do
    if [[ "${RESULT_CODES[i]}" -eq 0 ]]; then
      printf '  %s%-3s%s %s\n' "${GREEN}" "PASS" "${RESET}" "${RESULT_TARGETS[i]}"
    else
      printf '  %s%-3s%s %s (exit %s)\n' "${RED}" "FAIL" "${RESET}" "${RESULT_TARGETS[i]}" "${RESULT_CODES[i]}"
    fi
  done
}

run_target() {
  local target="$1"
  local keep_after_run="$2"
  local project="jadx-integration-${target}"
  local pytest_exit=0
  local host_jadx_port
  local host_mcp_port

  host_jadx_port="$(extract_port_from_url "${JADX_BASE_URL}" "8650")"
  host_mcp_port="$(extract_port_from_url "${MCP_BASE_URL}" "8651")"

  ACTIVE_KEEP=0
  start_stack "${target}" "${project}" "${host_jadx_port}" "${host_mcp_port}"
  if ! wait_for_health "${project}"; then
    pytest_exit=1
    record_result "${target}" "${pytest_exit}"
    cleanup_active_project
    return "${pytest_exit}"
  fi

  if run_pytest "${target}"; then
    pytest_exit=0
  else
    pytest_exit=$?
  fi

  record_result "${target}" "${pytest_exit}"

  if [[ "${keep_after_run}" -eq 1 ]]; then
    ACTIVE_KEEP=1
    log_warn "Keeping container ${project} running on ${JADX_BASE_URL} and ${MCP_BASE_URL}"
    if [[ -n "${TEST_CONFIG_PATH}" ]]; then
      log_warn "Keeping generated test config: ${TEST_CONFIG_PATH}"
    fi
  else
    cleanup_active_project
  fi

  return "${pytest_exit}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      if [[ $# -lt 2 ]]; then
        log_error "--target requires a value"
        usage
        exit 1
      fi
      TARGET="$2"
      shift 2
      ;;
    --build)
      BUILD_IMAGE=1
      shift
      ;;
    --keep)
      KEEP_CONTAINERS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      log_error "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

case "${TARGET}" in
  jar|apk|all)
    ;;
  *)
    log_error "Unsupported target: ${TARGET}"
    usage
    exit 1
    ;;
esac

trap on_exit EXIT INT TERM

assert_local_url "JADX_BASE_URL" "${JADX_BASE_URL}"
assert_local_url "MCP_BASE_URL" "${MCP_BASE_URL}"
require_commands
prepare_test_config
ensure_image

overall_exit=0

if [[ "${TARGET}" == "all" ]]; then
  if run_target "jar" 0; then
    :
  else
    overall_exit=$?
  fi
  if run_target "apk" "${KEEP_CONTAINERS}"; then
    :
  else
    if [[ "${overall_exit}" -eq 0 ]]; then
      overall_exit=$?
    fi
  fi
else
  if run_target "${TARGET}" "${KEEP_CONTAINERS}"; then
    :
  else
    overall_exit=$?
  fi
fi

print_summary

if [[ "${overall_exit}" -eq 0 ]]; then
  log_success "Integration tests completed successfully"
else
  log_error "Integration tests failed"
fi

exit "${overall_exit}"
