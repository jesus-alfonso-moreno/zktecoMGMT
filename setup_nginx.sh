#!/bin/bash
# Setup Nginx for ZKTeco Management System
# This script installs and configures Nginx as reverse proxy for Gunicorn

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "$1"
}

log "${BLUE}========================================${NC}"
log "${BLUE}   Nginx Setup for ZKTeco System${NC}"
log "${BLUE}========================================${NC}"
log ""

# =============================================================================
# Step 1: Install Nginx
# =============================================================================
log "${YELLOW}Step 1: Installing Nginx...${NC}"

if command -v nginx &> /dev/null; then
    log "${GREEN}✓ Nginx already installed${NC}"
    nginx -v
else
    log "${YELLOW}Installing Nginx from EPEL repository...${NC}"
    sudo dnf install -y nginx

    if [ $? -eq 0 ]; then
        log "${GREEN}✓ Nginx installed successfully${NC}"
        nginx -v
    else
        log "${RED}✗ Failed to install Nginx${NC}"
        exit 1
    fi
fi

# =============================================================================
# Step 2: Read Configuration from .env
# =============================================================================
log ""
log "${YELLOW}Step 2: Reading configuration from .env...${NC}"

PROJECT_DIR="/home/almita/CCP/zktecoMGMT"
cd "$PROJECT_DIR"

if [ ! -f .env ]; then
    log "${RED}✗ .env file not found${NC}"
    exit 1
fi

# Source .env file
set -a
source .env
set +a

# Get server port (default 8000 if not set)
SERVER_PORT=${SERVER_PORT:-8000}
log "${GREEN}✓ Gunicorn port: $SERVER_PORT${NC}"

# Get allowed hosts
ALLOWED_HOSTS=${ALLOWED_HOSTS:-localhost,127.0.0.1}
# Get first host as server name
SERVER_NAME=$(echo $ALLOWED_HOSTS | cut -d',' -f1)
log "${GREEN}✓ Server name: $SERVER_NAME${NC}"

# =============================================================================
# Step 3: Create Nginx Configuration
# =============================================================================
log ""
log "${YELLOW}Step 3: Creating Nginx configuration...${NC}"

NGINX_CONF="/etc/nginx/conf.d/zkteco.conf"

sudo tee "$NGINX_CONF" > /dev/null << EOF
# ZKTeco Management System - Nginx Configuration

upstream gunicorn_zkteco {
    server 127.0.0.1:$SERVER_PORT fail_timeout=0;
}

