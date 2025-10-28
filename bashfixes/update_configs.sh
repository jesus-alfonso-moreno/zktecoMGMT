#!/bin/bash
# Update all configurations to use /opt/CCP/zktecoMGMT
# Run this script after moving the project

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Variables
PROJECT_DIR="/opt/CCP/zktecoMGMT"
VENV_NAME="zkteco_env"

# =============================================================================
# Logging Setup
# =============================================================================
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/update_configs_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

log "${BLUE}========================================${NC}"
log "${BLUE}   Update Configurations${NC}"
log "${BLUE}========================================${NC}"
log ""
log "${GREEN}Log file: $LOG_FILE${NC}"
log "Started at: $(date '+%Y-%m-%d %H:%M:%S')"
log ""

# =============================================================================
# Step 1: Stop all services
# =============================================================================
log "${YELLOW}Step 1: Stopping services...${NC}"

sudo systemctl stop nginx 2>&1 | tee -a "$LOG_FILE"
log "${GREEN}✓ Nginx stopped${NC}"

sudo systemctl stop gunicorn 2>&1 | tee -a "$LOG_FILE"
log "${GREEN}✓ Gunicorn stopped${NC}"

sudo systemctl stop django-q 2>&1 | tee -a "$LOG_FILE"
log "${GREEN}✓ Django-Q stopped${NC}"

# =============================================================================
# Step 2: Read configuration from .env
# =============================================================================
log ""
log "${YELLOW}Step 2: Reading .env configuration...${NC}"

cd "$PROJECT_DIR"
set -a
source .env
set +a

SERVER_PORT=${SERVER_PORT:-8000}
SERVER_NAME=$(echo $ALLOWED_HOSTS | cut -d',' -f1)

log "${GREEN}✓ Server port: $SERVER_PORT${NC}"
log "${GREEN}✓ Server name: $SERVER_NAME${NC}"

# =============================================================================
# Step 3: Update Gunicorn service
# =============================================================================
log ""
log "${YELLOW}Step 3: Updating Gunicorn service...${NC}"

GUNICORN_SERVICE="/etc/systemd/system/gunicorn.service"

sudo tee "$GUNICORN_SERVICE" > /dev/null << EOF
[Unit]
Description=gunicorn daemon for zkteco
After=network.target

[Service]
User=almita
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/$VENV_NAME/bin"
ExecStart=$PROJECT_DIR/$VENV_NAME/bin/gunicorn zkteco_project.wsgi:application --bind 127.0.0.1:$SERVER_PORT
Restart=always

[Install]
WantedBy=multi-user.target
EOF

log "${GREEN}✓ Gunicorn service updated${NC}"

# =============================================================================
# Step 4: Update Django-Q service
# =============================================================================
log ""
log "${YELLOW}Step 4: Updating Django-Q service...${NC}"

DJANGOQ_SERVICE="/etc/systemd/system/django-q.service"

sudo tee "$DJANGOQ_SERVICE" > /dev/null << EOF
[Unit]
Description=Django-Q2 Worker Cluster
After=network.target postgresql.service

[Service]
User=almita
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/$VENV_NAME/bin"
ExecStart=$PROJECT_DIR/$VENV_NAME/bin/python manage.py qcluster
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

log "${GREEN}✓ Django-Q service updated${NC}"

# =============================================================================
# Step 5: Update Nginx configuration
# =============================================================================
log ""
log "${YELLOW}Step 5: Updating Nginx configuration...${NC}"

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

log "${GREEN}✓ Nginx configuration updated${NC}"

# =============================================================================
# Step 6: Test Nginx configuration
# =============================================================================
log ""
log "${YELLOW}Step 6: Testing Nginx configuration...${NC}"

sudo nginx -t 2>&1 | tee -a "$LOG_FILE"

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Nginx configuration test passed${NC}"
else
    log "${RED}✗ Nginx configuration test failed${NC}"
    exit 1
fi

# =============================================================================
# Step 7: Set SELinux contexts
# =============================================================================
log ""
log "${YELLOW}Step 7: Setting SELinux contexts...${NC}"

if command -v getenforce &> /dev/null; then
    SELINUX_STATUS=$(getenforce)
    if [ "$SELINUX_STATUS" != "Disabled" ]; then
        sudo chcon -R -t httpd_sys_content_t "$PROJECT_DIR/staticfiles" 2>&1 | tee -a "$LOG_FILE"
        sudo chcon -R -t httpd_sys_content_t "$PROJECT_DIR/media" 2>&1 | tee -a "$LOG_FILE"
        sudo setsebool -P httpd_can_network_connect 1 2>&1 | tee -a "$LOG_FILE"
        log "${GREEN}✓ SELinux contexts set${NC}"
    else
        log "${YELLOW}~ SELinux is disabled${NC}"
    fi
