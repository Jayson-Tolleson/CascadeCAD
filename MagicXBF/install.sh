#!/bin/bash

# ==============================================================================
# MagicXBF Universal Installer
# ==============================================================================

# 1. ROOT PRIVILEGE CHECK
# Ensure the script is run with sudo
if [ "$EUID" -ne 0 ]; then
  echo "❌ Error: Please run this installer as root (e.g., sudo ./install.sh)"
  exit 1
fi

echo "🚀 Starting MagicXBF installation..."

# ==============================================================================
# CONFIGURATION VARIABLES
# Change these if deploying to a different environment
# ==============================================================================
APP_NAME="magicxbf"
APP_DIR="/opt/magicxbf"
APP_USER="magicxbf"
VENV_DIR="$APP_DIR/.venv"
PORT="8000"

# ==============================================================================
# STEP 1: SYSTEM USER & PERMISSIONS
# ==============================================================================
echo "⚙️  Configuring system user and directories..."

# Create a dedicated system user with no login shell (for security) if it doesn't exist
if id "$APP_USER" &>/dev/null; then
    echo "User $APP_USER already exists."
else
    useradd -r -s /bin/false $APP_USER
    echo "Created system user: $APP_USER"
fi

# Ensure the app directory exists (assuming files are already copied here)
mkdir -p $APP_DIR

# ==============================================================================
# STEP 2: PYTHON VIRTUAL ENVIRONMENT & DEPENDENCIES
# ==============================================================================
echo "🐍 Setting up Python virtual environment..."

# Check if python3-venv is installed (Debian/Ubuntu specific)
if ! dpkg -s python3-venv >/dev/null 2>&1; then
    apt-get update && apt-get install -y python3-venv
fi

# Create the .venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv $VENV_DIR
fi

# Upgrade pip and install requirements
$VENV_DIR/bin/pip install --upgrade pip
if [ -f "$APP_DIR/requirements.txt" ]; then
    $VENV_DIR/bin/pip install -r $APP_DIR/requirements.txt
fi

# Ensure Hypercorn is installed
$VENV_DIR/bin/pip install hypercorn

# Hand ownership of the entire app directory over to the dedicated user
chown -R $APP_USER:$APP_USER $APP_DIR

# ==============================================================================
# STEP 3: SYSTEMD SERVICE CONFIGURATION
# ==============================================================================
echo "🛠️  Creating systemd service..."

# Create the service file using a "Here Document" (EOF)
cat << EOF > /etc/systemd/system/${APP_NAME}.service
[Unit]
Description=MagicXBF Hypercorn Server
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV_DIR/bin/hypercorn app:app --bind 127.0.0.1:$PORT --workers 1
Restart=always
RestartSec=3
TimeoutStartSec=60
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd to recognize the new file
systemctl daemon-reload
systemctl enable ${APP_NAME}.service
systemctl restart ${APP_NAME}.service

# ==============================================================================
# STEP 4: NGINX CONFIGURATION (DROP-IN)
# ==============================================================================
echo "🌐 Configuring Nginx..."

# Create a dedicated snippet for the MagicXBF routes
cat << 'EOF' > /etc/nginx/snippets/magicxbf-cad.conf
# MagicXBF CAD App Static Files
location /magicxbf-cad/static/ {
    alias /opt/magicxbf/static/;
    expires 30d;
    add_header Cache-Control "public, max-age=2592000";
}

# MagicXBF CAD App Proxy Block
location /magicxbf-cad/ {
    proxy_pass http://127.0.0.1:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
EOF

echo "⚠️  Nginx snippet created at /etc/nginx/snippets/magicxbf-cad.conf."
echo "⚠️  To activate, ensure 'include /etc/nginx/snippets/magicxbf-cad.conf;' is in your main site's server block."

# Test and reload Nginx (ignoring errors if snippet isn't included yet)
nginx -t && systemctl reload nginx

echo "✅ Installation Complete! The service is running on 127.0.0.1:$PORT"
