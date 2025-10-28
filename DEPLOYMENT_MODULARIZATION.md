# Deployment Script Modularization - Complete

## Overview

The deployment script has been successfully modularized into a maintainable architecture with OS-specific subscripts.

## Architecture

```
deploy.sh (Universal Orchestrator)
├── deploy_debian.sh (Debian/Ubuntu specific)
└── deploy_rhel.sh (RHEL/AlmaLinux/Fedora specific)
```

### File Descriptions

#### `deploy.sh` - Universal Orchestrator
**Purpose**: Main entry point containing only OS-agnostic operations

**Responsibilities**:
- OS detection and family determination
- Logging setup with timestamped log files
- Virtual environment creation and ownership management
- User input collection (database credentials, allowed hosts, etc.)
- `.env` file generation with SECRET_KEY
- Python dependency installation via pip
- Calling OS-specific subscripts
- Universal database connection testing
- Django migrations
- Superuser creation
- Static files collection
- Deployment summary

**Key Features**:
- Exports color variables for subscripts
- Fixes venv ownership to $SUDO_USER (not root)
- Creates comprehensive deployment logs in `logs/`
- Error handling with immediate exit on failure
- Validates subscript existence before calling

#### `deploy_debian.sh` - Debian/Ubuntu Specific Operations
**Purpose**: Debian-based system configuration

**Responsibilities**:
1. PostgreSQL server installation (apt-get)
2. PostgreSQL development libraries (postgresql-server-dev-all, libpq-dev)
3. PostgreSQL service start/enable
4. pg_hba.conf configuration (Debian path: `/etc/postgresql/*/main/pg_hba.conf`)
5. Database and user creation/validation
6. Gunicorn systemd service creation
7. Django-Q2 systemd service creation

**Uses verified approach from**: `gunicorn_ubuntu_example.sh`

#### `deploy_rhel.sh` - RHEL/AlmaLinux/Fedora Specific Operations
**Purpose**: RHEL-based system configuration

**Responsibilities**:
1. PostgreSQL server installation (dnf)
2. PostgreSQL development libraries (postgresql-server-devel)
3. PostgreSQL initialization (`postgresql-setup --initdb`)
4. PostgreSQL service start/enable
5. pg_hba.conf configuration (RHEL path: `/var/lib/pgsql/data/pg_hba.conf`)
6. Database and user creation/validation
7. Gunicorn systemd service creation
8. Django-Q2 systemd service creation

**RHEL-Specific**:
- Database cluster initialization required before first use
- Handles incomplete data directory cleanup
- Different pg_hba.conf location

## Usage

### Running Deployment

```bash
sudo ./deploy.sh
```

**The script will**:
1. Detect your OS automatically
2. Prompt for configuration (venv name, database credentials, etc.)
3. Create virtual environment owned by the installing user
4. Install Python dependencies
5. Call the appropriate OS-specific subscript
6. Set up PostgreSQL with md5 authentication
7. Create systemd services for Gunicorn and Django-Q2
8. Run migrations and create superuser
9. Collect static files
10. Provide comprehensive summary

### Logs

All deployment activity is logged to:
```
logs/deployment_YYYYMMDD_HHMMSS.log
```

This enables self-correction and troubleshooting without user intervention.

## Key Improvements

### 1. Virtual Environment Ownership
**Problem**: Packages were installing to `~/.local/bin` instead of venv when running with sudo.

**Solution**:
```bash
if [ -n "$SUDO_USER" ]; then
    chown -R $SUDO_USER:$SUDO_USER "$VENV_PATH"
fi
```

Applied before pip install to ensure venv is writable by the correct user.

### 2. Static Files Ownership
**Problem**: Staticfiles directory owned by root after collectstatic.

**Solution**:
```bash
# Before and after collectstatic
if [ -d "$PROJECT_DIR/staticfiles" ]; then
    if [ -n "$SUDO_USER" ]; then
        chown -R $SUDO_USER:$SUDO_USER "$PROJECT_DIR/staticfiles"
    fi
fi
```

### 3. Comprehensive Logging
**Features**:
- Timestamped log files
- All output captured to log
- Error diagnostics logged
- Service status logged

**Purpose**: Enables self-correction by reviewing logs.

