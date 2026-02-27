#!/usr/bin/env bash
set -euo pipefail

# Verifies production SPA routing and auth API behavior for the Docker deployment.
#
# Usage:
#   scripts/verify_prod_spa_auth.sh [expected_commit]
#
# Optional env vars:
#   DOMAIN=debatecoachsa.southafricanorth.cloudapp.azure.com
#   AUTO_REDEPLOY=1      # redeploy backend if expected commit mismatches
#   RESTART_CADDY=1      # restart caddy when local checks pass but public /auth fails

EXPECTED_COMMIT="${1:-}"
DOMAIN="${DOMAIN:-debatecoachsa.southafricanorth.cloudapp.azure.com}"
AUTO_REDEPLOY="${AUTO_REDEPLOY:-0}"
RESTART_CADDY="${RESTART_CADDY:-0}"
HEALTH_TIMEOUT_SECS="${HEALTH_TIMEOUT_SECS:-90}"
COMPOSE_FILE="docker-compose.prod.yml"
BACKEND_CONTAINER="debate-coach-app"

banner() {
  printf "\n==> %s\n" "$1"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $1"
    exit 1
  fi
}

require_cmd git
require_cmd docker
require_cmd curl

wait_for_local_health() {
  local timeout="$1"
  local start now
  start="$(date +%s)"
  while true; do
    if curl -fsS --max-time 5 http://localhost:8000/api/health >/dev/null 2>&1; then
      return 0
    fi
    now="$(date +%s)"
    if (( now - start >= timeout )); then
      return 1
    fi
    sleep 2
  done
}

