#!/usr/bin/env bash
# Ensures a given docker compose project is up; if not, relaunches it.
# Designed for cron (@reboot and periodic). Works with docker compose v2 or docker-compose v1.

set -Eeuo pipefail

# === CONFIG ===
COMPOSE_DIR="$HOME/PARKING_PI3"
COMPOSE_FILE="docker-compose.yml"
# List the services you expect to be up (must match service names in the compose file)
REQUIRED_SERVICES=("mosquitto-broker" "pi3-subscriber" "webpanel")
LOG_FILE="$COMPOSE_DIR/compose-watchdog.log"
LOCK_FILE="/tmp/compose-watchdog.PARKING_PI3.lock"
# Cron often has a minimal PATH; make sure docker is reachable
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

# === LOCK (prevents overlapping runs) ===
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "$(date -Is) [WARN] Another watchdog run is in progress, exiting." >> "$LOG_FILE"
  exit 0
fi

# === Compose command shim ===
compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    echo "$(date -Is) [ERROR] Docker Compose not found." >> "$LOG_FILE"
    exit 1
  fi
}

# === Core logic ===
cd "$COMPOSE_DIR"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "$(date -Is) [ERROR] $COMPOSE_FILE not found in $COMPOSE_DIR" >> "$LOG_FILE"
  exit 1
fi

# Get the list of currently *running* services for this project
mapfile -t RUNNING < <(compose -f "$COMPOSE_FILE" ps --services --filter "status=running" 2>/dev/null || true)

missing=()
for svc in "${REQUIRED_SERVICES[@]}"; do
  found="no"
  for r in "${RUNNING[@]}"; do
    if [[ "$r" == "$svc" ]]; then found="yes"; break; fi
  done
  [[ "$found" == "no" ]] && missing+=("$svc")
done

if [[ ${#missing[@]} -eq 0 ]]; then
  echo "$(date -Is) [OK] All services are running: ${REQUIRED_SERVICES[*]}" >> "$LOG_FILE"
  exit 0
fi

echo "$(date -Is) [INFO] Missing/not-running services: ${missing[*]}. Running 'compose up -d'…" >> "$LOG_FILE"

# `up -d` is idempotent: it starts what’s down, recreates failed ones, builds if needed.
if compose -f "$COMPOSE_FILE" up -d >> "$LOG_FILE" 2>&1; then
  echo "$(date -Is) [OK] Relaunched containers." >> "$LOG_FILE"
else
  echo "$(date -Is) [ERROR] Failed to relaunch containers." >> "$LOG_FILE"
  exit 1
fi

# Optional: re-check and report
sleep 2
mapfile -t RUNNING2 < <(compose -f "$COMPOSE_FILE" ps --services --filter "status=running" 2>/dev/null || true)
echo "$(date -Is) [INFO] Now running: ${RUNNING2[*]}" >> "$LOG_FILE"
