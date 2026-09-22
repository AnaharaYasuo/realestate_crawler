#!/usr/bin/env bash
# Per-boot startup for the Realestate Crawler Cloud Agent.
# Reconciles host networking, starts the Docker daemon and brings the core
# stack (MySQL + MinIO + Flask app) up. Safe to run repeatedly.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

log() { echo "[start] $*"; }

# ---------------------------------------------------------------------------
# 1. Host networking required for Docker's custom bridge in this nested VM.
#   - ip_forward: route container -> internet traffic.
#   - bridge-nf-call-iptables=0: let intra-bridge (container<->container)
#     traffic bypass the host's legacy FORWARD DROP policy.
#   - legacy iptables backend: see install.sh for the full explanation.
# ---------------------------------------------------------------------------
sudo sysctl -w net.ipv4.ip_forward=1 net.bridge.bridge-nf-call-iptables=0 >/dev/null 2>&1 || true
sudo update-alternatives --set iptables /usr/sbin/iptables-legacy >/dev/null 2>&1 || true
sudo update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy >/dev/null 2>&1 || true

# ---------------------------------------------------------------------------
# 2. Start the Docker daemon if it is not already running.
# ---------------------------------------------------------------------------
if ! sudo docker info >/dev/null 2>&1; then
  log "Starting dockerd..."
  sudo bash -c 'nohup dockerd >/var/log/dockerd.log 2>&1 &'
  for _ in $(seq 1 30); do
    sudo docker info >/dev/null 2>&1 && break
    sleep 2
  done
fi
sudo docker info >/dev/null 2>&1 || { log "ERROR: dockerd failed to start"; tail -20 /var/log/dockerd.log 2>/dev/null; exit 1; }

# ---------------------------------------------------------------------------
# 3. Ensure .env exists (in case install.sh output was not carried over).
# ---------------------------------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  # DB_PASSWORD left blank on purpose: docker-compose's default (or a DB_PASSWORD
  # Cloud Agent secret, which wins during substitution) applies to both MySQL and
  # the app, so no credential literal is written here.
  sed -i 's/^DB_HOST=.*/DB_HOST=db/; s/^DB_PORT=.*/DB_PORT=3306/; s/^DB_PASSWORD=.*/DB_PASSWORD=/' .env
fi

# ---------------------------------------------------------------------------
# 4. Bring up the core services (idempotent).
# ---------------------------------------------------------------------------
log "Bringing up db, minio and app..."
sudo docker compose up -d db minio app

# Wait for the database to accept connections (same readiness check the CI uses),
# then apply migrations. A DB-connection or migration failure fails the start
# hook rather than silently leaving the app on a stale schema.
sudo docker compose exec -T app python src/crawler/scripts/debug_tools/wait_for_db.py
sudo docker compose exec -T app python src/crawler/manage.py migrate --no-input

log "Stack is up. Flask app: http://localhost:8000 (API docs at /docs)."
