#!/bin/bash
set -e

echo "=========================================="
echo "Updating CascadeCAD Systemd & Nginx Configs..."
echo "=========================================="

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Update Systemd Service File
SERVICE_SRC="$PROJECT_DIR/deploy/systemd/cascade-cad.service"
SERVICE_DEST="/etc/systemd/system/cascade-cad.service"

if [ -f "$SERVICE_SRC" ]; then
    echo "Copying updated systemd service file..."
    sudo cp "$SERVICE_SRC" "$SERVICE_DEST"
    echo "Reloading systemd daemon..."
    sudo systemctl daemon-reload
    sudo systemctl restart cascade-cad.service
else
    echo "Warning: $SERVICE_SRC not found. Skipping systemd update."
fi

# 2. Update Nginx Snippet File
SNIPPET_SRC="$PROJECT_DIR/deploy/nginx/cascade-cad.conf"
SNIPPET_DEST_DIR="/etc/nginx/snippets"
SNIPPET_DEST="$SNIPPET_DEST_DIR/cascade-cad.conf"

sudo mkdir -p "$SNIPPET_DEST_DIR"

if [ -f "$SNIPPET_SRC" ]; then
    echo "Copying Nginx snippet from deploy folder to $SNIPPET_DEST..."
    sudo cp "$SNIPPET_SRC" "$SNIPPET_DEST"
else
    echo "Deploy snippet not found. Creating standard Nginx snippet..."
    sudo tee "$SNIPPET_DEST" > /dev/null << 'EOF'
# CascadeCAD Static Assets (Fixes MIME type errors)
location /cascade-cad/static/ {
    alias /home/jayson_tolleson/Cascade/webcad_xbf/static/;
    expires 30d;
    add_header Cache-Control "public, no-transform";
}

location /static/ {
    alias /home/jayson_tolleson/Cascade/webcad_xbf/static/;
    expires 30d;
    add_header Cache-Control "public, no-transform";
}

# Route CascadeCAD API calls to Quart backend (Port 8790)
location /cascade-cad/api/ {
    proxy_pass http://127.0.0.1:8790/cascade-cad/api/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# Route CascadeCAD WebSockets
location /cascade-cad/ws/ {
    proxy_pass http://127.0.0.1:8790/cascade-cad/ws/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

# Route CascadeCAD main web app pages/assets
location /cascade-cad {
    proxy_pass http://127.0.0.1:8790;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
EOF
fi

# 3. Verify Include in Main Nginx Site File
NGINX_SITE="/etc/nginx/sites-available/broadcast"
if [ -f "$NGINX_SITE" ]; then
    if ! grep -q "cascade-cad.conf" "$NGINX_SITE"; then
        echo "Adding include directive to $NGINX_SITE..."
        sudo sed -i '/ssl_certificate_key/a \    # CascadeCAD Modular Configuration Include\n    include /etc/nginx/snippets/cascade-cad.conf;\n' "$NGINX_SITE"
    else
        echo "Nginx include directive already exists in $NGINX_SITE."
    fi
fi

echo "Testing Nginx configuration..."
sudo nginx -t

echo "Reloading Nginx..."
sudo systemctl reload nginx

echo "=========================================="
echo "Configuration update complete!"
echo "=========================================="
sudo systemctl status cascade-cad.service --no-pager
