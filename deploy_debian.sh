#!/bin/bash
# deploy_debian.sh - Debian/Ubuntu specific deployment operations
# This script is called by deploy.sh and depends on variables from it

# Exit immediately if a command exits with a non-zero status
set -e

# Log function
log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

log "${YELLOW}=== Starting Debian/Ubuntu Specific Configuration ===${NC}"

# =============================================================================
# Step 1: Check if PostgreSQL is Already Running
# =============================================================================
log "${YELLOW}Checking PostgreSQL status...${NC}"

POSTGRES_RUNNING=false
POSTGRES_INSTALLED=false

# Check if PostgreSQL is installed
if command -v psql &> /dev/null; then
    POSTGRES_INSTALLED=true
    log "${GREEN}✓ PostgreSQL is already installed${NC}"

    # Check if PostgreSQL service is running
    if systemctl is-active --quiet postgresql; then
        POSTGRES_RUNNING=true
        log "${GREEN}✓ PostgreSQL service is already running${NC}"
    else
        log "${YELLOW}~ PostgreSQL is installed but not running${NC}"
    fi
else
    log "${YELLOW}~ PostgreSQL is not installed${NC}"
fi

# =============================================================================
# Step 2: Install PostgreSQL Server and Development Libraries (if needed)
# =============================================================================
if [ "$POSTGRES_INSTALLED" = false ]; then
    log "${YELLOW}Installing PostgreSQL server and development libraries...${NC}"

    sudo apt-get update
    sudo apt-get install -y \
        postgresql \
        postgresql-contrib \
        postgresql-server-dev-all \
        python3-dev \
        build-essential \
        libpq-dev

    if [ $? -eq 0 ]; then
        log "${GREEN}✓ PostgreSQL packages installed successfully${NC}"
        POSTGRES_INSTALLED=true
    else
        log "${RED}✗ Failed to install PostgreSQL packages${NC}"
        exit 1
    fi
else
    log "${GREEN}✓ Skipping PostgreSQL installation - already installed${NC}"

    # Still ensure development libraries are present
    log "${YELLOW}Ensuring development libraries are installed...${NC}"
    sudo apt-get install -y \
        postgresql-server-dev-all \
        python3-dev \
        build-essential \
        libpq-dev > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        log "${GREEN}✓ Development libraries verified${NC}"
    fi
fi

# =============================================================================
# Step 3: Start PostgreSQL (if not already running)
# =============================================================================
if [ "$POSTGRES_RUNNING" = true ]; then
    log "${GREEN}✓ Skipping PostgreSQL service start - already running${NC}"
else
    log "${YELLOW}Starting PostgreSQL service...${NC}"
    sudo systemctl start postgresql
    sudo systemctl enable postgresql

    if [ $? -eq 0 ]; then
        log "${GREEN}✓ PostgreSQL service started and enabled${NC}"
        POSTGRES_RUNNING=true
    else
        log "${RED}✗ Failed to start PostgreSQL service${NC}"
        exit 1
    fi
fi

# =============================================================================
# Step 4: Configure PostgreSQL Authentication (pg_hba.conf)
# =============================================================================
log "${YELLOW}Configuring PostgreSQL authentication...${NC}"

# Find the correct pg_hba.conf file
PG_VERSION=$(su - postgres -c "psql -tAc 'SHOW server_version;'" | cut -d'.' -f1)
PG_HBA_CONF="/etc/postgresql/${PG_VERSION}/main/pg_hba.conf"

if [ ! -f "$PG_HBA_CONF" ]; then
    # Fallback: find it
    PG_HBA_CONF=$(sudo find /etc/postgresql -name pg_hba.conf | head -n 1)
fi

if [ -f "$PG_HBA_CONF" ]; then
    log "${GREEN}✓ Found pg_hba.conf at: $PG_HBA_CONF${NC}"

    # Check if already configured with md5 authentication
    if grep -q "^local.*all.*all.*md5" "$PG_HBA_CONF"; then
        log "${GREEN}✓ pg_hba.conf already configured with md5 authentication${NC}"
    else
        log "${YELLOW}Updating pg_hba.conf configuration...${NC}"

        # Backup original
        sudo cp "$PG_HBA_CONF" "${PG_HBA_CONF}.backup.$(date +%Y%m%d_%H%M%S)"
        log "${GREEN}✓ Created backup: ${PG_HBA_CONF}.backup.$(date +%Y%m%d_%H%M%S)${NC}"

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
host    replication     all             127.0.0.1/32            scram-sha-256
host    replication     all             ::1/128                 scram-sha-256
HBAEOF

        # Reload PostgreSQL to apply changes
        sudo systemctl reload postgresql

        if [ $? -eq 0 ]; then
            log "${GREEN}✓ PostgreSQL authentication configured (md5)${NC}"
        else
            log "${RED}✗ Failed to reload PostgreSQL${NC}"
            exit 1
        fi
    fi
