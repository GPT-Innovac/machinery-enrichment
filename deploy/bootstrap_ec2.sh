#!/usr/bin/env bash
set -euo pipefail

# Usage: sudo bash bootstrap_ec2.sh

sudo dnf update -y
sudo dnf install -y python3.12 python3.12-venv nginx git

APP_DIR=/opt/machinery-enrichment
sudo mkdir -p "$APP_DIR"
sudo chown -R ec2-user:ec2-user "$APP_DIR"

cat <<'CONF' | sudo tee /etc/nginx/conf.d/machinery-dashboard.conf >/dev/null
server {
  listen 80;
  server_name _;
  client_max_body_size 20m;

  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
CONF

sudo nginx -t
sudo systemctl enable --now nginx

cat <<'UNIT' | sudo tee /etc/systemd/system/machinery-dashboard.service >/dev/null
[Unit]
Description=Machinery Enrichment Dashboard
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/opt/machinery-enrichment
Environment="PATH=/opt/machinery-enrichment/.venv/bin"
ExecStart=/opt/machinery-enrichment/.venv/bin/gunicorn -w 3 -b 127.0.0.1:8000 web_dashboard.app:app
Restart=always

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
echo "Bootstrap complete. Copy your project to $APP_DIR and run deploy.sh on the instance."