### 4. Error Handling
```bash
set -e  # Exit immediately on error

# After subscript call
if [ $? -ne 0 ]; then
    log "${RED}✗ OS-specific script failed${NC}"
    exit 1
fi
```

All scripts stop immediately on any failure.

### 5. Variable Exports
```bash
export RED GREEN YELLOW BLUE NC      # Colors
export PROJECT_DIR LOG_FILE           # Paths
export OS OS_FAMILY                   # System info
export VENV_PATH                      # Virtual environment
export DB_NAME DB_USER DB_PASSWORD    # Database config
```

Subscripts inherit all necessary variables from main script.

## Systemd Services Created

### Gunicorn Service
**File**: `/etc/systemd/system/gunicorn.service`

```ini
[Unit]
Description=gunicorn daemon for zkteco
After=network.target

[Service]
User=root
WorkingDirectory=/home/almita/CCP/zktecoMGMT
Environment="PATH=/home/almita/CCP/zktecoMGMT/zkteco_env/bin"
ExecStart=/home/almita/CCP/zktecoMGMT/zkteco_env/bin/gunicorn zkteco_project.wsgi:application --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**Management**:
```bash
sudo systemctl status gunicorn
sudo systemctl restart gunicorn
sudo journalctl -u gunicorn -f
```

### Django-Q2 Service
**File**: `/etc/systemd/system/django-q.service`

```ini
[Unit]
Description=Django-Q2 Worker Cluster
After=network.target postgresql.service

[Service]
User=root
WorkingDirectory=/home/almita/CCP/zktecoMGMT
Environment="PATH=/home/almita/CCP/zktecoMGMT/zkteco_env/bin"
ExecStart=/home/almita/CCP/zktecoMGMT/zkteco_env/bin/python3 manage.py qcluster
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Management**:
```bash
sudo systemctl status django-q
sudo systemctl restart django-q
sudo journalctl -u django-q -f
```

## PostgreSQL Configuration

### Database Authentication
Both subscripts configure pg_hba.conf for md5 authentication:

**Changes made**:
- `host all all 127.0.0.1/32 ident` → `md5`
- `host all all ::1/128 ident` → `md5`
- `local all all peer` → `md5`

**Purpose**: Allows password authentication from Django.

### Database Validation
Both subscripts validate:
1. Database exists and is accessible
2. User exists with correct privileges
3. Password is correct
4. Connection works

### Idempotency
- Can run scripts multiple times safely
- Updates existing resources instead of failing
- Preserves existing data

## Testing Scenarios

### Scenario 1: Fresh System (No PostgreSQL)
```bash
sudo ./deploy.sh
```
**Result**:
- Installs PostgreSQL
- Initializes database (RHEL only)
- Creates database and user
- Configures authentication
- Creates services
- Runs migrations

### Scenario 2: PostgreSQL Exists, No Database
```bash
sudo ./deploy.sh
```
**Result**:
- Skips PostgreSQL installation
- Creates database and user
- Configures authentication
- Creates services
- Runs migrations

### Scenario 3: Everything Exists
```bash
sudo ./deploy.sh
```
**Result**:
- Skips PostgreSQL installation
- Validates database exists
- Updates user password
- Updates pg_hba.conf if needed
- Updates service files
- Runs migrations

### Scenario 4: Re-deployment
```bash
sudo ./deploy.sh
```
**Options**:
- Keep existing venv or recreate
- Updates .env file
- Updates database password
- Updates services
- Runs new migrations

## Troubleshooting

### Check Deployment Logs
```bash
ls -lth logs/
cat logs/deployment_*.log
```

### Service Failures

#### Gunicorn not starting?
```bash
sudo systemctl status gunicorn
sudo journalctl -u gunicorn -n 50

# Check gunicorn binary exists
ls -la /home/almita/CCP/zktecoMGMT/zkteco_env/bin/gunicorn

# Check venv ownership
ls -la /home/almita/CCP/zktecoMGMT/zkteco_env/
```

#### Django-Q2 not starting?
```bash
sudo systemctl status django-q
sudo journalctl -u django-q -n 50

# Check if database is accessible
PGPASSWORD="your_password" psql -h localhost -U kb_db -d zkteco_db -c "SELECT 1;"
```

### Database Connection Issues