else
    log "${YELLOW}~ SELinux not available${NC}"
fi

# =============================================================================
# Step 8: Reload systemd and restart services
# =============================================================================
log ""
log "${YELLOW}Step 8: Restarting services...${NC}"

sudo systemctl daemon-reload 2>&1 | tee -a "$LOG_FILE"

# Start gunicorn
log "Starting gunicorn..." | tee -a "$LOG_FILE"
sudo systemctl start gunicorn 2>&1 | tee -a "$LOG_FILE"
sleep 2

if sudo systemctl is-active --quiet gunicorn; then
    log "${GREEN}✓ Gunicorn started${NC}"
else
    log "${RED}✗ Gunicorn failed to start${NC}"
    sudo systemctl status gunicorn --no-pager 2>&1 | tee -a "$LOG_FILE"
    sudo journalctl -u gunicorn -n 50 --no-pager 2>&1 | tee -a "$LOG_FILE"
    exit 1
fi

# Start django-q
log "Starting django-q..." | tee -a "$LOG_FILE"
sudo systemctl start django-q 2>&1 | tee -a "$LOG_FILE"
sleep 2

if sudo systemctl is-active --quiet django-q; then
    log "${GREEN}✓ Django-Q started${NC}"
else
    log "${RED}✗ Django-Q failed to start${NC}"
    sudo systemctl status django-q --no-pager 2>&1 | tee -a "$LOG_FILE"
    sudo journalctl -u django-q -n 50 --no-pager 2>&1 | tee -a "$LOG_FILE"
    exit 1
fi

# Start nginx
log "Starting nginx..." | tee -a "$LOG_FILE"
sudo systemctl start nginx 2>&1 | tee -a "$LOG_FILE"

if sudo systemctl is-active --quiet nginx; then
    log "${GREEN}✓ Nginx started${NC}"
else
    log "${RED}✗ Nginx failed to start${NC}"
    sudo systemctl status nginx --no-pager 2>&1 | tee -a "$LOG_FILE"
    exit 1
fi

# =============================================================================
# Step 9: Verify all services
# =============================================================================
log ""
log "${YELLOW}Step 9: Verifying services...${NC}"

SERVICES=("nginx" "gunicorn" "django-q" "postgresql")

for service in "${SERVICES[@]}"; do
    if sudo systemctl is-active --quiet "$service"; then
        log "${GREEN}✓ $service is running${NC}"
    else
        log "${RED}✗ $service is NOT running${NC}"
    fi
done

# =============================================================================
# Step 10: Test static file access
# =============================================================================
log ""
log "${YELLOW}Step 10: Testing application...${NC}"

# Test static file
log "Testing: http://localhost/static/js/task_progress.js" | tee -a "$LOG_FILE"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/static/js/task_progress.js)

if [ "$HTTP_CODE" = "200" ]; then
    log "${GREEN}✓ Static files: HTTP $HTTP_CODE${NC}"
else
    log "${RED}✗ Static files: HTTP $HTTP_CODE${NC}"
    sudo tail -20 /var/log/nginx/zkteco_error.log 2>&1 | tee -a "$LOG_FILE"
fi

# Test main page
log "Testing: http://localhost/" | tee -a "$LOG_FILE"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/)

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
    log "${GREEN}✓ Main page: HTTP $HTTP_CODE${NC}"
else
    log "${RED}✗ Main page: HTTP $HTTP_CODE${NC}"
fi

# Test admin
log "Testing: http://localhost/en/admin/" | tee -a "$LOG_FILE"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/en/admin/)

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
    log "${GREEN}✓ Admin page: HTTP $HTTP_CODE${NC}"
else
    log "${YELLOW}~ Admin page: HTTP $HTTP_CODE${NC}"
fi

# =============================================================================
# Completion
# =============================================================================
log ""
log "${BLUE}========================================${NC}"
log "${GREEN}✓ Configuration Update Complete!${NC}"
log "${BLUE}========================================${NC}"
log ""
log "Completed at: $(date '+%Y-%m-%d %H:%M:%S')"
log ""
log "${YELLOW}Updated files:${NC}"
log "  Gunicorn service:  /etc/systemd/system/gunicorn.service"
log "  Django-Q service:  /etc/systemd/system/django-q.service"
log "  Nginx config:      /etc/nginx/conf.d/zkteco.conf"
log ""
log "${YELLOW}Project location:${NC}"
log "  $PROJECT_DIR"
log ""
log "${YELLOW}Access your application:${NC}"
log "  ${BLUE}http://localhost/${NC}"
log "  ${BLUE}http://$(hostname -I | awk '{print $1}')/${NC}"
log ""
log "${YELLOW}Log file:${NC}"
log "  ${BLUE}$LOG_FILE${NC}"
log ""
