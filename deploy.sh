#!/bin/bash
# deploy.sh - Universal deployment orchestrator for ZKTeco Management System
# This script auto-detects the project directory and calls OS-specific subscripts

# Exit immediately if a command exits with a non-zero status
set -e

# =============================================================================
# Color Variables (exported for subscripts)
# =============================================================================
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export NC='\033[0m' # No Color

# =============================================================================
# Auto-Detect Project Directory
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

# Verify this is a Django project directory
echo -e "${YELLOW}Verifying project directory: $PROJECT_DIR${NC}"

# Check for required files
REQUIRED_FILES=("manage.py" "requirements.txt")
MISSING_FILES=()

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$PROJECT_DIR/$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}ERROR: Invalid Django project directory${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo -e "${YELLOW}This script must be run from the root directory of the ZKTeco Management System.${NC}"
    echo ""
    echo -e "${YELLOW}Current directory: $PROJECT_DIR${NC}"
    echo ""
    echo -e "${RED}Missing required files:${NC}"
    for file in "${MISSING_FILES[@]}"; do
        echo -e "  ${RED}✗ $file${NC}"
    done
    echo ""
    echo -e "${YELLOW}Please navigate to the project directory and run this script from there.${NC}"
    echo -e "${YELLOW}Example: cd /opt/CCP/zktecoMGMT && sudo ./deploy.sh${NC}"
    exit 1
fi

# Check for settings.py in zkteco_project
if [ ! -f "$PROJECT_DIR/zkteco_project/settings.py" ]; then
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}WARNING: Django settings.py not found${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo -e "${YELLOW}Expected location: $PROJECT_DIR/zkteco_project/settings.py${NC}"
    echo ""
    read -p "$(echo -e ${YELLOW}Do you want to continue anyway?${NC}) (y/n) [n]: " CONTINUE
    if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo -e "${GREEN}✓ Project directory validated: $PROJECT_DIR${NC}"
echo ""

# =============================================================================
# Logging Setup
# =============================================================================
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/deployment_$(date +%Y%m%d_%H%M%S).log"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Log function
log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

log "${BLUE}========================================${NC}"
log "${BLUE}   ZKTeco Management System Setup${NC}"
log "${BLUE}========================================${NC}"
log ""
log "${GREEN}Deployment log: $LOG_FILE${NC}"
log ""

# =============================================================================
# Detect Operating System
# =============================================================================
log "${YELLOW}Detecting operating system...${NC}"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    log "${GREEN}✓ Detected OS: $OS ($PRETTY_NAME)${NC}"
else
    log "${RED}✗ Cannot detect operating system${NC}"
    exit 1
fi

# Determine OS family
if [[ "$OS" == "ubuntu" || "$OS" == "debian" ]]; then
    OS_FAMILY="debian"
    OS_SCRIPT="$PROJECT_DIR/deploy_debian.sh"
elif [[ "$OS" == "rhel" || "$OS" == "fedora" || "$OS" == "centos" || "$OS" == "rocky" || "$OS" == "almalinux" ]]; then
    OS_FAMILY="rhel"
    OS_SCRIPT="$PROJECT_DIR/deploy_rhel.sh"
else
    log "${RED}✗ Unsupported OS: $OS${NC}"
    log "${YELLOW}Supported: Debian, Ubuntu, RHEL, AlmaLinux, Fedora, CentOS, Rocky Linux${NC}"
    exit 1
fi

log "${GREEN}✓ OS Family: $OS_FAMILY${NC}"
log "${YELLOW}OS-specific script: $OS_SCRIPT${NC}"

# Verify OS-specific script exists
if [ ! -f "$OS_SCRIPT" ]; then
    log "${RED}✗ OS-specific script not found: $OS_SCRIPT${NC}"
    exit 1
fi

# Export variables for subscripts
export PROJECT_DIR
export LOG_FILE
export OS
export OS_FAMILY

# =============================================================================
# Virtual Environment Setup
# =============================================================================
log ""
log "${YELLOW}Virtual Environment Setup:${NC}"
read -p "$(echo -e ${YELLOW}Enter virtual environment name${NC}) [zkteco_env]: " VENV_NAME
VENV_NAME=${VENV_NAME:-zkteco_env}
export VENV_PATH="$PROJECT_DIR/$VENV_NAME"

log "${YELLOW}Virtual environment path: $VENV_PATH${NC}"

# Check if venv already exists
if [ -d "$VENV_PATH" ]; then
    log "${YELLOW}Virtual environment '$VENV_NAME' already exists at $VENV_PATH${NC}"
    read -p "$(echo -e ${YELLOW}Do you want to delete and recreate it?${NC}) (y/n) [n]: " RECREATE_VENV
    if [[ "$RECREATE_VENV" =~ ^[Yy]$ ]]; then
        log "${YELLOW}Deleting existing virtual environment...${NC}"
        rm -rf "$VENV_PATH"
        log "${GREEN}✓ Deleted existing virtual environment${NC}"
    else
        log "${YELLOW}Using existing virtual environment${NC}"
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_PATH" ]; then
    log "${YELLOW}Creating virtual environment '$VENV_NAME'...${NC}"
    python3 -m venv "$VENV_PATH"
    if [ $? -eq 0 ]; then
        log "${GREEN}✓ Virtual environment created at $VENV_PATH${NC}"
    else
        log "${RED}✗ Failed to create virtual environment${NC}"
        exit 1
    fi
fi

# Fix venv ownership for the actual user (not root)
if [ -n "$SUDO_USER" ]; then
    log "${YELLOW}Setting venv ownership to $SUDO_USER...${NC}"
    chown -R $SUDO_USER:$SUDO_USER "$VENV_PATH"
    log "${GREEN}✓ Virtual environment owned by $SUDO_USER${NC}"
fi

# Activate virtual environment
log "${YELLOW}Activating virtual environment...${NC}"
source "$VENV_PATH/bin/activate"
if [ $? -eq 0 ]; then
    log "${GREEN}✓ Virtual environment activated${NC}"
else
    log "${RED}✗ Failed to activate virtual environment${NC}"
    exit 1
fi

# =============================================================================
# User Input for Database Configuration
# =============================================================================
log ""
log "${BLUE}========================================${NC}"
log "${BLUE}   Database & Configuration Setup${NC}"
log "${BLUE}========================================${NC}"
log ""

log "${YELLOW}Please provide the following information:${NC}"
log ""

# Database name
read -p "$(echo -e ${YELLOW}Enter database name${NC} [zkteco_db]: )" DB_NAME
DB_NAME=${DB_NAME:-zkteco_db}
export DB_NAME
log "${GREEN}✓ Database name: $DB_NAME${NC}"

# Database user
read -p "$(echo -e ${YELLOW}Enter database user${NC} [kb_db]: )" DB_USER
DB_USER=${DB_USER:-kb_db}
export DB_USER
log "${GREEN}✓ Database user: $DB_USER${NC}"

# Database password
read -sp "$(echo -e ${YELLOW}Enter database password${NC}: )" DB_PASSWORD
echo ""
if [ -z "$DB_PASSWORD" ]; then
    log "${RED}✗ Password cannot be empty${NC}"
    exit 1
fi
export DB_PASSWORD
log "${GREEN}✓ Password set${NC}"

# Allowed hosts
read -p "$(echo -e "${YELLOW}Enter allowed hosts (comma-separated)${NC}") [localhost,127.0.0.1]: " ALLOWED_HOSTS
ALLOWED_HOSTS=${ALLOWED_HOSTS:-localhost,127.0.0.1}
log "${GREEN}✓ Allowed hosts: $ALLOWED_HOSTS${NC}"

# Nginx public port
log ""
log "${YELLOW}Port Configuration:${NC}"
log "${YELLOW}  - Nginx (public access): Port for users to access the application${NC}"
log "${YELLOW}  - Gunicorn (internal): Localhost-only port for Django backend${NC}"
log ""
read -p "$(echo -e "${YELLOW}Enter Nginx public port${NC}") [80]: " NGINX_PORT
NGINX_PORT=${NGINX_PORT:-80}
export NGINX_PORT
log "${GREEN}✓ Nginx public port: $NGINX_PORT${NC}"

# Gunicorn internal port
read -p "$(echo -e "${YELLOW}Enter Gunicorn internal port${NC}") [8000]: " GUNICORN_PORT
GUNICORN_PORT=${GUNICORN_PORT:-8000}
export GUNICORN_PORT
log "${GREEN}✓ Gunicorn internal port: $GUNICORN_PORT${NC}"

# For backward compatibility with .env and scripts
export SERVER_PORT=$GUNICORN_PORT

# Test mode
read -p "$(echo -e "${YELLOW}Enable TEST MODE?${NC}") (y/n) [n]: " TEST_MODE_INPUT
TEST_MODE_INPUT=${TEST_MODE_INPUT:-n}
if [[ "$TEST_MODE_INPUT" =~ ^[Yy]$ ]]; then
    ZK_TEST_MODE="True"
else
    ZK_TEST_MODE="False"
fi
log "${GREEN}✓ Test mode: $ZK_TEST_MODE${NC}"

# =============================================================================
# Install Python Dependencies
# =============================================================================
log ""
log "${YELLOW}Installing Python dependencies...${NC}"

# Upgrade pip
log "${YELLOW}Upgrading pip...${NC}"
python3 -m pip install --upgrade pip > /dev/null 2>&1
if [ $? -eq 0 ]; then
    log "${GREEN}✓ Pip upgraded${NC}"
else
    log "${YELLOW}~ Pip upgrade skipped or encountered issues${NC}"
fi

# Install requirements
if [ -f "requirements.txt" ]; then
    log "${YELLOW}Installing requirements from requirements.txt...${NC}"
    python3 -m pip install --ignore-installed -r requirements.txt 2>&1 | tee -a "$LOG_FILE"
    if [ $? -eq 0 ]; then
        log "${GREEN}✓ Requirements installed successfully${NC}"
    else
        log "${RED}✗ Failed to install requirements${NC}"
        exit 1
    fi
else
    log "${RED}✗ requirements.txt not found in $PROJECT_DIR${NC}"
    exit 1
fi

# =============================================================================
# Generate .env File
# =============================================================================
log ""
log "${YELLOW}Generating .env file...${NC}"

# Delete existing .env file if it exists
if [ -f ".env" ]; then
    rm .env
    log "${GREEN}✓ Deleted existing .env file${NC}"
fi

# Generate a strong secret key (Django is now installed)
SECRET_KEY=$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')

# Build DATABASE_URL
DATABASE_URL="postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME"

# Create new .env file with quoted SECRET_KEY to handle special characters
cat > .env << EOF
DEBUG=False
SECRET_KEY='$SECRET_KEY'
ALLOWED_HOSTS=$ALLOWED_HOSTS
ZK_TEST_MODE=$ZK_TEST_MODE
DATABASE_URL=$DATABASE_URL
SERVER_PORT=$SERVER_PORT
EOF

log "${GREEN}✓ Created new .env file${NC}"
log "${GREEN}  Generated SECRET_KEY: ${SECRET_KEY:0:20}...${NC}"
log "${GREEN}  DATABASE_URL: postgresql://$DB_USER:***@localhost/$DB_NAME${NC}"
log "${GREEN}  SERVER_PORT: $SERVER_PORT${NC}"

# =============================================================================
# Call OS-Specific Subscript
# =============================================================================
log ""
log "${BLUE}========================================${NC}"
log "${BLUE}   OS-Specific Configuration${NC}"
log "${BLUE}========================================${NC}"
log ""

log "${YELLOW}Executing OS-specific script: $OS_SCRIPT${NC}"

# Make script executable
chmod +x "$OS_SCRIPT"

# Source the OS-specific script (runs in same shell to inherit variables)
source "$OS_SCRIPT"

# Check if subscript succeeded
if [ $? -ne 0 ]; then
    log "${RED}✗ OS-specific script failed${NC}"
    log "${YELLOW}Check log for details: $LOG_FILE${NC}"
    exit 1
fi

log "${GREEN}✓ OS-specific configuration completed${NC}"

# =============================================================================
# Test Database Connection (Universal)
# =============================================================================
log ""
log "${YELLOW}Testing database connection...${NC}"

PGPASSWORD="$DB_PASSWORD" psql -h localhost -U "$DB_USER" -d "$DB_NAME" -c "SELECT version();" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Database connection successful${NC}"
else
    log "${RED}✗ Database connection failed${NC}"
    log "${YELLOW}Troubleshooting:${NC}"
    log "  1. Check if PostgreSQL is running: sudo systemctl status postgresql"
    log "  2. Check pg_hba.conf authentication settings"
    log "  3. Verify database and user exist"
    log "  4. Check password is correct"

    # Try to diagnose the issue
    log "${YELLOW}Attempting to diagnose issue...${NC}"

    # Check if we can connect as postgres user
    if sudo -u postgres psql -c "SELECT 1;" > /dev/null 2>&1; then
        log "${GREEN}✓ PostgreSQL is running and accessible${NC}"

        # Check if database exists
        if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
            log "${GREEN}✓ Database $DB_NAME exists${NC}"
        else
            log "${RED}✗ Database $DB_NAME not found${NC}"
        fi

        # Check if user exists
        if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
            log "${GREEN}✓ User $DB_USER exists${NC}"
        else
            log "${RED}✗ User $DB_USER not found${NC}"
        fi
    else
        log "${RED}✗ Cannot connect to PostgreSQL${NC}"
    fi

    exit 1
fi

# =============================================================================
# Create Django Migrations
# =============================================================================
log ""
log "${YELLOW}Creating Django migrations...${NC}"
python3 manage.py makemigrations 2>&1 | tee -a "$LOG_FILE"
if [ $? -eq 0 ]; then
    log "${GREEN}✓ Django migrations created${NC}"
else
    log "${YELLOW}~ No new migrations to create (this is normal)${NC}"
fi

# =============================================================================
# Run Django Migrations
# =============================================================================
log ""
log "${YELLOW}Applying Django migrations...${NC}"
python3 manage.py migrate 2>&1 | tee -a "$LOG_FILE"
if [ $? -eq 0 ]; then
    log "${GREEN}✓ Django migrations applied${NC}"
else
    log "${RED}✗ Django migrations failed${NC}"
    log "${YELLOW}Check DATABASE_URL in .env file${NC}"
    exit 1
fi

# =============================================================================
# Create Superuser
# =============================================================================
log ""
log "${YELLOW}Creating Django superuser...${NC}"
log "${BLUE}Please enter your admin credentials:${NC}"
python3 manage.py createsuperuser
if [ $? -eq 0 ]; then
    log "${GREEN}✓ Superuser created${NC}"
else
    log "${RED}✗ Failed to create superuser${NC}"
    exit 1
fi

# =============================================================================
# Create Media Directory
# =============================================================================
log ""
log "${YELLOW}Creating media directory...${NC}"

if [ ! -d "$PROJECT_DIR/media" ]; then
    mkdir -p "$PROJECT_DIR/media"
    log "${GREEN}✓ Created media directory${NC}"
else
    log "${GREEN}✓ Media directory already exists${NC}"
fi

# Set ownership and permissions
if [ -n "$SUDO_USER" ]; then
    chown -R $SUDO_USER:$SUDO_USER "$PROJECT_DIR/media"
    log "${GREEN}✓ Set media directory ownership to $SUDO_USER${NC}"
fi
chmod 755 "$PROJECT_DIR/media"
log "${GREEN}✓ Set media directory permissions${NC}"

# =============================================================================
# Collect Static Files
# =============================================================================
log ""
log "${YELLOW}Collecting static files...${NC}"

# Fix staticfiles directory ownership if it exists
if [ -d "$PROJECT_DIR/staticfiles" ]; then
    if [ -n "$SUDO_USER" ]; then
        log "${YELLOW}Setting staticfiles ownership to $SUDO_USER...${NC}"
        chown -R $SUDO_USER:$SUDO_USER "$PROJECT_DIR/staticfiles"
    fi
fi

python3 manage.py collectstatic --noinput 2>&1 | tee -a "$LOG_FILE"
if [ $? -eq 0 ]; then
    log "${GREEN}✓ Static files collected${NC}"
else
    log "${RED}✗ Failed to collect static files${NC}"
    exit 1
fi

# Fix ownership after collectstatic
if [ -d "$PROJECT_DIR/staticfiles" ]; then
    if [ -n "$SUDO_USER" ]; then
        chown -R $SUDO_USER:$SUDO_USER "$PROJECT_DIR/staticfiles"
    fi
fi

# =============================================================================
# Configure Firewall (UFW)
# =============================================================================
log ""
log "${YELLOW}Configuring firewall...${NC}"

# Check if UFW is installed
if command -v ufw &> /dev/null; then
    # Check if UFW is active
    UFW_STATUS=$(sudo ufw status | grep -i "Status:" | awk '{print $2}')

    if [ "$UFW_STATUS" == "active" ]; then
        log "${GREEN}✓ UFW is active${NC}"
    else
        log "${YELLOW}UFW is installed but not active${NC}"
        read -p "$(echo -e ${YELLOW}Do you want to enable UFW?${NC}) (y/n) [y]: " ENABLE_UFW
        ENABLE_UFW=${ENABLE_UFW:-y}

        if [[ "$ENABLE_UFW" =~ ^[Yy]$ ]]; then
            # Allow SSH first to prevent lockout
            sudo ufw allow 22/tcp
            log "${GREEN}✓ Allowed SSH (port 22)${NC}"

            sudo ufw --force enable
            log "${GREEN}✓ UFW enabled${NC}"
        fi
    fi

    # Allow the server port
    if sudo ufw status | grep -q "$SERVER_PORT"; then
        log "${GREEN}✓ Port $SERVER_PORT already allowed in UFW${NC}"
    else
        sudo ufw allow $SERVER_PORT/tcp
        if [ $? -eq 0 ]; then
            log "${GREEN}✓ Opened port $SERVER_PORT in UFW${NC}"
        else
            log "${RED}✗ Failed to open port $SERVER_PORT in UFW${NC}"
        fi
    fi

    # Show current UFW status
    log ""
    log "${YELLOW}Current UFW status:${NC}"
    sudo ufw status numbered | tee -a "$LOG_FILE"
else
    log "${YELLOW}~ UFW not installed - skipping firewall configuration${NC}"
    log "${YELLOW}  You may need to manually open port $SERVER_PORT${NC}"
fi

# =============================================================================
# Deployment Complete
# =============================================================================
log ""
log "${BLUE}========================================${NC}"
log "${GREEN}✓ Setup complete!${NC}"
log "${BLUE}========================================${NC}"
log ""
log "${YELLOW}Configuration Summary:${NC}"
log "  Project Directory: $PROJECT_DIR"
log "  Virtual Environment: $VENV_PATH"
log "  Database: $DB_NAME"
log "  Database User: $DB_USER"
log "  Nginx Port (public): $NGINX_PORT"
log "  Gunicorn Port (internal): $GUNICORN_PORT"
log "  Test Mode: $ZK_TEST_MODE"
log "  Allowed Hosts: $ALLOWED_HOSTS"
log "  Deployment Log: $LOG_FILE"
log ""
log "${YELLOW}Systemd Services Created:${NC}"
log "  Gunicorn:  /etc/systemd/system/gunicorn.service"
log "  Django-Q2: /etc/systemd/system/django-q.service"
log ""
log "${YELLOW}Systemd Service Management:${NC}"
log "  Check all services:  ${BLUE}sudo systemctl status nginx gunicorn django-q postgresql${NC}"
log "  Check gunicorn:      ${BLUE}sudo systemctl status gunicorn${NC}"
log "  Check django-q:      ${BLUE}sudo systemctl status django-q${NC}"
log "  Check nginx:         ${BLUE}sudo systemctl status nginx${NC}"
log "  View gunicorn logs:  ${BLUE}sudo journalctl -u gunicorn -f${NC}"
log "  View django-q logs:  ${BLUE}sudo journalctl -u django-q -f${NC}"
log "  View nginx logs:     ${BLUE}sudo tail -f /var/log/nginx/error.log${NC}"
log "  Restart gunicorn:    ${BLUE}sudo systemctl restart gunicorn${NC}"
log "  Restart django-q:    ${BLUE}sudo systemctl restart django-q${NC}"
log "  Restart nginx:       ${BLUE}sudo systemctl restart nginx${NC}"
log ""
log "${YELLOW}Application Access:${NC}"
if [ "$NGINX_PORT" -eq 80 ]; then
    log "  Main application:    ${BLUE}http://$(echo $ALLOWED_HOSTS | cut -d',' -f1)/${NC}"
    log "  Admin panel:         ${BLUE}http://$(echo $ALLOWED_HOSTS | cut -d',' -f1)/admin${NC}"
    log "  Static files:        ${BLUE}http://$(echo $ALLOWED_HOSTS | cut -d',' -f1)/static/${NC}"
else
    log "  Main application:    ${BLUE}http://$(echo $ALLOWED_HOSTS | cut -d',' -f1):$NGINX_PORT/${NC}"
    log "  Admin panel:         ${BLUE}http://$(echo $ALLOWED_HOSTS | cut -d',' -f1):$NGINX_PORT/admin${NC}"
    log "  Static files:        ${BLUE}http://$(echo $ALLOWED_HOSTS | cut -d',' -f1):$NGINX_PORT/static/${NC}"
fi
log ""
log "${YELLOW}Development:${NC}"
log "  Activate venv:       ${BLUE}source $VENV_PATH/bin/activate${NC}"
log "  Django shell:        ${BLUE}python manage.py shell${NC}"
log "  Make migrations:     ${BLUE}python manage.py makemigrations${NC}"
log "  Apply migrations:    ${BLUE}python manage.py migrate${NC}"
log "  Collect static:      ${BLUE}python manage.py collectstatic${NC}"
log ""
log "${YELLOW}Important Notes:${NC}"
log "  - Nginx runs on port $NGINX_PORT (public) and proxies to Gunicorn on localhost:$GUNICORN_PORT"
log "  - Gunicorn serves Django on localhost:$GUNICORN_PORT (not publicly exposed)"
log "  - Django-Q2 processes background tasks (employee sync, attendance download)"
log "  - All services run as user: $([ -n "$SUDO_USER" ] && echo "$SUDO_USER" || echo "$(whoami)")"
log ""
