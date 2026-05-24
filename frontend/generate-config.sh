#!/bin/sh

# Generates config.json inside the webroot using environment variables passed to Nginx container.
# If variables are not set, falls back to defaults.

PROXMOX_URL=${BACKEND_URL:-http://localhost:9091}
SYNOLOGY_URL=${SYNOLOGY_URL:-http://localhost:9090}
AUTH_KEY=${API_KEY:-my_secure_screensaver_key}

echo "Writing configuration..."
cat <<EOF > /usr/share/nginx/html/config.json
{
  "proxmoxUrl": "$PROXMOX_URL",
  "synologyUrl": "$SYNOLOGY_URL",
  "apiKey": "$AUTH_KEY"
}
EOF

echo "Frontend config generated successfully with:"
echo "Proxmox URL: $PROXMOX_URL"
echo "Synology URL: $SYNOLOGY_URL"
echo "API Key injected: [CONFIGURED]"
