# Nginx Setup for ZKTeco Management System

## Overview

This document explains the Nginx setup for the ZKTeco Management System, which uses Nginx as a reverse proxy for Gunicorn and to serve static/media files.

## Architecture

```
Client Browser
    ↓
Nginx :80 (0.0.0.0)
    ↓
    ├─→ /static/* → staticfiles/ (served directly by Nginx)
    ├─→ /media/*  → media/ (served directly by Nginx)
    └─→ /*        → Gunicorn :8000 (127.0.0.1 only)
                      ↓
                    Django Application
                      ↓
                    PostgreSQL Database
```

## Components

### 1. Nginx
- **Role**: Reverse proxy and static file server
- **Listens on**: 0.0.0.0:80 (public)
- **Configuration**: `/etc/nginx/conf.d/zkteco.conf`
- **Serves**:
  - Static files from `/home/almita/CCP/zktecoMGMT/staticfiles/`
  - Media files from `/home/almita/CCP/zktecoMGMT/media/`
  - Proxies dynamic requests to Gunicorn

### 2. Gunicorn
- **Role**: WSGI HTTP server for Django
- **Listens on**: 127.0.0.1:8000 (localhost only - security improvement)
- **Service**: `/etc/systemd/system/gunicorn.service`
- **Workers**: Handles Django application requests

### 3. Django-Q2
- **Role**: Background task processing
- **Service**: `/etc/systemd/system/django-q.service`
- **Purpose**: Processes async tasks (device sync, attendance download)

### 4. PostgreSQL
- **Role**: Database server
- **Database**: zkteco_db
- **User**: kb_db

## Installation

Run the setup script:

```bash
cd /home/almita/CCP/zktecoMGMT
sudo ./setup_nginx.sh
```

The script will:
1. Install Nginx
2. Create Nginx configuration
3. Set proper file permissions
4. Configure SELinux (if enabled)
5. Configure firewall (firewalld or UFW)
6. Start and enable Nginx
7. Update Gunicorn to listen on localhost only
8. Test the setup

## Configuration Details

### Nginx Configuration (`/etc/nginx/conf.d/zkteco.conf`)

**Upstream Definition**:
```nginx
upstream gunicorn_zkteco {
    server 127.0.0.1:8000 fail_timeout=0;
}
```

**Server Block**:
- **Listen**: Port 80 (IPv4 and IPv6)
- **Server Name**: From ALLOWED_HOSTS in .env
- **Max Upload Size**: 4GB

**Static Files**:
```nginx
location /static/ {
    alias /home/almita/CCP/zktecoMGMT/staticfiles/;
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```
- **Cache**: 30 days with immutable flag
- **Direct serving**: Nginx serves files directly (fast)

**Media Files**:
```nginx
location /media/ {
    alias /home/almita/CCP/zktecoMGMT/media/;
    expires 7d;
}
```

**Proxy Settings**:
```nginx
location / {
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Host $http_host;
    proxy_redirect off;

    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;

    proxy_pass http://gunicorn_zkteco;
}
```
- **Timeouts**: 5 minutes (300s) for long-running device operations
- **Headers**: Preserves client information for Django

## SELinux Configuration

If SELinux is enabled, the setup script configures:

1. **Static/Media File Context**:
```bash
chcon -R -t httpd_sys_content_t /home/almita/CCP/zktecoMGMT/staticfiles
chcon -R -t httpd_sys_content_t /home/almita/CCP/zktecoMGMT/media
```

2. **Network Connection Permission**:
```bash
setsebool -P httpd_can_network_connect 1
```

This allows Nginx to:
- Read static/media files
- Connect to Gunicorn backend

## Firewall Configuration

### AlmaLinux (firewalld)
```bash
firewall-cmd --permanent --add-service=http
firewall-cmd --permanent --add-service=https
firewall-cmd --reload
```

### Ubuntu/Debian (UFW)
```bash
ufw allow 'Nginx Full'
```

## Security Improvements

### 1. Gunicorn Localhost Binding
- **Before**: `--bind 0.0.0.0:8000` (accessible from network)
- **After**: `--bind 127.0.0.1:8000` (localhost only)
- **Benefit**: Gunicorn only accessible through Nginx, not directly

### 2. File Permissions
- **Static files**: 755 (read/execute for all, write for owner)
- **Media files**: 755 (same)
- **Benefit**: Nginx can read, but files are protected

### 3. Proxy Headers
- `X-Forwarded-For`: Real client IP preserved
- `X-Forwarded-Proto`: Protocol (http/https) preserved
- **Benefit**: Django sees real client information for logging/security

## Accessing the Application

### Before Nginx Setup
- Direct Gunicorn: `http://localhost:8000`
- Required: Port 8000 open in firewall

