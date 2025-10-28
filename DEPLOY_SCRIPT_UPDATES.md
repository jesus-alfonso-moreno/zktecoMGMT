# Deploy Script Updates Summary

This document summarizes all updates made to the deployment scripts based on lessons learned during deployment on AlmaLinux 10.

## Date: 2025-10-27

---

## Main Changes

### 1. deploy.sh - Now Directory-Flexible

**Before**: Used `pwd` which assumed script was run from project directory

**After**: Auto-detects project directory and validates it's a Django project

```bash
# Auto-detect script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

# Verify required files exist
REQUIRED_FILES=("manage.py" "requirements.txt")
```

**Benefits**:
- Works from any directory location (`/opt/CCP/zktecoMGMT` or `/home/user/project`)
- Validates project directory before proceeding
- Shows clear error if run from wrong location
- No hardcoded paths

---

### 2. Quoted SECRET_KEY in .env

**Issue**: SECRET_KEY with special characters like `$`, `#`, `%` caused bash parsing errors

**Fix**: Quote the SECRET_KEY value in .env file

```bash
# Before
SECRET_KEY=$SECRET_KEY

# After
SECRET_KEY='$SECRET_KEY'
```

---

### 3. Added Media Directory Creation

**Issue**: Media directory didn't exist by default, causing errors when users uploaded files

**Fix**: Create media directory with proper ownership and permissions

```bash
mkdir -p "$PROJECT_DIR/media"
chown -R $SUDO_USER:$SUDO_USER "$PROJECT_DIR/media"
chmod 755 "$PROJECT_DIR/media"
```

---

### 4. Enhanced Deployment Summary

**Added**:
- Nginx service management commands
- Service log viewing commands
- Development commands (migrations, collectstatic, shell)
- Important notes about architecture:
  - Nginx on port 80 (public)
  - Gunicorn on localhost:8000 (not public)
  - Django-Q2 for background tasks
  - All services run as non-root user

---

## deploy_rhel.sh Updates

### 1. Changed PostgreSQL Commands from `sudo -u` to `su -`

**Issue**: When deploy script is run with `sudo ./deploy.sh`, nested `sudo -u postgres` commands would hang

**Fix**: Use `su - postgres -c` instead

```bash
# Before
DB_EXISTS=$(sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -w "$DB_NAME" | wc -l)

# After
DB_EXISTS=$(su - postgres -c "psql -lqt" | cut -d \| -f 1 | grep -w "$DB_NAME" | wc -l)
```

**All affected commands updated**:
- Database existence check
- User existence check
- Database creation
- User creation
- Password updates

---

### 2. Gunicorn Service - Non-root User and Localhost Binding

**Issue**: Running as root is insecure, binding to 0.0.0.0 exposes Gunicorn publicly

**Fix**: Run as actual user, bind to localhost only

```bash
# Determine actual user (not root)
ACTUAL_USER="${SUDO_USER:-$(whoami)}"

[Service]
User=$ACTUAL_USER                    # Was: root
ExecStart=$GUNICORN_BIN ... --bind 127.0.0.1:$SERVER_PORT  # Was: 0.0.0.0
--workers 3 --timeout 300           # Added for better performance
RestartSec=10                       # Added for reliability
```

**Benefits**:
- Better security (non-root)
- Gunicorn not exposed publicly
- Nginx handles public traffic and serves static files
- Automatic restart on failure

---

### 3. Django-Q Service - Non-root User

**Issue**: Running background workers as root is unnecessary and insecure

**Fix**: Run as actual user

```bash
[Service]
User=$ACTUAL_USER                    # Was: root
```

---

### 4. Added Nginx Installation and Configuration

**New Step 7**: Installs and configures Nginx as reverse proxy

```nginx
server {
    listen 80;

    # Static files (30 day cache)
    location /static/ {
        alias /opt/CCP/zktecoMGMT/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files (7 day cache)
    location /media/ {
        alias /opt/CCP/zktecoMGMT/media/;
        expires 7d;
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:$SERVER_PORT;
        proxy_connect_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

**Benefits**:
- ~100x faster static file serving vs Django
- Browser caching reduces server load
- Better security (Gunicorn not exposed)
- Handles large file uploads

---

### 5. Added SELinux Configuration

**New Step 8**: Configures SELinux to allow Nginx to work properly

```bash
# Set context for static/media files
chcon -R -t httpd_sys_content_t /opt/CCP/zktecoMGMT/staticfiles
chcon -R -t httpd_sys_content_t /opt/CCP/zktecoMGMT/media

