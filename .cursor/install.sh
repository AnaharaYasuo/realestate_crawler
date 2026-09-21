#!/usr/bin/env bash
# Idempotent environment bootstrap for the Realestate Crawler Cloud Agent.
# Runs after checkout (build/setup time) and its result is captured in the snapshot:
#   - installs Docker Engine, the Compose plugin and Task
#   - configures Docker for this nested VM (legacy iptables backend)
#   - generates a local .env
#   - builds the application image and initialises the MySQL schema
# Per-boot concerns (starting dockerd, bringing the stack up) live in start.sh.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

log() { echo "[install] $*"; }

# ---------------------------------------------------------------------------
# 1. System dependencies (Docker Engine + Compose plugin + fuse-overlayfs)
# ---------------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker Engine and the Compose plugin..."
  sudo install -m 0755 -d /etc/apt/keyrings
  export DEBIAN_FRONTEND=noninteractive
  sudo apt-get update -qq
  sudo apt-get install -y -qq ca-certificates curl gnupg >/dev/null
  if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
  fi
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -qq
  sudo apt-get install -y -qq --no-install-recommends \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin fuse-overlayfs \
    >/dev/null 2>&1 || sudo DEBIAN_FRONTEND=noninteractive dpkg --configure -a --force-confold
else
  log "Docker already installed: $(docker --version)"
fi

# ---------------------------------------------------------------------------
# 2. Task runner (Taskfile.dev) used by the project's workflows
# ---------------------------------------------------------------------------
if ! command -v task >/dev/null 2>&1; then
  log "Installing Task..."
  curl -fsSL https://github.com/go-task/task/releases/latest/download/task_linux_amd64.tar.gz -o /tmp/task.tgz
  sudo tar -xzf /tmp/task.tgz -C /usr/local/bin task
  sudo chmod +x /usr/local/bin/task
  rm -f /tmp/task.tgz
fi

# ---------------------------------------------------------------------------
# 3. Docker networking for this nested VM.
# The base VM enforces a legacy-iptables FORWARD DROP policy that only allows
# the default docker0 bridge. Docker 29 defaults to the nftables backend, whose
# rules are ignored by that policy, so traffic from Compose's custom bridge is
# dropped (containers cannot reach each other or the internet). Pinning Docker
# to the legacy iptables backend makes it program the same table the policy
# lives in, restoring both inter-container and outbound connectivity.
# ---------------------------------------------------------------------------
log "Pinning iptables/ip6tables to the legacy backend for Docker..."
sudo update-alternatives --set iptables /usr/sbin/iptables-legacy >/dev/null 2>&1 || true
sudo update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy >/dev/null 2>&1 || true
sudo mkdir -p /etc/docker
echo '{ "firewall-backend": "iptables" }' | sudo tee /etc/docker/daemon.json >/dev/null

# ---------------------------------------------------------------------------
# 4. Local environment file (Compose requires .env to exist).
# Uses the committed .env.example defaults; real secrets (Slack, Gemini) can be
# supplied via Cloud Agent secrets and are optional for core crawling.
# ---------------------------------------------------------------------------
if [ ! -f .env ]; then
  log "Creating .env from .env.example..."
  cp .env.example .env
  sed -i 's/^DB_PASSWORD=.*/DB_PASSWORD=mayumimayumi0413/; s/^DB_HOST=.*/DB_HOST=db/; s/^DB_PORT=.*/DB_PORT=3306/' .env
fi

# ---------------------------------------------------------------------------
# 5. Start dockerd (build-time only), build the app image and initialise the DB.
# These artifacts (image layers + MySQL data volume) are captured in the
# snapshot so that per-boot startup is fast.
# ---------------------------------------------------------------------------
sudo sysctl -w net.ipv4.ip_forward=1 net.bridge.bridge-nf-call-iptables=0 >/dev/null 2>&1 || true

if ! sudo docker info >/dev/null 2>&1; then
  log "Starting dockerd for build-time setup..."
  sudo bash -c 'nohup dockerd >/var/log/dockerd-install.log 2>&1 &'
  for i in $(seq 1 30); do
    sudo docker info >/dev/null 2>&1 && break
    sleep 2
  done
fi
sudo docker info >/dev/null 2>&1 || { log "ERROR: dockerd failed to start"; cat /var/log/dockerd-install.log 2>/dev/null | tail -20; exit 1; }

log "Building the application image (this can take a few minutes)..."
sudo docker compose build app

log "Initialising the MySQL schema..."
sudo docker compose up -d db
for i in $(seq 1 30); do
  sudo docker compose exec -T db mysqladmin ping -h localhost -uroot -prootpassword 2>/dev/null | grep -q "is alive" && break
  sleep 5
done
sudo docker compose up -d app
# Wait for the app container to be running, then apply migrations.
sleep 5
sudo docker compose exec -T app python src/crawler/manage.py migrate --no-input

log "Stopping build-time containers (images + db volume are retained in the snapshot)..."
sudo docker compose down

log "Install complete."
