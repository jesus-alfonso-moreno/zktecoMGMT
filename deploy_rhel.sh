#!/bin/bash
# deploy_rhel.sh - RHEL/AlmaLinux/Fedora specific deployment operations
# This script is called by deploy.sh and depends on variables from it

# Exit immediately if a command exits with a non-zero status
set -e

# Log function
log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

log "${YELLOW}=== Starting RHEL/AlmaLinux/Fedora Specific Configuration ===${NC}"

# =============================================================================
# Step 1: Install PostgreSQL Server and Development Libraries
# =============================================================================
log "${YELLOW}Installing PostgreSQL server and development libraries...${NC}"

sudo dnf install -y \
    postgresql-server \
    postgresql-contrib \
    postgresql-server-devel \
    python3-devel \
    gcc

if [ $? -eq 0 ]; then
    log "${GREEN}✓ PostgreSQL packages installed successfully${NC}"
else
    log "${RED}✗ Failed to install PostgreSQL packages${NC}"
    exit 1
fi

# =============================================================================
# Step 2: Initialize PostgreSQL Database (RHEL specific)
# =============================================================================
log "${YELLOW}Initializing PostgreSQL database cluster...${NC}"

# Check if already initialized
if sudo test -f /var/lib/pgsql/data/PG_VERSION; then
    log "${GREEN}✓ PostgreSQL database already initialized${NC}"
else
    log "${YELLOW}Initializing PostgreSQL...${NC}"

    # Remove incomplete directory if exists
    if sudo test -d /var/lib/pgsql/data; then
        log "${YELLOW}Removing incomplete data directory...${NC}"
        sudo rm -rf /var/lib/pgsql/data
    fi

    # Initialize database
    sudo postgresql-setup --initdb

    if [ $? -eq 0 ]; then
        log "${GREEN}✓ PostgreSQL initialized successfully${NC}"
    else
        log "${RED}✗ Failed to initialize PostgreSQL${NC}"
        exit 1
    fi
fi

# Start and enable PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

if [ $? -eq 0 ]; then
    log "${GREEN}✓ PostgreSQL service started and enabled${NC}"
else
    log "${RED}✗ Failed to start PostgreSQL service${NC}"
    exit 1
fi

# =============================================================================
# Step 3: Configure PostgreSQL Authentication (pg_hba.conf)
# =============================================================================
log "${YELLOW}Configuring PostgreSQL authentication...${NC}"

PG_HBA_CONF="/var/lib/pgsql/data/pg_hba.conf"

if [ -f "$PG_HBA_CONF" ]; then
    log "${GREEN}✓ Found pg_hba.conf at: $PG_HBA_CONF${NC}"

    # Backup original
    sudo cp "$PG_HBA_CONF" "${PG_HBA_CONF}.backup.$(date +%Y%m%d_%H%M%S)"

    # Configure authentication properly
    log "${YELLOW}Configuring PostgreSQL authentication...${NC}"

    # Create a new pg_hba.conf with proper authentication rules
    sudo tee "$PG_HBA_CONF" > /dev/null << 'HBAEOF'
# PostgreSQL Client Authentication Configuration File
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# "local" is for Unix domain socket connections only
local   all             postgres                                peer
local   all             all                                     md5

# IPv4 local connections:
host    all             all             127.0.0.1/32            md5

# IPv6 local connections:
host    all             all             ::1/128                 md5

# Allow replication connections from localhost, by a user with the
# replication privilege.
local   replication     all                                     peer
host    replication     all             127.0.0.1/32            ident
host    replication     all             ::1/128                 ident
HBAEOF

    # Reload PostgreSQL to apply changes
    sudo systemctl reload postgresql

    if [ $? -eq 0 ]; then
        log "${GREEN}✓ PostgreSQL authentication configured (md5)${NC}"
    else
        log "${RED}✗ Failed to reload PostgreSQL${NC}"
        exit 1
    fi
else
    log "${RED}✗ Could not find pg_hba.conf at $PG_HBA_CONF${NC}"
    exit 1
fi