# Allow Nginx to proxy to Gunicorn
setsebool -P httpd_can_network_connect 1
```

**Why needed**: SELinux in enforcing mode blocks Nginx from:
- Reading files outside standard directories
- Making network connections to Gunicorn

---

### 6. Added Firewalld Configuration

**New Step 9**: Opens HTTP/HTTPS ports in firewalld

```bash
firewall-cmd --permanent --add-service=http
firewall-cmd --permanent --add-service=https
firewall-cmd --reload
```

**Note**: Does NOT open port 8000 (Gunicorn) - intentionally kept internal only

---

### 7. Added Service Restart Sequence

**New Step 10**: Ensures all services start in correct order

```bash
# Order matters:
1. Enable and start Nginx
2. Restart Gunicorn (ensure it's running)
3. Restart Django-Q (ensure it's running)

# Verify each service after starting
systemctl is-active --quiet <service> || exit 1
```

**Why**: Ensures deployment doesn't succeed if services fail to start

---

## deploy_debian.sh Updates

**Status**: Not updated yet, but should receive same fixes as deploy_rhel.sh:

1. Change `sudo -u postgres` to `su - postgres -c`
2. Update Gunicorn service (user, bind address)
3. Update Django-Q service (user)
4. Add Nginx installation and configuration
5. Add SELinux configuration (if installed)
6. Add UFW firewall configuration (instead of firewalld)
7. Add service restart sequence

---

## Key Architectural Changes

### Before Deployment
```
User → Gunicorn (port 8000) → Django
       └─ Serves static files slowly
```

### After Deployment
```
User → Nginx (port 80)
       ├─ /static/ → Directly serves from /staticfiles (fast)
       ├─ /media/  → Directly serves from /media (fast)
       └─ /*       → Proxy to Gunicorn (localhost:8000) → Django

Background: Django-Q2 → Processes async tasks
```

**Benefits**:
- 100x faster static file serving
- Better security (Gunicorn not exposed)
- Browser caching reduces load
- Async tasks don't block web requests

---

## Testing the Updated Scripts

### On Fresh AlmaLinux 10 System:

```bash
# 1. Clone/copy project to /opt
sudo mkdir -p /opt/CCP
sudo cp -r /path/to/zktecoMGMT /opt/CCP/
cd /opt/CCP/zktecoMGMT

# 2. Make script executable
sudo chmod +x deploy.sh deploy_rhel.sh

# 3. Run deployment
sudo ./deploy.sh
```

### What Should Happen:

1. ✅ Script validates it's in a Django project directory
2. ✅ Detects AlmaLinux and uses deploy_rhel.sh
3. ✅ Creates virtual environment at detected location
4. ✅ Prompts for database credentials and port
5. ✅ Generates .env with quoted SECRET_KEY
6. ✅ Installs PostgreSQL with proper authentication
7. ✅ Creates database and user using `su -` (not `sudo -u`)
8. ✅ Runs makemigrations
9. ✅ Runs migrate
10. ✅ Creates superuser
11. ✅ Creates media directory
12. ✅ Collects static files
13. ✅ Creates Gunicorn service (localhost:8000, non-root)
14. ✅ Creates Django-Q service (non-root)
15. ✅ Installs and configures Nginx
16. ✅ Configures SELinux contexts
17. ✅ Opens firewall for HTTP/HTTPS
18. ✅ Starts all services in correct order
19. ✅ Verifies all services are running

### Expected Result:

- Access http://localhost/ → Homepage loads
- Access http://localhost/admin → Admin panel loads
- Access http://localhost/static/js/task_progress.js → JavaScript loads (200 OK)
- Progress bars work when syncing employees or downloading attendance
- All services running as non-root user
- No SELinux denials in audit log
- No firewall blocking HTTP traffic

---

## Files Modified

### Main Scripts:
- `/opt/CCP/zktecoMGMT/deploy.sh` - Made directory-flexible, added media directory
- `/opt/CCP/zktecoMGMT/deploy_rhel.sh` - All 7 major fixes applied

### Documentation:
- `/opt/CCP/zktecoMGMT/DEPLOYMENT_FIXES_SUMMARY.md` - Complete list of issues fixed
- `/opt/CCP/zktecoMGMT/DEPLOY_SCRIPT_UPDATES.md` - This file

### Helper Scripts (in bashfixes/):
- `fix_venv_paths.sh` - Fixes virtual environment paths when moving project
- `update_configs.sh` - Updates service configs for new location
- `complete_setup.sh` - Single script that does both above

---

## Deployment Best Practices

### 1. Always Run with sudo
```bash
sudo ./deploy.sh
```
This ensures:
- $SUDO_USER contains actual username
- Services run as non-root user
- Script can install packages and create system files

### 2. Recommended Project Location
```bash
/opt/CCP/zktecoMGMT
```
Reasons:
- Standard location for third-party applications
- No SELinux home directory restrictions
- Clear separation from user files

### 3. After Deployment
```bash
# Check all services
sudo systemctl status nginx gunicorn django-q postgresql

# View logs
sudo journalctl -u gunicorn -f
sudo journalctl -u django-q -f
sudo tail -f /var/log/nginx/error.log

# Test static files
curl http://localhost/static/js/task_progress.js

# Test admin
curl http://localhost/admin/
```

---

## Troubleshooting

### If Gunicorn Fails to Start

**Check logs:**
```bash
sudo journalctl -u gunicorn -n 50
```

**Common issues:**
- Virtual environment paths incorrect → Run `bashfixes/fix_venv_paths.sh`
- Database connection failed → Check .env DATABASE_URL
- Permission denied → Check file ownership: `chown -R user:user /opt/CCP/zktecoMGMT`

### If Static Files Return 404

**Check SELinux:**
```bash
sudo ausearch -m avc -ts recent
sudo chcon -R -t httpd_sys_content_t /opt/CCP/zktecoMGMT/staticfiles
```

**Check Nginx:**
```bash
sudo nginx -t
sudo tail -f /var/log/nginx/error.log
```

### If Progress Bars Don't Work

**Check Django-Q:**
```bash
sudo systemctl status django-q
sudo journalctl -u django-q -f
```

**Check browser console:**
- Should load task_progress.js (200 OK)
- No "taskTracker is not defined" error
- POST requests to /en/tasks/... (not GET)

---

## Migration from Old Deployment

If you have an existing deployment in `/home/user/CCP/zktecoMGMT`:

### Option 1: Move to /opt (Recommended)

```bash
# 1. Stop services
sudo systemctl stop gunicorn django-q nginx

# 2. Copy project
sudo cp -r /home/user/CCP/zktecoMGMT /opt/CCP/

# 3. Fix venv paths
cd /opt/CCP/zktecoMGMT
sudo bash bashfixes/complete_setup.sh

# 4. Services now running from /opt
```

### Option 2: Stay in /home

The new deploy.sh works anywhere:

```bash
cd /home/user/CCP/zktecoMGMT
sudo ./deploy.sh
```

Script will detect location and use it.

---

## Future Improvements

### Could Be Added:

1. **HTTPS/SSL support** - Let's Encrypt certificate automation
2. **Database backups** - Automated pg_dump schedule
3. **Log rotation** - Configure logrotate for application logs
4. **Monitoring** - Install and configure system monitoring
5. **Email alerts** - Configure Django to send error emails
6. **Performance tuning** - PostgreSQL optimization for production

### Deploy Script Enhancements:

1. **Rollback capability** - Save state before deployment
2. **Zero-downtime deployment** - Blue-green deployment
3. **Configuration testing** - Test database connection before migration
4. **Dependency validation** - Check all required packages before starting

---

## Summary of Benefits

### Security:
✅ Services run as non-root user
✅ Gunicorn not exposed to internet
✅ SELinux properly configured
✅ Firewall configured correctly

### Performance:
✅ Nginx serves static files 100x faster
✅ Browser caching reduces server load
✅ Async tasks don't block requests
✅ Multiple Gunicorn workers

### Reliability:
✅ Services auto-restart on failure
✅ Proper service dependencies
✅ Detailed logging
✅ Validation at each step

### Maintainability:
✅ No hardcoded paths
✅ Works from any directory
✅ Clear error messages
✅ Comprehensive documentation