else
    log "${RED}✗ Could not find pg_hba.conf${NC}"
    exit 1
fi

# =============================================================================
# Step 5: Create PostgreSQL Database and User
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
USER_EXISTS=$(su - postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'\"" 2>/dev/null | grep -c 1 || echo "0")

if [ "$USER_EXISTS" -gt 0 ]; then
    log "${GREEN}✓ User '$DB_USER' exists - updating credentials${NC}"

    # Update password and ensure all privileges including schema permissions
    su - postgres -c "psql -d \"$DB_NAME\"" <<EOF
ALTER USER "$DB_USER" WITH PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE "$DB_NAME" TO "$DB_USER";
GRANT ALL ON SCHEMA public TO "$DB_USER";
GRANT CREATE ON SCHEMA public TO "$DB_USER";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "$DB_USER";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO "$DB_USER";
ALTER DATABASE "$DB_NAME" OWNER TO "$DB_USER";
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
        log "${GREEN}✓ User '$DB_USER' created${NC}"
    else
        log "${RED}✗ Failed to create user${NC}"
        exit 1
    fi

    # Grant schema-level permissions
    log "${YELLOW}Granting schema permissions to '$DB_USER'...${NC}"
    su - postgres -c "psql -d \"$DB_NAME\"" <<EOF
GRANT ALL ON SCHEMA public TO "$DB_USER";
GRANT CREATE ON SCHEMA public TO "$DB_USER";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "$DB_USER";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO "$DB_USER";
ALTER DATABASE "$DB_NAME" OWNER TO "$DB_USER";
EOF

    if [ $? -eq 0 ]; then
        log "${GREEN}✓ Schema permissions granted to '$DB_USER'${NC}"
    else
        log "${RED}✗ Failed to grant schema permissions${NC}"
        exit 1
    fi
fi

# =============================================================================
# Step 6: Configure Gunicorn Systemd Service
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
ExecStart=$GUNICORN_BIN zkteco_project.wsgi:application --bind 127.0.0.1:$GUNICORN_PORT --workers 3 --timeout 300
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

# Reload systemd and enable gunicorn (but don't start yet - wait for migrations)
log "${YELLOW}Enabling gunicorn service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable gunicorn.service

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Gunicorn service enabled (will start after migrations)${NC}"
else
    log "${RED}✗ Failed to enable gunicorn service${NC}"
    exit 1
fi

# =============================================================================
# Step 7: Configure Django-Q2 Systemd Service
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

# Reload systemd and enable django-q (but don't start yet - wait for migrations)
log "${YELLOW}Enabling django-q service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable django-q.service

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Django-Q2 service enabled (will start after migrations)${NC}"
else
    log "${RED}✗ Failed to enable Django-Q2 service${NC}"
    exit 1
fi

# =============================================================================
# Step 8: Install and Configure Nginx
# =============================================================================
log "${YELLOW}Installing and configuring Nginx...${NC}"

# Install Nginx
sudo apt-get install -y nginx

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Nginx installed successfully${NC}"
else
    log "${RED}✗ Failed to install Nginx${NC}"
    exit 1
fi

# Create Nginx configuration
NGINX_CONF="/etc/nginx/sites-available/zkteco.conf"

log "${YELLOW}Creating Nginx configuration at $NGINX_CONF...${NC}"

sudo tee "$NGINX_CONF" > /dev/null << EOF
server {
    listen $NGINX_PORT;
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

    # Proxy to Gunicorn (internal port)
    location / {
        proxy_pass http://127.0.0.1:$GUNICORN_PORT;
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

# Enable the site (Debian/Ubuntu specific)
if [ -f "/etc/nginx/sites-enabled/zkteco.conf" ]; then
    log "${YELLOW}Removing old symlink...${NC}"
    sudo rm /etc/nginx/sites-enabled/zkteco.conf
fi

# Disable default Nginx site to avoid port conflicts
if [ -L /etc/nginx/sites-enabled/default ]; then
    log "${YELLOW}Removing default Nginx site...${NC}"
    sudo rm /etc/nginx/sites-enabled/default
    log "${GREEN}✓ Default Nginx site disabled${NC}"
fi

sudo ln -s /etc/nginx/sites-available/zkteco.conf /etc/nginx/sites-enabled/
log "${GREEN}✓ Nginx site enabled${NC}"

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
# Step 9: Configure SELinux (if installed)
# =============================================================================
log "${YELLOW}Checking for SELinux...${NC}"

# Check if SELinux is installed and enabled
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
    log "${YELLOW}~ SELinux not installed or disabled - skipping SELinux configuration${NC}"
fi

# =============================================================================
# Step 10: Configure Firewall (UFW)
# =============================================================================
log "${YELLOW}Configuring firewall (UFW)...${NC}"

# Check if UFW is installed
if command -v ufw &> /dev/null; then
    # Check if UFW is active
    UFW_STATUS=$(sudo ufw status | grep -i "Status:" | awk '{print $2}')

    if [ "$UFW_STATUS" == "active" ]; then
        log "${GREEN}✓ UFW is active${NC}"

        # Handle standard ports (80/443) vs custom ports
        if [ "$NGINX_PORT" -eq 80 ]; then
            if sudo ufw status | grep -q "80/tcp"; then
                log "${GREEN}✓ Port 80 already allowed in firewall${NC}"
            else
                sudo ufw allow 80/tcp
                log "${GREEN}✓ Opened port 80 in UFW${NC}"
            fi
        elif [ "$NGINX_PORT" -eq 443 ]; then
            if sudo ufw status | grep -q "443/tcp"; then
                log "${GREEN}✓ Port 443 already allowed in firewall${NC}"
            else
                sudo ufw allow 443/tcp
                log "${GREEN}✓ Opened port 443 in UFW${NC}"
            fi
        else
            # Custom port
            if sudo ufw status | grep -q "$NGINX_PORT/tcp"; then
                log "${GREEN}✓ Port $NGINX_PORT already allowed in firewall${NC}"
            else
                sudo ufw allow $NGINX_PORT/tcp
                log "${GREEN}✓ Opened port $NGINX_PORT/tcp in UFW${NC}"
            fi
        fi

        # Show current UFW status
        log "${YELLOW}Current UFW status:${NC}"
        sudo ufw status numbered | tee -a "$LOG_FILE"
    else
        log "${YELLOW}~ UFW is installed but not active${NC}"
        read -p "$(echo -e ${YELLOW}Do you want to enable UFW?${NC}) (y/n) [y]: " ENABLE_UFW
        ENABLE_UFW=${ENABLE_UFW:-y}

        if [[ "$ENABLE_UFW" =~ ^[Yy]$ ]]; then
            # Allow SSH first to prevent lockout
            sudo ufw allow 22/tcp
            log "${GREEN}✓ Allowed SSH (port 22)${NC}"

            # Add appropriate port
            if [ "$NGINX_PORT" -eq 80 ]; then
                sudo ufw allow 80/tcp
            elif [ "$NGINX_PORT" -eq 443 ]; then
                sudo ufw allow 443/tcp
            else
                sudo ufw allow $NGINX_PORT/tcp
            fi

            sudo ufw --force enable
            log "${GREEN}✓ UFW enabled and configured for port $NGINX_PORT${NC}"
        fi
    fi
else
    log "${YELLOW}~ UFW not installed - skipping firewall configuration${NC}"
    log "${YELLOW}  You may need to manually configure your firewall to allow port $NGINX_PORT${NC}"
fi

# =============================================================================
# Step 11: Start and Enable Services
# =============================================================================
log ""
log "${YELLOW}Starting and enabling all services...${NC}"

# Check for port conflicts before starting Nginx
log "${YELLOW}Checking for port conflicts on port $NGINX_PORT...${NC}"
PORT_IN_USE=$(sudo lsof -i :$NGINX_PORT -sTCP:LISTEN -t 2>/dev/null || echo "")

if [ -n "$PORT_IN_USE" ]; then
    CONFLICTING_PROCESS=$(sudo lsof -i :$NGINX_PORT -sTCP:LISTEN | tail -n +2)
    log "${RED}✗ Port $NGINX_PORT is already in use by another process:${NC}"
    echo "$CONFLICTING_PROCESS" | tee -a "$LOG_FILE"
    log ""
    log "${YELLOW}Resolution options:${NC}"
    log "${YELLOW}  1. Stop the conflicting service (if safe to do so)${NC}"
    log "${YELLOW}  2. Re-run deploy.sh and choose a different port (e.g., 8080)${NC}"
    log "${YELLOW}  3. Configure Traefik/reverse proxy to forward to this application${NC}"
    log ""
    log "${RED}Deployment cannot continue with port conflict.${NC}"
    exit 1
else
    log "${GREEN}✓ Port $NGINX_PORT is available${NC}"
fi

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
log "${GREEN}=== Debian/Ubuntu Configuration Complete ===${NC}"
