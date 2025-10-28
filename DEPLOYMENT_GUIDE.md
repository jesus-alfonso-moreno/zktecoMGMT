# ZKTeco Management System - Deployment Guide

Quick reference for deploying the ZKTeco Management System on AlmaLinux 10, RHEL, or Debian/Ubuntu.

## Prerequisites

- Fresh installation of AlmaLinux 10, RHEL 9+, or Ubuntu 22.04+
- Root or sudo access
- Internet connection for package downloads
- At least 2GB RAM, 10GB disk space

## Quick Start Deployment

### 1. Get the Project Files

```bash
# Clone or copy project to /opt/CCP
sudo mkdir -p /opt/CCP
sudo cp -r /path/to/zktecoMGMT /opt/CCP/
cd /opt/CCP/zktecoMGMT
```

### 2. Run Deployment Script

```bash
# Make script executable
sudo chmod +x deploy.sh

# Run deployment (use sudo!)
sudo ./deploy.sh
```

### 3. Follow Prompts

The script will ask you for:

1. **Virtual environment name** (default: `zkteco_env`)
2. **Database name** (default: `zkteco_db`)
3. **Database user** (default: `kb_db`)
4. **Database password** (required - choose a strong password)
5. **Allowed hosts** (default: `localhost,127.0.0.1`)
6. **Server port** (default: `8000` - Gunicorn internal port)
7. **Test mode** (default: `n` for production)
8. **Admin username, email, password** (for Django superuser)

### 4. Wait for Completion

The deployment process takes 5-15 minutes depending on your system. It will:

- Install Python packages and dependencies
- Install and configure PostgreSQL
- Create database and user
- Run Django migrations
- Create superuser account
- Collect static files
- Install and configure Nginx
- Configure SELinux (if enabled)
- Configure firewall
- Start all services

### 5. Access Your Application

Once complete, access the application at:

- **Main application**: http://localhost/ or http://your-server-ip/
- **Admin panel**: http://localhost/admin/ or http://your-server-ip/admin/

## Post-Deployment Verification

### Check All Services

```bash
sudo systemctl status nginx gunicorn django-q postgresql
```

All services should show **active (running)** in green.

### Test Static Files

```bash
curl -I http://localhost/static/js/task_progress.js
```

Should return `HTTP/1.1 200 OK`

### Test Application

```bash
curl -I http://localhost/
```

Should return `HTTP/1.1 200 OK` or `HTTP/1.1 302 Found` (redirect)

### Check Logs

```bash
# Gunicorn logs
sudo journalctl -u gunicorn -n 50

# Django-Q logs
sudo journalctl -u django-q -n 50

# Nginx error log
sudo tail -f /var/log/nginx/error.log
```

No errors should be present.

## Common Management Tasks

### Restart Services

```bash
# Restart all services
sudo systemctl restart nginx gunicorn django-q

# Or individually
sudo systemctl restart nginx
sudo systemctl restart gunicorn
sudo systemctl restart django-q
```

### View Live Logs

```bash
# Follow Gunicorn logs
sudo journalctl -u gunicorn -f

# Follow Django-Q logs
sudo journalctl -u django-q -f

# Follow Nginx error log
sudo tail -f /var/log/nginx/error.log
```

### Update Application Code

```bash
cd /opt/CCP/zktecoMGMT

# Activate virtual environment
source zkteco_env/bin/activate

# Pull latest code (if using git)
git pull

# Install any new dependencies
pip install -r requirements.txt

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Restart services
sudo systemctl restart gunicorn django-q
```

### Create Additional Admin Users

```bash
cd /opt/CCP/zktecoMGMT
source zkteco_env/bin/activate
python manage.py createsuperuser
```

### Backup Database

```bash
# Create backup
sudo -u postgres pg_dump zkteco_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from backup
sudo -u postgres psql zkteco_db < backup_20251027_120000.sql
```

## Troubleshooting

### Issue: Gunicorn Service Failed

**Symptoms**: `sudo systemctl status gunicorn` shows failed or inactive

**Solution**:
```bash
# Check detailed error
sudo journalctl -u gunicorn -n 100

# Common fixes:
# 1. Database connection issue
nano /opt/CCP/zktecoMGMT/.env  # Check DATABASE_URL

# 2. Virtual environment paths
cd /opt/CCP/zktecoMGMT
sudo bash bashfixes/fix_venv_paths.sh

# 3. Permission issues
sudo chown -R almita:almita /opt/CCP/zktecoMGMT

# Restart
sudo systemctl restart gunicorn
```