#### Authentication failed?
```bash
# Check pg_hba.conf
cat /etc/postgresql/*/main/pg_hba.conf  # Debian
cat /var/lib/pgsql/data/pg_hba.conf     # RHEL

# Verify md5 authentication is set
# Reload PostgreSQL
sudo systemctl reload postgresql
```

#### User doesn't exist?
```bash
sudo -u postgres psql -c "\du"
```

#### Database doesn't exist?
```bash
sudo -u postgres psql -l
```

### Permission Issues

#### Venv owned by root?
```bash
ls -la /home/almita/CCP/zktecoMGMT/
sudo chown -R almita:almita /home/almita/CCP/zktecoMGMT/zkteco_env/
```

#### Staticfiles owned by root?
```bash
ls -la /home/almita/CCP/zktecoMGMT/staticfiles/
sudo chown -R almita:almita /home/almita/CCP/zktecoMGMT/staticfiles/
```

## Files Structure

```
zktecoMGMT/
├── deploy.sh                    # Universal orchestrator
├── deploy_debian.sh             # Debian/Ubuntu specific
├── deploy_rhel.sh               # RHEL/AlmaLinux/Fedora specific
├── gunicorn_ubuntu_example.sh   # Reference (verified approach)
├── logs/                        # Deployment logs
│   └── deployment_*.log
├── zkteco_env/                  # Virtual environment
│   ├── bin/
│   │   ├── python3
│   │   ├── pip
│   │   └── gunicorn
│   └── ...
├── .env                         # Generated configuration
├── manage.py
├── requirements.txt
└── ...
```

## Environment Variables Exported

Available to subscripts:

| Variable | Description | Example |
|----------|-------------|---------|
| RED, GREEN, YELLOW, BLUE, NC | Color codes | `'\033[0;32m'` |
| PROJECT_DIR | Project root directory | `/home/almita/CCP/zktecoMGMT` |
| LOG_FILE | Deployment log file path | `logs/deployment_20251026_143022.log` |
| OS | Operating system ID | `almalinux` |
| OS_FAMILY | OS family (debian/rhel) | `rhel` |
| VENV_PATH | Virtual environment path | `/home/almita/CCP/zktecoMGMT/zkteco_env` |
| DB_NAME | Database name | `zkteco_db` |
| DB_USER | Database user | `kb_db` |
| DB_PASSWORD | Database password | `secret123` |

## Next Steps After Deployment

### 1. Verify Services Running
```bash
sudo systemctl status gunicorn
sudo systemctl status django-q
```

### 2. Access Application
```bash
# Web interface
http://localhost:8000

# Admin panel
http://localhost:8000/admin
```

### 3. Update Employee List Template
Edit `templates/employees/employee_list.html` to use async task system:

**Change from**:
```html
<a href="{% url 'employees:sync_to_device' %}?device={{ device.id }}" class="btn btn-sm btn-primary">
    Sync To Device
</a>
```

**To**:
```html
<button onclick="taskTracker.startTask('/tasks/sync-to-device/{{ device.id }}/', 'Sync To Device')"
        class="btn btn-sm btn-primary">
    <i class="bi bi-cloud-upload"></i> Sync To Device
</button>
```

Similar changes for:
- Sync From Device → `/tasks/sync-from-device/{{ device.id }}/`
- Download Attendance → `/tasks/download-attendance/{{ device.id }}/`

### 4. Test Background Tasks
1. Start Django-Q worker: Already running as service
2. Go to employee list page
3. Click "Sync To Device"
4. Watch the progress bar update in real-time

## Summary of Benefits

### Maintainability
- Clear separation of concerns
- Easy to add new OS families
- Modular and testable

### Reliability
- Comprehensive error handling
- Idempotent operations
- Detailed logging for self-correction

### Security
- Virtual environment isolation
- Proper file ownership
- PostgreSQL authentication configured

### Production Ready
- Systemd services auto-start on boot
- Background task processing with Django-Q2
- Static files properly collected
- Database migrations applied

---

**Status**: ✅ Complete and Production Ready

**Deployment Command**: `sudo ./deploy.sh`

**Log Location**: `logs/deployment_*.log`

**Services Created**:
- Gunicorn (port 8000)
- Django-Q2 (background worker)
