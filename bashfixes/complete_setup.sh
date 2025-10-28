#!/bin/bash
# Complete setup for ZKTeco Management System at /opt/CCP/zktecoMGMT
# This script does everything in one go - no multi-step execution needed

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Variables
PROJECT_DIR="/opt/CCP/zktecoMGMT"
OLD_PATH="/home/almita/CCP/zktecoMGMT"
NEW_PATH="/opt/CCP/zktecoMGMT"
VENV_NAME="zkteco_env"

# =============================================================================
# Logging Setup
# =============================================================================
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/complete_setup_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

log "${BLUE}========================================${NC}"
log "${BLUE}   ZKTeco Complete Setup${NC}"
log "${BLUE}========================================${NC}"
log ""
log "${GREEN}Log file: $LOG_FILE${NC}"
log "Started at: $(date '+%Y-%m-%d %H:%M:%S')"
log ""

# =============================================================================
# PHASE 1: Fix Virtual Environment Paths
# =============================================================================
log "${BLUE}=== PHASE 1: Fix Virtual Environment Paths ===${NC}"
log ""

log "${YELLOW}Step 1.1: Fixing Python shebangs in $VENV_NAME/bin...${NC}"

FIXED_COUNT=0
BIN_DIR="$PROJECT_DIR/$VENV_NAME/bin"

cd "$BIN_DIR"

for file in *; do
    if [ -f "$file" ] && [ -x "$file" ]; then
        if head -n 1 "$file" 2>/dev/null | grep -q "$OLD_PATH"; then
            log "  Fixing: $file"
            sed -i "1s|$OLD_PATH|$NEW_PATH|" "$file"
            FIXED_COUNT=$((FIXED_COUNT + 1))
        fi
    fi
done

log "${GREEN}✓ Fixed $FIXED_COUNT Python scripts${NC}"

log ""
log "${YELLOW}Step 1.2: Fixing activate scripts...${NC}"

for script in activate activate.csh activate.fish Activate.ps1; do
    if [ -f "$BIN_DIR/$script" ]; then
        sed -i "s|$OLD_PATH|$NEW_PATH|g" "$BIN_DIR/$script"
        log "${GREEN}✓ Fixed $script${NC}"
    fi
done

log ""
log "${YELLOW}Step 1.3: Fixing pyvenv.cfg...${NC}"

PYVENV_CFG="$PROJECT_DIR/$VENV_NAME/pyvenv.cfg"

if [ -f "$PYVENV_CFG" ]; then
    sed -i "s|$OLD_PATH|$NEW_PATH|g" "$PYVENV_CFG"
    log "${GREEN}✓ Fixed pyvenv.cfg${NC}"
fi

log ""
log "${YELLOW}Step 1.4: Setting ownership to almita:almita...${NC}"

sudo chown -R almita:almita "$PROJECT_DIR/$VENV_NAME"
log "${GREEN}✓ Ownership updated${NC}"

log ""
log "${YELLOW}Step 1.5: Verifying gunicorn...${NC}"

if "$BIN_DIR/gunicorn" --version > /dev/null 2>&1; then
    GUNICORN_VERSION=$("$BIN_DIR/gunicorn" --version 2>&1)
    log "${GREEN}✓ gunicorn works: $GUNICORN_VERSION${NC}"
else
    log "${RED}✗ gunicorn test failed${NC}"
    exit 1
fi

# =============================================================================
# PHASE 2: Update System Configurations
# =============================================================================
log ""
log "${BLUE}=== PHASE 2: Update System Configurations ===${NC}"
log ""

log "${YELLOW}Step 2.1: Stopping services...${NC}"

for service in nginx gunicorn django-q; do
    sudo systemctl stop $service 2>&1 | tee -a "$LOG_FILE"
    log "${GREEN}✓ $service stopped${NC}"
done

log ""
log "${YELLOW}Step 2.2: Reading .env configuration...${NC}"

cd "$PROJECT_DIR"
set -a
source .env
set +a

SERVER_PORT=${SERVER_PORT:-8000}
SERVER_NAME=$(echo $ALLOWED_HOSTS | cut -d',' -f1)

log "${GREEN}✓ Server port: $SERVER_PORT${NC}"
log "${GREEN}✓ Server name: $SERVER_NAME${NC}"

log ""
log "${YELLOW}Step 2.3: Updating Gunicorn service...${NC}"

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

log ""
log "${YELLOW}Step 2.4: Updating Django-Q service...${NC}"

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

log ""
log "${YELLOW}Step 2.5: Updating Nginx configuration...${NC}"

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

