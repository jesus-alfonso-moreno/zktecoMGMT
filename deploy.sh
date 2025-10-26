#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   ZKTeco Management System Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get project directory
PROJECT_DIR=$(pwd)

echo -e "${YELLOW}Project Directory: $PROJECT_DIR${NC}"
echo ""

# Step 0: Get virtual environment name
echo -e "${YELLOW}Virtual Environment Setup:${NC}"
read -p "$(echo -e ${YELLOW}Enter virtual environment name${NC} [zkteco_env]: )" VENV_NAME
VENV_NAME=${VENV_NAME:-zkteco_env}
VENV_PATH="$PROJECT_DIR/$VENV_NAME"

# Check if venv already exists
if [ -d "$VENV_PATH" ]; then
    echo -e "${YELLOW}Virtual environment '$VENV_NAME' already exists at $VENV_PATH${NC}"
    read -p "$(echo -e ${YELLOW}Do you want to delete and recreate it?${NC} (y/n) [n]: )" RECREATE_VENV
    if [[ "$RECREATE_VENV" =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Deleting existing virtual environment...${NC}"
        rm -rf "$VENV_PATH"
        echo -e "${GREEN}✓ Deleted existing virtual environment${NC}"
    else
        echo -e "${YELLOW}Using existing virtual environment${NC}"
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${YELLOW}Creating virtual environment '$VENV_NAME'...${NC}"
    python3 -m venv "$VENV_PATH"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Virtual environment created at $VENV_PATH${NC}"
    else
        echo -e "${RED}✗ Failed to create virtual environment${NC}"
        exit 1
    fi
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source "$VENV_PATH/bin/activate"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
else
    echo -e "${RED}✗ Failed to activate virtual environment${NC}"
    exit 1
fi

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
python3 -m pip install --upgrade pip > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Pip upgraded${NC}"
else
    echo -e "${YELLOW}~ Pip upgrade skipped or encountered issues${NC}"
fi

# Install requirements
if [ -f "requirements.txt" ]; then
    echo -e "${YELLOW}Installing requirements from requirements.txt...${NC}"
    python3 -m pip install -r requirements.txt
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Requirements installed successfully${NC}"
    else
        echo -e "${RED}✗ Failed to install requirements${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ requirements.txt not found in $PROJECT_DIR${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Database & Configuration Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Get user input
echo -e "${YELLOW}Please provide the following information:${NC}"
echo ""

# Database name
read -p "$(echo -e ${YELLOW}Enter database name${NC} [zkteco_db]: )" DB_NAME
DB_NAME=${DB_NAME:-zkteco_db}
echo -e "${GREEN}✓ Database name: $DB_NAME${NC}"

# Database user
read -p "$(echo -e ${YELLOW}Enter database user${NC} [kb_db]: )" DB_USER
DB_USER=${DB_USER:-kb_db}
echo -e "${GREEN}✓ Database user: $DB_USER${NC}"

# Database password
read -sp "$(echo -e ${YELLOW}Enter database password${NC}: )" DB_PASSWORD
echo ""
if [ -z "$DB_PASSWORD" ]; then
    echo -e "${RED}✗ Password cannot be empty${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Password set${NC}"

# Allowed hosts
read -p "$(echo -e ${YELLOW}Enter allowed hosts${NC} (comma-separated) [localhost,127.0.0.1]: )" ALLOWED_HOSTS
ALLOWED_HOSTS=${ALLOWED_HOSTS:-localhost,127.0.0.1}
echo -e "${GREEN}✓ Allowed hosts: $ALLOWED_HOSTS${NC}"

# Test mode
read -p "$(echo -e ${YELLOW}Enable TEST MODE?${NC} (y/n) [n]: )" TEST_MODE_INPUT
TEST_MODE_INPUT=${TEST_MODE_INPUT:-n}
if [[ "$TEST_MODE_INPUT" =~ ^[Yy]$ ]]; then
    ZK_TEST_MODE="True"
else
    ZK_TEST_MODE="False"
fi
echo -e "${GREEN}✓ Test mode: $ZK_TEST_MODE${NC}"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Proceeding with setup...${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 2: Delete existing .env file if it exists
if [ -f ".env" ]; then
    rm .env
    echo -e "${GREEN}✓ Deleted existing .env file${NC}"
else
    echo -e "${YELLOW}No existing .env file found${NC}"
fi

# Step 3: Generate a strong secret key
echo -e "${YELLOW}Generating secret key...${NC}"
SECRET_KEY=$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')

# Build DATABASE_URL
DATABASE_URL="postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME"

# Step 4: Create new .env file
cat > .env << EOF
DEBUG=False
SECRET_KEY=$SECRET_KEY
ALLOWED_HOSTS=$ALLOWED_HOSTS
ZK_TEST_MODE=$ZK_TEST_MODE
DATABASE_URL=$DATABASE_URL
EOF

echo -e "${GREEN}✓ Created new .env file${NC}"
echo -e "${GREEN}  Generated SECRET_KEY: ${SECRET_KEY:0:20}...${NC}"
echo -e "${GREEN}  DATABASE_URL: $DATABASE_URL${NC}"

# Step 5: Create PostgreSQL database
echo -e "${YELLOW}Creating PostgreSQL database '$DB_NAME'...${NC}"
sudo -u postgres createdb "$DB_NAME"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database $DB_NAME created${NC}"
else
    echo -e "${RED}✗ Failed to create database${NC}"
    exit 1
fi

# Step 6: Create PostgreSQL user and grant all necessary privileges
echo -e "${YELLOW}Creating PostgreSQL user '$DB_USER' and granting privileges...${NC}"
sudo -u postgres psql << SQL
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
SQL

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Failed to create user or grant database privileges${NC}"
    exit 1
fi

# Grant schema-level privileges
sudo -u postgres psql -d "$DB_NAME" << SQL
GRANT ALL ON SCHEMA public TO $DB_USER;
GRANT USAGE ON SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
SQL

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Failed to grant schema privileges${NC}"
    exit 1
fi

echo -e "${GREEN}✓ User $DB_USER created and all privileges granted${NC}"

# Step 7: Run Django migrations
echo -e "${YELLOW}Running Django migrations...${NC}"
python3 manage.py migrate
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Django migrations completed${NC}"
else
    echo -e "${RED}✗ Django migrations failed${NC}"
    exit 1
fi

# Step 8: Create superuser
echo -e "${YELLOW}Creating Django superuser...${NC}"
python3 manage.py createsuperuser
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Superuser created${NC}"
else
    echo -e "${RED}✗ Failed to create superuser${NC}"
    exit 1
fi

# Step 9: Check and install gunicorn if needed
echo -e "${YELLOW}Checking for gunicorn...${NC}"
python3 -m pip show gunicorn > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Gunicorn is already installed${NC}"
else
    echo -e "${YELLOW}Installing gunicorn...${NC}"
    python3 -m pip install gunicorn
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Gunicorn installed successfully${NC}"
    else
        echo -e "${RED}✗ Failed to install gunicorn${NC}"
        exit 1
    fi
fi

# Step 10: Collect static files
echo -e "${YELLOW}Collecting static files...${NC}"
python3 manage.py collectstatic --noinput
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Static files collected${NC}"
else
    echo -e "${RED}✗ Failed to collect static files${NC}"
    exit 1
fi

# Step 11: Configure gunicorn systemd service
echo -e "${YELLOW}Configuring gunicorn systemd service...${NC}"

# Use the venv we just created
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
ExecStart=$GUNICORN_BIN zkteco_project.wsgi:application --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Gunicorn service file created at $SYSTEMD_SERVICE${NC}"
else
    echo -e "${RED}✗ Failed to create gunicorn service file${NC}"
    exit 1
fi

# Reload systemd and enable gunicorn
echo -e "${YELLOW}Enabling and starting gunicorn service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable gunicorn.service
sudo systemctl start gunicorn.service

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Gunicorn service enabled and started${NC}"
else
    echo -e "${RED}✗ Failed to start gunicorn service${NC}"
    exit 1
fi

# Check service status
sleep 2
sudo systemctl status gunicorn.service

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Setup complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Configuration Summary:${NC}"
echo -e "  Project Directory: $PROJECT_DIR"
echo -e "  Virtual Environment: $VENV_PATH"
echo -e "  Database: $DB_NAME"
echo -e "  Database User: $DB_USER"
echo -e "  Test Mode: $ZK_TEST_MODE"
echo -e "  Allowed Hosts: $ALLOWED_HOSTS"
echo -e "  Gunicorn Service: $SYSTEMD_SERVICE"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo -e "  Activate venv:     ${BLUE}source $VENV_PATH/bin/activate${NC}"
echo -e "  Check status:      ${BLUE}sudo systemctl status gunicorn${NC}"
echo -e "  View logs:         ${BLUE}sudo journalctl -u gunicorn -f${NC}"
echo -e "  Restart service:   ${BLUE}sudo systemctl restart gunicorn${NC}"
echo -e "  Access admin:      ${BLUE}http://$ALLOWED_HOSTS:8000/admin${NC}"
echo ""
