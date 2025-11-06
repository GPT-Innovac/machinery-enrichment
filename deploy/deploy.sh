#!/usr/bin/env bash
set -euo pipefail

# Usage (on EC2): bash deploy.sh
APP_DIR=/opt/machinery-enrichment

cd "$APP_DIR"
python3.12 -m venv .venv || true
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn flask

# Ensure .env exists
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Set OPENAI_API_KEY in $APP_DIR/.env before starting."
fi

sudo systemctl restart machinery-dashboard || true
sudo systemctl enable machinery-dashboard || true
sudo systemctl status machinery-dashboard | cat
echo "Deployment finished. Visit http://<EC2_IP>/"