log ""
log "${YELLOW}Step 2.6: Testing Nginx configuration...${NC}"

sudo nginx -t 2>&1 | tee -a "$LOG_FILE"

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Nginx configuration test passed${NC}"
else
    log "${RED}✗ Nginx configuration test failed${NC}"
    exit 1
fi

# =============================================================================
# PHASE 3: Set SELinux Contexts
# =============================================================================
log ""
log "${BLUE}=== PHASE 3: Set SELinux Contexts ===${NC}"
log ""

if command -v getenforce &> /dev/null; then
    SELINUX_STATUS=$(getenforce)
    if [ "$SELINUX_STATUS" != "Disabled" ]; then
        log "${YELLOW}Configuring SELinux...${NC}"
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
# PHASE 4: Start All Services
# =============================================================================
log ""
log "${BLUE}=== PHASE 4: Start All Services ===${NC}"
log ""

sudo systemctl daemon-reload 2>&1 | tee -a "$LOG_FILE"

# Start gunicorn
log "${YELLOW}Starting gunicorn...${NC}"
sudo systemctl start gunicorn 2>&1 | tee -a "$LOG_FILE"
sleep 2

if sudo systemctl is-active --quiet gunicorn; then
    log "${GREEN}✓ Gunicorn started${NC}"
else
    log "${RED}✗ Gunicorn failed to start${NC}"
    sudo systemctl status gunicorn --no-pager 2>&1 | tee -a "$LOG_FILE"
    exit 1
fi

# Start django-q
log "${YELLOW}Starting django-q...${NC}"
sudo systemctl start django-q 2>&1 | tee -a "$LOG_FILE"
sleep 2

if sudo systemctl is-active --quiet django-q; then
    log "${GREEN}✓ Django-Q started${NC}"
else
    log "${RED}✗ Django-Q failed to start${NC}"
    sudo systemctl status django-q --no-pager 2>&1 | tee -a "$LOG_FILE"
    exit 1
fi

# Start nginx
log "${YELLOW}Starting nginx...${NC}"
sudo systemctl start nginx 2>&1 | tee -a "$LOG_FILE"

if sudo systemctl is-active --quiet nginx; then
    log "${GREEN}✓ Nginx started${NC}"
else
    log "${RED}✗ Nginx failed to start${NC}"
    sudo systemctl status nginx --no-pager 2>&1 | tee -a "$LOG_FILE"
    exit 1
fi

# =============================================================================
# PHASE 5: Verify Everything
# =============================================================================
log ""
log "${BLUE}=== PHASE 5: Verify Everything ===${NC}"
log ""

log "${YELLOW}Checking services...${NC}"

SERVICES=("nginx" "gunicorn" "django-q" "postgresql")

for service in "${SERVICES[@]}"; do
    if sudo systemctl is-active --quiet "$service"; then
        log "${GREEN}✓ $service is running${NC}"
    else
        log "${RED}✗ $service is NOT running${NC}"
    fi
done

log ""
log "${YELLOW}Testing application endpoints...${NC}"

# Test static file
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/static/js/task_progress.js)
if [ "$HTTP_CODE" = "200" ]; then
    log "${GREEN}✓ Static files: HTTP $HTTP_CODE${NC}"
else
    log "${RED}✗ Static files: HTTP $HTTP_CODE${NC}"
fi

# Test main page
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/)
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
    log "${GREEN}✓ Main page: HTTP $HTTP_CODE${NC}"
else
    log "${RED}✗ Main page: HTTP $HTTP_CODE${NC}"
fi

# Test admin
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
log "${GREEN}✓ Complete Setup Finished!${NC}"
log "${BLUE}========================================${NC}"
log ""
log "Completed at: $(date '+%Y-%m-%d %H:%M:%S')"
log ""
log "${YELLOW}Summary:[0m"
log "  Project: $PROJECT_DIR"
log "  Virtual env: $VENV_NAME"
log "  Server port: $SERVER_PORT"
log "  Files fixed: $FIXED_COUNT"
log ""
log "${YELLOW}Services:[0m"
for service in "${SERVICES[@]}"; do
    if sudo systemctl is-active --quiet "$service"; then
        log "  ${GREEN}✓${NC} $service"
    else
        log "  ${RED}✗${NC} $service"
    fi
done
log ""
log "${YELLOW}Access your application:[0m"
log "  ${BLUE}http://localhost/${NC}"
log "  ${BLUE}http://$(hostname -I | awk '{print $1}')/${NC}"
log ""
log "${YELLOW}Log file:[0m"
log "  ${BLUE}$LOG_FILE${NC}"
log ""