server {
    listen 80;
    listen [::]:80;

    server_name $SERVER_NAME;

    client_max_body_size 4G;

    # Access and error logs
    access_log /var/log/nginx/zkteco_access.log;
    error_log /var/log/nginx/zkteco_error.log;

    # Serve static files directly
    location /static/ {
        alias $PROJECT_DIR/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Serve media files directly
    location /media/ {
        alias $PROJECT_DIR/media/;
        expires 7d;
    }

    # Proxy all other requests to Gunicorn
    location / {
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Host \$http_host;
        proxy_redirect off;

        # Increase timeout for long-running operations
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;

        # Pass to Gunicorn
        proxy_pass http://gunicorn_zkteco;
    }

    # Error pages
    error_page 500 502 503 504 /500.html;
    location = /500.html {
        root $PROJECT_DIR/templates/;
    }
}
EOF

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Nginx configuration created at $NGINX_CONF${NC}"
else
    log "${RED}✗ Failed to create Nginx configuration${NC}"
    exit 1
fi

# =============================================================================
# Step 4: Set Proper Permissions for Static Files
# =============================================================================
log ""
log "${YELLOW}Step 4: Setting permissions for static/media files...${NC}"

# Ensure nginx user can read static files
sudo chmod -R 755 "$PROJECT_DIR/staticfiles"
sudo chmod -R 755 "$PROJECT_DIR/media"

# Set SELinux context if SELinux is enabled
if command -v getenforce &> /dev/null; then
    SELINUX_STATUS=$(getenforce)
    if [ "$SELINUX_STATUS" != "Disabled" ]; then
        log "${YELLOW}Setting SELinux context for static files...${NC}"
        sudo chcon -R -t httpd_sys_content_t "$PROJECT_DIR/staticfiles" 2>/dev/null || true
        sudo chcon -R -t httpd_sys_content_t "$PROJECT_DIR/media" 2>/dev/null || true

        # Allow Nginx to connect to Gunicorn
        log "${YELLOW}Allowing Nginx to connect to network...${NC}"
        sudo setsebool -P httpd_can_network_connect 1

        log "${GREEN}✓ SELinux context configured${NC}"
    fi
fi

log "${GREEN}✓ Permissions set${NC}"

# =============================================================================
# Step 5: Test Nginx Configuration
# =============================================================================
log ""
log "${YELLOW}Step 5: Testing Nginx configuration...${NC}"

sudo nginx -t

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Nginx configuration test passed${NC}"
else
    log "${RED}✗ Nginx configuration test failed${NC}"
    exit 1
fi

# =============================================================================
# Step 6: Configure Firewall
# =============================================================================
log ""
log "${YELLOW}Step 6: Configuring firewall...${NC}"

# Check if firewalld is active (RHEL/AlmaLinux default)
if systemctl is-active --quiet firewalld; then
    log "${YELLOW}Configuring firewalld...${NC}"

    sudo firewall-cmd --permanent --add-service=http
    sudo firewall-cmd --permanent --add-service=https
    sudo firewall-cmd --reload

    log "${GREEN}✓ Firewall configured (firewalld)${NC}"

# Check if UFW is active
elif command -v ufw &> /dev/null && sudo ufw status | grep -q "Status: active"; then
    log "${YELLOW}Configuring UFW...${NC}"

    sudo ufw allow 'Nginx Full'

    log "${GREEN}✓ Firewall configured (UFW)${NC}"
else
    log "${YELLOW}~ No active firewall detected${NC}"
    log "${YELLOW}  You may need to manually open ports 80 and 443${NC}"
fi

# =============================================================================
# Step 7: Enable and Start Nginx
# =============================================================================
log ""
log "${YELLOW}Step 7: Starting Nginx...${NC}"

sudo systemctl enable nginx
sudo systemctl restart nginx

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Nginx enabled and started${NC}"
else
    log "${RED}✗ Failed to start Nginx${NC}"
    log "${YELLOW}Checking status...${NC}"
    sudo systemctl status nginx --no-pager
    exit 1
fi

# Wait for Nginx to fully start
sleep 2

# Check if Nginx is running
if sudo systemctl is-active --quiet nginx; then
    log "${GREEN}✓ Nginx is running${NC}"
else
    log "${RED}✗ Nginx is not running${NC}"
    exit 1
fi

# =============================================================================
# Step 8: Update Gunicorn to Listen Only on Localhost
# =============================================================================
log ""
log "${YELLOW}Step 8: Updating Gunicorn to listen on localhost only...${NC}"

GUNICORN_SERVICE="/etc/systemd/system/gunicorn.service"

# Update bind address from 0.0.0.0 to 127.0.0.1 (security improvement)
sudo sed -i "s/--bind 0.0.0.0:$SERVER_PORT/--bind 127.0.0.1:$SERVER_PORT/" "$GUNICORN_SERVICE"

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Gunicorn service updated${NC}"

    # Reload systemd and restart Gunicorn
    sudo systemctl daemon-reload
    sudo systemctl restart gunicorn

    if [ $? -eq 0 ]; then
        log "${GREEN}✓ Gunicorn restarted${NC}"
    else
        log "${RED}✗ Failed to restart Gunicorn${NC}"
        exit 1
    fi
else
    log "${YELLOW}~ Could not update Gunicorn bind address${NC}"
fi

# =============================================================================
# Step 9: Verify All Services
# =============================================================================
log ""
log "${YELLOW}Step 9: Verifying services...${NC}"

SERVICES=("nginx" "gunicorn" "django-q" "postgresql")
ALL_RUNNING=true

for service in "${SERVICES[@]}"; do
    if sudo systemctl is-active --quiet "$service"; then
        log "${GREEN}✓ $service is running${NC}"
    else
        log "${RED}✗ $service is NOT running${NC}"
        ALL_RUNNING=false
    fi
done

if [ "$ALL_RUNNING" = false ]; then
    log ""
    log "${RED}Some services are not running. Check logs with:${NC}"
    log "  sudo journalctl -u <service-name> -n 50"
    exit 1
fi

# =============================================================================
# Step 10: Test Static File Access
# =============================================================================
log ""
log "${YELLOW}Step 10: Testing static file access...${NC}"

# Test static file
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/static/js/task_progress.js)

if [ "$HTTP_CODE" = "200" ]; then
    log "${GREEN}✓ Static files are being served correctly${NC}"
else
    log "${RED}✗ Static file returned HTTP $HTTP_CODE${NC}"
    log "${YELLOW}Checking Nginx error log...${NC}"
    sudo tail -20 /var/log/nginx/zkteco_error.log
fi

# =============================================================================
# Completion Summary
# =============================================================================
log ""
log "${BLUE}========================================${NC}"
log "${GREEN}✓ Nginx Setup Complete!${NC}"
log "${BLUE}========================================${NC}"
log ""
log "${YELLOW}Configuration Summary:${NC}"
log "  Nginx config:        /etc/nginx/conf.d/zkteco.conf"
log "  Access log:          /var/log/nginx/zkteco_access.log"
log "  Error log:           /var/log/nginx/zkteco_error.log"
log "  Listening on:        0.0.0.0:80"
log "  Proxy to:            127.0.0.1:$SERVER_PORT (Gunicorn)"
log "  Static files:        $PROJECT_DIR/staticfiles/"
log "  Media files:         $PROJECT_DIR/media/"
log ""
log "${YELLOW}Access your application:${NC}"
log "  ${BLUE}http://$SERVER_NAME/${NC}"
log "  ${BLUE}http://$(hostname -I | awk '{print $1}')/${NC}"
log ""
log "${YELLOW}Useful commands:${NC}"
log "  Check Nginx status:     ${BLUE}sudo systemctl status nginx${NC}"
log "  Check Nginx config:     ${BLUE}sudo nginx -t${NC}"
log "  Reload Nginx:           ${BLUE}sudo systemctl reload nginx${NC}"
log "  Restart Nginx:          ${BLUE}sudo systemctl restart nginx${NC}"
log "  View access log:        ${BLUE}sudo tail -f /var/log/nginx/zkteco_access.log${NC}"
log "  View error log:         ${BLUE}sudo tail -f /var/log/nginx/zkteco_error.log${NC}"
log "  View Gunicorn log:      ${BLUE}sudo journalctl -u gunicorn -f${NC}"
log "  View Django-Q log:      ${BLUE}sudo journalctl -u django-q -f${NC}"
log ""