# =============================================================================
# Step 4: Create PostgreSQL Database and User
# =============================================================================
log "${YELLOW}Setting up PostgreSQL database and user...${NC}"

# Check if database exists
DB_EXISTS=$(su - postgres -c "psql -lqt" | cut -d \| -f 1 | grep -w "$DB_NAME" | wc -l)

if [ "$DB_EXISTS" -gt 0 ]; then
    log "${GREEN}✓ Database '$DB_NAME' already exists${NC}"

    # Verify database is accessible
    if su - postgres -c "psql -d \"$DB_NAME\" -c \"SELECT 1;\"" > /dev/null 2>&1; then
        log "${GREEN}✓ Database '$DB_NAME' is accessible${NC}"
    else
        log "${RED}✗ Database exists but is not accessible${NC}"
        exit 1
    fi
else
    log "${YELLOW}Creating database '$DB_NAME'...${NC}"
    su - postgres -c "createdb \"$DB_NAME\""

    if [ $? -eq 0 ]; then
        log "${GREEN}✓ Database '$DB_NAME' created successfully${NC}"
    else
        log "${RED}✗ Failed to create database${NC}"
        exit 1
    fi
fi

# Check if user exists
USER_EXISTS=$(su - postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'\"" | grep -c 1)

if [ "$USER_EXISTS" -gt 0 ]; then
    log "${GREEN}✓ User '$DB_USER' exists - updating credentials${NC}"

    # Update password and ensure privileges
    su - postgres -c "psql" <<EOF
ALTER USER "$DB_USER" WITH PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE "$DB_NAME" TO "$DB_USER";
EOF

    if [ $? -eq 0 ]; then
        log "${GREEN}✓ User credentials updated and privileges granted${NC}"
    else
        log "${RED}✗ Failed to update user${NC}"
        exit 1
    fi
else
    log "${YELLOW}Creating user '$DB_USER'...${NC}"

    su - postgres -c "psql" <<EOF
CREATE USER "$DB_USER" WITH PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE "$DB_NAME" TO "$DB_USER";
EOF

    if [ $? -eq 0 ]; then
        log "${GREEN}✓ User '$DB_USER' created with privileges${NC}"
    else
        log "${RED}✗ Failed to create user${NC}"
        exit 1
    fi
fi

# =============================================================================
# Step 5: Configure Gunicorn Systemd Service
# =============================================================================
log "${YELLOW}Configuring gunicorn systemd service...${NC}"

# Use the venv paths from main deploy.sh
PYTHON_BIN="$VENV_PATH/bin/python3"
GUNICORN_BIN="$VENV_PATH/bin/gunicorn"

# Create systemd service file
SYSTEMD_SERVICE="/etc/systemd/system/gunicorn.service"

# Determine the actual user (not root)
ACTUAL_USER="${SUDO_USER:-$(whoami)}"
if [ "$ACTUAL_USER" == "root" ]; then
    log "${YELLOW}Warning: Running as root without SUDO_USER. Using 'root' as service user.${NC}"
fi

sudo tee "$SYSTEMD_SERVICE" > /dev/null << EOF
[Unit]
Description=gunicorn daemon for zkteco
After=network.target

[Service]
User=$ACTUAL_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_PATH/bin"
ExecStart=$GUNICORN_BIN zkteco_project.wsgi:application --bind 127.0.0.1:$SERVER_PORT --workers 3 --timeout 300
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Gunicorn service file created at $SYSTEMD_SERVICE${NC}"
else
    log "${RED}✗ Failed to create gunicorn service file${NC}"
    exit 1
fi

# Reload systemd and enable gunicorn
log "${YELLOW}Enabling and starting gunicorn service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable gunicorn.service
sudo systemctl start gunicorn.service

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Gunicorn service enabled and started${NC}"
else
    log "${RED}✗ Failed to start gunicorn service${NC}"
    log "${YELLOW}Checking service status...${NC}"
    sudo systemctl status gunicorn.service | tee -a "$LOG_FILE"
    exit 1
fi

# Check service status
sleep 2
if sudo systemctl is-active --quiet gunicorn.service; then
    log "${GREEN}✓ Gunicorn service is running${NC}"
else
    log "${RED}✗ Gunicorn service failed to start${NC}"
    log "${YELLOW}Service status:${NC}"
    sudo systemctl status gunicorn.service | tee -a "$LOG_FILE"
    exit 1
fi

# =============================================================================
# Step 6: Configure Django-Q2 Systemd Service
# =============================================================================
log "${YELLOW}Configuring Django-Q2 worker service...${NC}"

DJANGOQ_SERVICE="/etc/systemd/system/django-q.service"

sudo tee "$DJANGOQ_SERVICE" > /dev/null << EOF
[Unit]
Description=Django-Q2 Worker Cluster
After=network.target postgresql.service

[Service]
User=$ACTUAL_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_PATH/bin"
ExecStart=$PYTHON_BIN manage.py qcluster
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Django-Q2 service file created at $DJANGOQ_SERVICE${NC}"
else
    log "${RED}✗ Failed to create Django-Q2 service file${NC}"
    exit 1
fi

# Reload systemd and enable django-q
log "${YELLOW}Enabling and starting django-q service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable django-q.service
sudo systemctl start django-q.service

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Django-Q2 service enabled and started${NC}"
else
    log "${RED}✗ Failed to start Django-Q2 service${NC}"
    log "${YELLOW}Checking service status...${NC}"
    sudo systemctl status django-q.service | tee -a "$LOG_FILE"
    exit 1
fi

# Check service status
sleep 2
if sudo systemctl is-active --quiet django-q.service; then
    log "${GREEN}✓ Django-Q2 service is running${NC}"
else
    log "${RED}✗ Django-Q2 service failed to start${NC}"
    log "${YELLOW}Service status:${NC}"
    sudo systemctl status django-q.service | tee -a "$LOG_FILE"
    exit 1
fi

# =============================================================================
# Step 7: Install and Configure Nginx
# =============================================================================
log "${YELLOW}Installing and configuring Nginx...${NC}"

# Install Nginx
sudo dnf install -y nginx

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Nginx installed successfully${NC}"
else
    log "${RED}✗ Failed to install Nginx${NC}"
    exit 1
fi

# Create Nginx configuration
NGINX_CONF="/etc/nginx/conf.d/zkteco.conf"

log "${YELLOW}Creating Nginx configuration at $NGINX_CONF...${NC}"

sudo tee "$NGINX_CONF" > /dev/null << EOF
server {
    listen 80;
    server_name _;

    client_max_body_size 20M;

    # Static files
    location /static/ {
        alias $PROJECT_DIR/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias $PROJECT_DIR/media/;
        expires 7d;
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:$SERVER_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 300s;
        proxy_read_timeout 300s;
    }
}
EOF

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Nginx configuration created${NC}"
else
    log "${RED}✗ Failed to create Nginx configuration${NC}"
    exit 1
fi

# Test Nginx configuration
log "${YELLOW}Testing Nginx configuration...${NC}"
sudo nginx -t > /dev/null 2>&1

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Nginx configuration is valid${NC}"
else
    log "${RED}✗ Nginx configuration test failed${NC}"
    sudo nginx -t | tee -a "$LOG_FILE"
    exit 1
fi

# =============================================================================
# Step 8: Configure SELinux
# =============================================================================
log "${YELLOW}Configuring SELinux contexts...${NC}"

# Check if SELinux is enabled
if command -v getenforce &> /dev/null && [ "$(getenforce)" != "Disabled" ]; then
    log "${GREEN}✓ SELinux is enabled - configuring contexts${NC}"

    # Set context for static files
    if [ -d "$PROJECT_DIR/staticfiles" ]; then
        sudo chcon -R -t httpd_sys_content_t "$PROJECT_DIR/staticfiles"
        log "${GREEN}✓ Set SELinux context for staticfiles${NC}"
    fi

    # Set context for media files
    if [ -d "$PROJECT_DIR/media" ]; then
        sudo chcon -R -t httpd_sys_content_t "$PROJECT_DIR/media"
        log "${GREEN}✓ Set SELinux context for media${NC}"
    fi

    # Allow Nginx to connect to network (for proxying to Gunicorn)
    sudo setsebool -P httpd_can_network_connect 1
    log "${GREEN}✓ Enabled httpd_can_network_connect${NC}"
else
    log "${YELLOW}~ SELinux is disabled - skipping SELinux configuration${NC}"
fi

# =============================================================================
# Step 9: Configure Firewalld
# =============================================================================
log "${YELLOW}Configuring firewall (firewalld)...${NC}"

# Check if firewalld is installed and running
if command -v firewall-cmd &> /dev/null; then
    # Check if firewalld is running
    if sudo systemctl is-active --quiet firewalld; then
        log "${GREEN}✓ firewalld is active${NC}"

        # Allow HTTP
        if sudo firewall-cmd --list-services | grep -q http; then
            log "${GREEN}✓ HTTP already allowed in firewall${NC}"
        else
            sudo firewall-cmd --permanent --add-service=http
            log "${GREEN}✓ Added HTTP to firewall${NC}"
        fi

        # Allow HTTPS
        if sudo firewall-cmd --list-services | grep -q https; then
            log "${GREEN}✓ HTTPS already allowed in firewall${NC}"
        else
            sudo firewall-cmd --permanent --add-service=https
            log "${GREEN}✓ Added HTTPS to firewall${NC}"
        fi

        # Reload firewall
        sudo firewall-cmd --reload
        log "${GREEN}✓ Firewall reloaded${NC}"

        # Show current zones
        log "${YELLOW}Current firewall configuration:${NC}"
        sudo firewall-cmd --list-all | tee -a "$LOG_FILE"
    else
        log "${YELLOW}~ firewalld is installed but not running${NC}"
        read -p "$(echo -e ${YELLOW}Do you want to enable firewalld?${NC}) (y/n) [y]: " ENABLE_FIREWALLD
        ENABLE_FIREWALLD=${ENABLE_FIREWALLD:-y}

        if [[ "$ENABLE_FIREWALLD" =~ ^[Yy]$ ]]; then
            sudo systemctl start firewalld
            sudo systemctl enable firewalld

            # Add HTTP/HTTPS
            sudo firewall-cmd --permanent --add-service=http
            sudo firewall-cmd --permanent --add-service=https
            sudo firewall-cmd --reload

            log "${GREEN}✓ firewalld enabled and configured${NC}"
        fi
    fi
else
    log "${YELLOW}~ firewalld not installed - skipping firewall configuration${NC}"
    log "${YELLOW}  You may need to manually configure your firewall to allow HTTP (port 80)${NC}"
fi

# =============================================================================
# Step 10: Start and Enable Services
# =============================================================================
log ""
log "${YELLOW}Starting and enabling all services...${NC}"

# Enable and start Nginx
sudo systemctl enable nginx
sudo systemctl restart nginx

if sudo systemctl is-active --quiet nginx; then
    log "${GREEN}✓ Nginx service is running${NC}"
else
    log "${RED}✗ Nginx service failed to start${NC}"
    sudo systemctl status nginx | tee -a "$LOG_FILE"
    exit 1
fi

# Restart gunicorn to ensure it's running
sudo systemctl restart gunicorn

if sudo systemctl is-active --quiet gunicorn; then
    log "${GREEN}✓ Gunicorn service is running${NC}"
else
    log "${RED}✗ Gunicorn service failed to start${NC}"
    sudo systemctl status gunicorn | tee -a "$LOG_FILE"
    exit 1
fi

# Restart django-q
sudo systemctl restart django-q

if sudo systemctl is-active --quiet django-q; then
    log "${GREEN}✓ Django-Q2 service is running${NC}"
else
    log "${RED}✗ Django-Q2 service failed to start${NC}"
    sudo systemctl status django-q | tee -a "$LOG_FILE"
    exit 1
fi

log ""
log "${GREEN}=== RHEL/AlmaLinux/Fedora Configuration Complete ===${NC}"
