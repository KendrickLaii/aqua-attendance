#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> First boot setup for AQUA Attendance"

if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    cp .env.example .env
    echo "Created .env from .env.example"
    echo "Edit deploy/.env before continuing."
    exit 0
  else
    echo "Missing .env and .env.example in deploy folder."
    exit 1
  fi
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker and Docker Compose plugin"
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl gnupg lsb-release
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo systemctl enable docker
  sudo systemctl start docker
else
  echo "Docker already installed."
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker exists but current user cannot access daemon."
  echo "Run: sudo usermod -aG docker \$USER && newgrp docker"
  exit 1
fi

echo "==> Checking GHCR login (required for private images)"
if ! docker system info 2>/dev/null | grep -qi "Username"; then
  echo "You may not be logged in to a registry yet."
  echo "Run: echo \"<GITHUB_PAT>\" | docker login ghcr.io -u <github-username> --password-stdin"
fi

echo "==> Pulling and starting services"
docker compose -f docker-compose.prod.yml --env-file .env pull
docker compose -f docker-compose.prod.yml --env-file .env up -d
docker compose -f docker-compose.prod.yml --env-file .env ps

echo "First boot completed."
