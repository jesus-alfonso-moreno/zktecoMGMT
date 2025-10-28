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