### After Nginx Setup
- Through Nginx: `http://localhost/` or `http://your-server-ip/`
- Standard HTTP port: 80
- Gunicorn: Not accessible from outside (security)

## Logs

### Nginx Logs
- **Access log**: `/var/log/nginx/zkteco_access.log`
- **Error log**: `/var/log/nginx/zkteco_error.log`

```bash
# View access log (real-time)
sudo tail -f /var/log/nginx/zkteco_access.log

# View error log (real-time)
sudo tail -f /var/log/nginx/zkteco_error.log
```

### Application Logs
```bash
# Gunicorn logs
sudo journalctl -u gunicorn -f

# Django-Q logs
sudo journalctl -u django-q -f
```

## Common Commands

### Service Management
```bash
# Restart Nginx
sudo systemctl restart nginx

# Reload Nginx (graceful - no downtime)
sudo systemctl reload nginx

# Check Nginx status
sudo systemctl status nginx

# Test Nginx configuration
sudo nginx -t
```

### Troubleshooting
```bash
# Check if all services are running
sudo systemctl status nginx gunicorn django-q postgresql

# Check Nginx configuration syntax
sudo nginx -t

# View recent Nginx errors
sudo tail -50 /var/log/nginx/zkteco_error.log

# Check SELinux denials
sudo ausearch -m avc -ts recent

# Test static file access
curl -I http://localhost/static/js/task_progress.js

# Test application access
curl -I http://localhost/
```

## File Structure

```
/home/almita/CCP/zktecoMGMT/
├── staticfiles/          # Static files (served by Nginx)
│   ├── admin/           # Django admin static files
│   ├── css/             # Custom CSS
│   └── js/              # JavaScript files (including task_progress.js)
├── media/               # User-uploaded files (served by Nginx)
├── static/              # Source static files (collected to staticfiles/)
└── templates/           # Django templates

/etc/nginx/
└── conf.d/
    └── zkteco.conf      # Nginx configuration for this app

/etc/systemd/system/
├── gunicorn.service     # Gunicorn systemd service
└── django-q.service     # Django-Q2 systemd service
```

## Performance Benefits

### Static File Serving
- **Nginx**: ~10,000-20,000 requests/second
- **Gunicorn/Django**: ~100-500 requests/second
- **Improvement**: 20-200x faster for static files

### Caching
- Static files: 30-day browser cache
- Media files: 7-day browser cache
- Reduces server load and improves user experience

### Connection Handling
- Nginx handles slow clients
- Keeps Gunicorn workers free for application logic
- Better resource utilization

## Updating Static Files

After making changes to static files:

```bash
cd /home/almita/CCP/zktecoMGMT
source zkteco_env/bin/activate
python manage.py collectstatic --noinput
```

Nginx will immediately serve the updated files (no restart needed).

## Adding HTTPS/SSL (Future Enhancement)

To add SSL/TLS encryption:

1. **Install Certbot** (Let's Encrypt):
```bash
sudo dnf install -y certbot python3-certbot-nginx
```

2. **Obtain Certificate**:
```bash
sudo certbot --nginx -d your-domain.com
```

3. **Auto-renewal** (Certbot sets this up automatically):
```bash
sudo certbot renew --dry-run
```

## Monitoring

### Check Service Health
```bash
# All services status
systemctl is-active nginx gunicorn django-q postgresql

# Detailed status
sudo systemctl status nginx --no-pager
sudo systemctl status gunicorn --no-pager
sudo systemctl status django-q --no-pager
```

### Performance Monitoring
```bash
# Nginx connections
curl http://localhost/nginx_status  # (requires stub_status module)

# System resources
htop
```

## Backup Configuration

Before making changes, backup Nginx config:

```bash
sudo cp /etc/nginx/conf.d/zkteco.conf /etc/nginx/conf.d/zkteco.conf.backup.$(date +%Y%m%d_%H%M%S)
```

## Rollback

To revert to direct Gunicorn access:

1. Stop Nginx:
```bash
sudo systemctl stop nginx
sudo systemctl disable nginx
```

2. Update Gunicorn to listen on all interfaces:
```bash
sudo sed -i 's/127.0.0.1:8000/0.0.0.0:8000/' /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
```

3. Open port 8000 in firewall:
```bash
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

## Summary

**What Nginx Does**:
✅ Serves static files (CSS, JavaScript, images) very fast
✅ Serves media files (uploads)
✅ Acts as reverse proxy to Gunicorn
✅ Provides security layer
✅ Handles slow clients efficiently
✅ Enables easy SSL/TLS setup in future

**What Gunicorn Does**:
✅ Runs Django application
✅ Processes dynamic requests
✅ Communicates with database
✅ Only accessible via Nginx (security)

**Result**:
🚀 Faster static file delivery
🔒 Better security (Gunicorn not exposed)
📈 Better resource utilization
🎯 Production-ready setup