### Issue: Static Files Return 404

**Symptoms**: CSS/JS not loading, browser console shows 404 errors

**Solution**:
```bash
# 1. Check static files exist
ls -la /opt/CCP/zktecoMGMT/staticfiles/

# If missing, collect them:
cd /opt/CCP/zktecoMGMT
source zkteco_env/bin/activate
python manage.py collectstatic --noinput

# 2. Fix SELinux context (AlmaLinux/RHEL)
sudo chcon -R -t httpd_sys_content_t /opt/CCP/zktecoMGMT/staticfiles
sudo chcon -R -t httpd_sys_content_t /opt/CCP/zktecoMGMT/media

# 3. Check Nginx configuration
sudo nginx -t
sudo systemctl restart nginx
```

### Issue: Progress Bars Don't Appear

**Symptoms**: Employee sync or attendance download doesn't show progress

**Solution**:
```bash
# 1. Check Django-Q is running
sudo systemctl status django-q

# If not running:
sudo systemctl restart django-q

# 2. Check browser console (F12)
# Should not see "taskTracker is not defined"
# Should see POST requests to /en/tasks/...

# 3. Clear browser cache
# Press Ctrl+Shift+R or Cmd+Shift+R
```

### Issue: Can't Access from Other Computers

**Symptoms**: Works on server (localhost) but not from other computers

**Solution**:
```bash
# 1. Check firewall allows HTTP
sudo firewall-cmd --list-all  # RHEL/AlmaLinux
sudo ufw status              # Debian/Ubuntu

# Open HTTP if needed:
sudo firewall-cmd --permanent --add-service=http  # RHEL
sudo firewall-cmd --reload
# OR
sudo ufw allow 80/tcp  # Debian/Ubuntu

# 2. Update ALLOWED_HOSTS in .env
nano /opt/CCP/zktecoMGMT/.env
# Add: ALLOWED_HOSTS=localhost,127.0.0.1,your-server-ip,your-domain.com

# 3. Restart Gunicorn
sudo systemctl restart gunicorn
```

### Issue: Database Connection Failed

**Symptoms**: "FATAL: password authentication failed"

**Solution**:
```bash
# 1. Test database connection manually
PGPASSWORD='your-password' psql -h localhost -U kb_db -d zkteco_db

# 2. If fails, check pg_hba.conf
sudo cat /var/lib/pgsql/data/pg_hba.conf  # RHEL
sudo cat /etc/postgresql/*/main/pg_hba.conf  # Debian

# Should have these lines:
# local   all             postgres                                peer
# local   all             all                                     md5
# host    all             all             127.0.0.1/32            md5

# 3. Fix if needed and reload
sudo systemctl reload postgresql

# 4. Recreate user password
sudo su - postgres
psql
ALTER USER kb_db WITH PASSWORD 'your-new-password';
\q
exit

# Update .env with new password
nano /opt/CCP/zktecoMGMT/.env
```

### Issue: SELinux Blocking Access

**Symptoms**: Permission denied errors in logs, AVC denials

**Solution**:
```bash
# 1. Check for SELinux denials
sudo ausearch -m avc -ts recent

# 2. Fix contexts
sudo chcon -R -t httpd_sys_content_t /opt/CCP/zktecoMGMT/staticfiles
sudo chcon -R -t httpd_sys_content_t /opt/CCP/zktecoMGMT/media
sudo setsebool -P httpd_can_network_connect 1

# 3. Restart services
sudo systemctl restart nginx gunicorn
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                            Internet                              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                     Port 80 (HTTP)
                            │
                    ┌───────▼───────┐
                    │     Nginx     │ Serves static/media files
                    │   (Port 80)   │ Reverse proxy to Gunicorn
                    └───┬───────┬───┘
                        │       │
                /static │       │ /*
                /media  │       │
                        │       │ Proxy
                        │   ┌───▼─────────────┐
                        │   │   Gunicorn      │
                        │   │ (localhost:8000)│
                        │   └────────┬────────┘
                        │            │
                        │    ┌───────▼─────────┐
                        │    │  Django App     │
                        │    │  (zkteco_mgmt)  │
                        │    └────┬───────┬────┘
                        │         │       │
                        │         │   ┌───▼──────────┐
                        │         │   │  Django-Q2   │
                        │         │   │ (Background) │
                        │         │   └───┬──────────┘
                        │         │       │
                        │    ┌────▼───────▼────┐
                        │    │   PostgreSQL    │
                        │    │   (Database)    │
                        │    └─────────────────┘
                        │
                   ┌────▼────────────┐
                   │  Static Files   │
                   │ (CSS/JS/Images) │
                   └─────────────────┘
```

