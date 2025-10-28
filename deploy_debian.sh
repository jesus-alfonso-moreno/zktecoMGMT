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
# Step 1: Install PostgreSQL Server and Development Libraries
# =============================================================================
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
else
    log "${RED}✗ Failed to install PostgreSQL packages${NC}"
    exit 1
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
# Step 2: Configure PostgreSQL Authentication (pg_hba.conf)
# =============================================================================
log "${YELLOW}Configuring PostgreSQL authentication...${NC}"

# Find the correct pg_hba.conf file
PG_VERSION=$(sudo -u postgres psql -tAc "SHOW server_version;" | cut -d'.' -f1)
PG_HBA_CONF="/etc/postgresql/${PG_VERSION}/main/pg_hba.conf"

if [ ! -f "$PG_HBA_CONF" ]; then
    # Fallback: find it
    PG_HBA_CONF=$(sudo find /etc/postgresql -name pg_hba.conf | head -n 1)
fi

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
else
    log "${RED}✗ Could not find pg_hba.conf${NC}"
    exit 1
fi

# =============================================================================
# Step 3: Create PostgreSQL Database and User
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
# Step 4: Configure Gunicorn Systemd Service
# =============================================================================
log "${YELLOW}Configuring gunicorn systemd service...${NC}"

# Use the venv paths from main deploy.sh
PYTHON_BIN="$VENV_PATH/bin/python3"
GUNICORN_BIN="$VENV_PATH/bin/gunicorn"

# Create systemd service file
SYSTEMD_SERVICE="/etc/systemd/system/gunicorn.service"

sudo tee "$SYSTEMD_SERVICE" > /dev/null << EOF
[Unit]
Description=gunicorn daemon for zkteco
After=network.target

[Service]
User=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_PATH/bin"
ExecStart=$GUNICORN_BIN zkteco_project.wsgi:application --bind 0.0.0.0:$SERVER_PORT
Restart=always

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
# Step 5: Configure Django-Q2 Systemd Service
# =============================================================================
log "${YELLOW}Configuring Django-Q2 worker service...${NC}"

DJANGOQ_SERVICE="/etc/systemd/system/django-q.service"

sudo tee "$DJANGOQ_SERVICE" > /dev/null << EOF
[Unit]
Description=Django-Q2 Worker Cluster
After=network.target postgresql.service

[Service]
User=root
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

log "${GREEN}=== Debian/Ubuntu Configuration Complete ===${NC}"