curl_headers_retry() {
  local url="$1"
  local out_file="$2"
  local attempts="${3:-15}"
  local i
  for ((i = 1; i <= attempts; i++)); do
    if curl -sS --max-time 10 -D "${out_file}" -o /dev/null "${url}"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

curl_body_and_status_retry() {
  local url="$1"
  local body_file="$2"
  local status_file="$3"
  local attempts="${4:-15}"
  local i
  for ((i = 1; i <= attempts; i++)); do
    if curl -sS --max-time 10 -o "${body_file}" -w '%{http_code}' "${url}" >"${status_file}"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

banner "Step 1: Repo and container version checks"
CURRENT_COMMIT="$(git rev-parse --short HEAD)"
echo "repo_commit=${CURRENT_COMMIT}"

if [[ -n "${EXPECTED_COMMIT}" && "${CURRENT_COMMIT}" != "${EXPECTED_COMMIT}" ]]; then
  echo "WARN: expected commit ${EXPECTED_COMMIT}, found ${CURRENT_COMMIT}"
  if [[ "${AUTO_REDEPLOY}" == "1" ]]; then
    banner "Commit mismatch and AUTO_REDEPLOY=1 -> redeploying backend"
    git pull
    docker compose -f "${COMPOSE_FILE}" build backend
    docker compose -f "${COMPOSE_FILE}" up -d --force-recreate backend
  else
    echo "INFO: skipping redeploy (set AUTO_REDEPLOY=1 to enforce)."
  fi
fi

if ! docker ps --format '{{.Names}}' | grep -qx "${BACKEND_CONTAINER}"; then
  echo "ERROR: backend container ${BACKEND_CONTAINER} is not running."
  echo "Run: docker compose -f ${COMPOSE_FILE} up -d --build backend"
  exit 1
fi

docker exec "${BACKEND_CONTAINER}" sh -lc "grep -n 'class SPAStaticFiles' /app/backend/app/main.py"
docker exec "${BACKEND_CONTAINER}" sh -lc "ls -l /app/static/index.html"

banner "Step 2: Local backend checks (before Caddy)"
if ! wait_for_local_health "${HEALTH_TIMEOUT_SECS}"; then
  echo "ERROR: backend did not become healthy within ${HEALTH_TIMEOUT_SECS}s"
  docker compose -f "${COMPOSE_FILE}" ps
  docker logs --tail=120 "${BACKEND_CONTAINER}" || true
  exit 1
fi

ROOT_HEADERS="$(mktemp)"
AUTH_HEADERS="$(mktemp)"
API_UNKNOWN_BODY="$(mktemp)"
API_STATUS_FILE="$(mktemp)"
trap 'rm -f "${ROOT_HEADERS}" "${AUTH_HEADERS}" "${API_UNKNOWN_BODY}" "${API_STATUS_FILE}"' EXIT

curl_headers_retry "http://localhost:8000/" "${ROOT_HEADERS}" 20
curl_headers_retry "http://localhost:8000/auth" "${AUTH_HEADERS}" 20
curl_body_and_status_retry "http://localhost:8000/api/unknown" "${API_UNKNOWN_BODY}" "${API_STATUS_FILE}" 20
API_STATUS="$(cat "${API_STATUS_FILE}")"

echo "[local /] $(head -n 1 "${ROOT_HEADERS}" | tr -d '\r')"
echo "[local /auth] $(head -n 1 "${AUTH_HEADERS}" | tr -d '\r')"
echo "[local /api/unknown] status=${API_STATUS} body=$(cat "${API_UNKNOWN_BODY}")"

if ! grep -qi '^HTTP/.* 200' "${ROOT_HEADERS}"; then
  echo "ERROR: local / is not 200"
  exit 1
fi
if ! grep -qi '^HTTP/.* 200' "${AUTH_HEADERS}"; then
  echo "ERROR: local /auth is not 200 (SPA fallback not active in running container)"
  exit 1
fi

banner "Step 3: Public URL checks via Caddy"
PUBLIC_ROOT_HEADERS="$(mktemp)"
PUBLIC_AUTH_HEADERS="$(mktemp)"
PUBLIC_ME_HEADERS="$(mktemp)"
trap 'rm -f "${ROOT_HEADERS}" "${AUTH_HEADERS}" "${API_UNKNOWN_BODY}" "${API_STATUS_FILE}" "${PUBLIC_ROOT_HEADERS}" "${PUBLIC_AUTH_HEADERS}" "${PUBLIC_ME_HEADERS}"' EXIT

curl_headers_retry "https://${DOMAIN}/" "${PUBLIC_ROOT_HEADERS}" 20
curl_headers_retry "https://${DOMAIN}/auth" "${PUBLIC_AUTH_HEADERS}" 20
curl_headers_retry "https://${DOMAIN}/api/auth/me" "${PUBLIC_ME_HEADERS}" 20

echo "[public /] $(head -n 1 "${PUBLIC_ROOT_HEADERS}" | tr -d '\r')"
echo "[public /auth] $(head -n 1 "${PUBLIC_AUTH_HEADERS}" | tr -d '\r')"
echo "[public /api/auth/me] $(head -n 1 "${PUBLIC_ME_HEADERS}" | tr -d '\r')"

PUBLIC_AUTH_OK=0
if grep -qi '^HTTP/.* 200' "${PUBLIC_AUTH_HEADERS}"; then
  PUBLIC_AUTH_OK=1
fi

if [[ "${PUBLIC_AUTH_OK}" -ne 1 && "${RESTART_CADDY}" == "1" ]]; then
  banner "Step 4: Public /auth failed and RESTART_CADDY=1 -> restarting caddy"
  docker restart caddy >/dev/null
  docker exec caddy cat /etc/caddy/Caddyfile | sed -n '1,80p'
  curl_headers_retry "https://${DOMAIN}/auth" "${PUBLIC_AUTH_HEADERS}" 20
  echo "[public /auth after caddy restart] $(head -n 1 "${PUBLIC_AUTH_HEADERS}" | tr -d '\r')"
fi

banner "Step 5: Final summary"
echo "PASS if:"
echo "  - local / = 200"
echo "  - local /auth = 200"
echo "  - public / = 200"
echo "  - public /auth = 200"
echo "  - public /api/auth/me = 401 (unauthenticated)"
echo
echo "Current results:"
echo "  $(head -n 1 "${ROOT_HEADERS}" | tr -d '\r')"
echo "  $(head -n 1 "${AUTH_HEADERS}" | tr -d '\r')"
echo "  $(head -n 1 "${PUBLIC_ROOT_HEADERS}" | tr -d '\r')"
echo "  $(head -n 1 "${PUBLIC_AUTH_HEADERS}" | tr -d '\r')"
echo "  $(head -n 1 "${PUBLIC_ME_HEADERS}" | tr -d '\r')"