**Key Points**:
- Nginx handles all public traffic on port 80
- Gunicorn runs on localhost:8000 (NOT exposed to internet)
- Django-Q2 processes background tasks (employee sync, attendance download)
- All services run as non-root user (almita)
- Static files served directly by Nginx (fast)

## Service Details

### Nginx
- **Purpose**: Web server and reverse proxy
- **Config**: `/etc/nginx/conf.d/zkteco.conf`
- **Logs**: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`
- **Port**: 80 (public)

### Gunicorn
- **Purpose**: WSGI server for Django
- **Config**: `/etc/systemd/system/gunicorn.service`
- **Logs**: `sudo journalctl -u gunicorn`
- **Port**: localhost:8000 (internal only)
- **Workers**: 3

### Django-Q2
- **Purpose**: Background task queue
- **Config**: `/etc/systemd/system/django-q.service`
- **Logs**: `sudo journalctl -u django-q`
- **Used for**: Employee sync, attendance download (shows progress bars)

### PostgreSQL
- **Purpose**: Database
- **Config**: `/var/lib/pgsql/data/postgresql.conf` (RHEL)
- **Logs**: `sudo journalctl -u postgresql`
- **Port**: 5432 (localhost only)

## Security Checklist

- [ ] All services running as non-root user
- [ ] Gunicorn bound to localhost only (not 0.0.0.0)
- [ ] Firewall allows only HTTP/HTTPS (ports 80/443)
- [ ] PostgreSQL allows only localhost connections
- [ ] DEBUG=False in .env file
- [ ] Strong SECRET_KEY generated
- [ ] Strong database password set
- [ ] SELinux in enforcing mode (RHEL/AlmaLinux)
- [ ] Regular database backups scheduled
- [ ] SSL/HTTPS configured (if using domain name)

## Performance Tuning

### For Production Use:

1. **Increase Gunicorn workers** (CPU cores * 2 + 1):
   ```bash
   sudo nano /etc/systemd/system/gunicorn.service
   # Change: --workers 3  to  --workers 9 (for 4-core CPU)
   sudo systemctl daemon-reload
   sudo systemctl restart gunicorn
   ```

2. **Configure PostgreSQL for production**:
   ```bash
   sudo nano /var/lib/pgsql/data/postgresql.conf
   # Set based on your RAM:
   shared_buffers = 256MB           # 25% of RAM
   effective_cache_size = 1GB       # 50% of RAM
   work_mem = 16MB
   maintenance_work_mem = 128MB

   sudo systemctl restart postgresql
   ```

3. **Enable gzip compression in Nginx**:
   ```bash
   sudo nano /etc/nginx/nginx.conf
   # Add in http block:
   gzip on;
   gzip_types text/plain text/css application/json application/javascript;

   sudo systemctl reload nginx
   ```

## Getting Help

### View All Documentation

```bash
cd /opt/CCP/zktecoMGMT
ls -la *.md
```

Available documentation:
- `README.md` - Project overview and features
- `QUICKSTART.md` - 5-minute quick start guide
- `CLAUDE.md` - Development guidance
- `DEPLOYMENT_FIXES_SUMMARY.md` - All fixes applied during deployment
- `DEPLOY_SCRIPT_UPDATES.md` - Detailed script changes
- `DEPLOYMENT_GUIDE.md` - This file

### Check Service Status

```bash
# Quick check of all services
sudo systemctl status nginx gunicorn django-q postgresql | grep -E "Active:|Loaded:"

# Or individually with full details
sudo systemctl status nginx
sudo systemctl status gunicorn
sudo systemctl status django-q
sudo systemctl status postgresql
```

### Log Locations

```bash
# Application logs
/opt/CCP/zktecoMGMT/logs/deployment_*.log  # Deployment logs

# System logs
sudo journalctl -u gunicorn -n 100         # Last 100 Gunicorn logs
sudo journalctl -u django-q -n 100         # Last 100 Django-Q logs
sudo tail -100 /var/log/nginx/error.log    # Last 100 Nginx errors
sudo tail -100 /var/log/nginx/access.log   # Last 100 Nginx access
```

---

**Last Updated**: 2025-10-27
**For Support**: Check project documentation or review system logs
