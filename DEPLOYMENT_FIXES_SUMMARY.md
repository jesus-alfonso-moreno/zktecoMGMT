# Deployment Fixes Summary

This document summarizes all the fixes that need to be incorporated into the deployment scripts.

## Issues Fixed During Session (2025-10-26)

### 1. **Project Location**
- **Issue**: Project was in `/home/almita/CCP/zktecoMGMT`
- **Fix**: Moved to `/opt/CCP/zktecoMGMT`
- **Reason**: Better security, no SELinux home directory issues, industry standard

### 2. **Virtual Environment Hardcoded Paths**
- **Issue**: When copying project to `/opt`, venv had hardcoded shebangs pointing to old location
- **Fix**: All Python script shebangs and activate scripts need path updates
- **Files affected**:
  - `zkteco_env/bin/*` - All Python scripts (gunicorn, django-admin, pip, etc.)
  - `zkteco_env/bin/activate*` - All activation scripts
  - `zkteco_env/pyvenv.cfg`

### 3. **Nginx Configuration**
- **Issue**: Static files not being served
- **Fix**: Nginx must be configured to serve static/media files
- **Configuration**:
  ```nginx
  location /static/ {
      alias /opt/CCP/zktecoMGMT/staticfiles/;
      expires 30d;
      add_header Cache-Control "public, immutable";
  }

  location /media/ {
      alias /opt/CCP/zktecoMGMT/media/;
      expires 7d;
  }
  ```

### 4. **SELinux Context for Nginx**
- **Issue**: SELinux blocking Nginx from reading static files in `/opt`
- **Fix**: Set proper SELinux contexts
  ```bash
  chcon -R -t httpd_sys_content_t /opt/CCP/zktecoMGMT/staticfiles
  chcon -R -t httpd_sys_content_t /opt/CCP/zktecoMGMT/media
  setsebool -P httpd_can_network_connect 1
  ```

### 5. **Gunicorn Service Configuration**
- **Issue**: Service user and paths
- **Fix**:
  - User: `almita` (not `root`)
  - WorkingDirectory: `/opt/CCP/zktecoMGMT`
  - Bind: `127.0.0.1:8000` (localhost only, Nginx proxies)
  - Environment PATH: `/opt/CCP/zktecoMGMT/zkteco_env/bin`
  - ExecStart: `/opt/CCP/zktecoMGMT/zkteco_env/bin/gunicorn`

### 6. **Django-Q2 Service Configuration**
- **Issue**: Same as Gunicorn
- **Fix**:
  - User: `almita` (not `root`)
  - WorkingDirectory: `/opt/CCP/zktecoMGMT`
  - Environment PATH: `/opt/CCP/zktecoMGMT/zkteco_env/bin`
  - ExecStart: `/opt/CCP/zktecoMGMT/zkteco_env/bin/python manage.py qcluster`

### 7. **Static Files Collection**
- **Issue**: Static files must be collected after deployment
- **Fix**: Run `python manage.py collectstatic --noinput` after migrations

### 8. **Firewall Configuration**
- **Issue**: Port 80/443 not open for Nginx
- **Fix**:
  - Open HTTP (80) and HTTPS (443)
  - Keep SSH (22) open
  - Gunicorn port (8000) should NOT be public (localhost only)

### 9. **.env File Configuration**
- **Issue**: SECRET_KEY with special characters causing bash parsing errors
- **Fix**: Quote the SECRET_KEY value
  ```bash
  SECRET_KEY='$f^%bk)#*h_1(cn&6lexmpc+r64$5^pcyiz^rl5z#fop5t14%n'
  ```
- **Required variables**:
  ```
  DEBUG=False
  SECRET_KEY='...'
  ALLOWED_HOSTS=localhost,127.0.0.1
  ZK_TEST_MODE=False
  DATABASE_URL=postgresql://user:pass@localhost/dbname
  SERVER_PORT=8000
  ```

### 10. **PostgreSQL Authentication**
- **Issue**: Nested sudo hanging, wrong authentication method
- **Fix**:
  - Use `su - postgres -c` instead of `sudo -u postgres`
  - pg_hba.conf: `peer` for postgres user, `md5` for application users

### 11. **Media Directory**
- **Issue**: Media directory doesn't exist by default
- **Fix**: Create during deployment
  ```bash
  mkdir -p /opt/CCP/zktecoMGMT/media
  chmod 755 /opt/CCP/zktecoMGMT/media
  ```

### 12. **Service Restart Order**
- **Issue**: Services start before all configuration is complete
- **Fix**: Proper order:
  1. Stop all services
  2. Configure everything
  3. Reload systemd daemon
  4. Start gunicorn
  5. Wait and verify
  6. Start django-q
  7. Wait and verify
  8. Start nginx
  9. Verify all running

### 13. **Ownership and Permissions**
- **Issue**: Files owned by root causing permission issues
- **Fix**:
  ```bash
  chown -R almita:almita /opt/CCP/zktecoMGMT
  chmod -R 755 /opt/CCP/zktecoMGMT/staticfiles
  chmod -R 755 /opt/CCP/zktecoMGMT/media
  ```

## Changes Needed in Deploy Scripts

### deploy.sh (Main Script)

**Add/Update:**
1. Change project directory to `/opt/CCP/zktecoMGMT` instead of user home
2. Quote SECRET_KEY when writing to .env
3. Add SERVER_PORT to .env file
4. Create media directory
5. Run collectstatic after migrations
6. Add proper service restart sequence with verification
7. Better error handling with detailed logging
8. Add SELinux configuration for Nginx

**Remove:**
- Any hardcoded paths to `/home/almita`

### deploy_rhel.sh

**Update:**
1. All `sudo -u postgres` to `su - postgres -c`
2. Gunicorn service:
   - User: `almita`
   - WorkingDirectory: `/opt/CCP/zktecoMGMT`
   - Bind: `127.0.0.1:$SERVER_PORT`
3. Django-Q service:
   - User: `almita`
   - WorkingDirectory: `/opt/CCP/zktecoMGMT`
4. Add SELinux context configuration
5. Add firewall configuration (firewalld for RHEL)

### deploy_debian.sh

**Update:**
1. All `sudo -u postgres` to `su - postgres -c`
2. Same service configuration changes as deploy_rhel.sh
3. Add SELinux context configuration (if SELinux installed)
4. Add firewall configuration (UFW for Debian/Ubuntu)

## New Deployment Flow

```
1. OS Detection
2. Virtual Environment Setup (in /opt/CCP/zktecoMGMT)
3. User Input Collection (including SERVER_PORT)
4. Install Python Dependencies
5. Generate .env file (with quoted SECRET_KEY, SERVER_PORT)
6. Install PostgreSQL
7. Configure PostgreSQL (pg_hba.conf with correct auth)
8. Create Database and User (using su - postgres -c)
9. Create media directory
10. Run makemigrations
11. Run migrate
12. Run collectstatic
13. Create superuser
14. Configure Gunicorn service (user: almita, localhost bind)
15. Configure Django-Q service (user: almita)
16. Configure Nginx (static/media serving, proxy to localhost:8000)
17. Set SELinux contexts
18. Configure Firewall (HTTP/HTTPS, not 8000)
19. Reload systemd daemon
20. Start and verify gunicorn
21. Start and verify django-q
22. Start and verify nginx
23. Test static file access
24. Display completion summary
```

## Testing Checklist

After deployment, verify:
- [ ] All services running: `systemctl status nginx gunicorn django-q postgresql`
- [ ] Static files accessible: `curl http://localhost/static/js/task_progress.js`
- [ ] Main page loads: `curl http://localhost/`
- [ ] Admin page loads: `curl http://localhost/en/admin/`
- [ ] Django-Q processing tasks: Check journalctl logs
- [ ] Progress bar works: Try sync/download operations
- [ ] No 404 errors in browser console
- [ ] No permission denied in Nginx logs

## Files Modified

### Configuration Files:
- `/etc/systemd/system/gunicorn.service`
- `/etc/systemd/system/django-q.service`
- `/etc/nginx/conf.d/zkteco.conf`
- `/opt/CCP/zktecoMGMT/.env`

### Application Files:
- `/opt/CCP/zktecoMGMT/templates/base.html` (static file versioning)
- `/opt/CCP/zktecoMGMT/static/js/task_progress.js` (better error handling)
- `/opt/CCP/zktecoMGMT/templates/employees/employee_list.html` (URL fix)
- `/opt/CCP/zktecoMGMT/templates/attendance/attendance_list.html` (URL fix)

### SELinux:
- Static files context: `httpd_sys_content_t`
- Network connect: `httpd_can_network_connect=1`

## Key Lessons

1. **Never hardcode paths in virtual environments** - They break when moving
2. **Always use localhost binding for backend services** - Use reverse proxy
3. **SELinux matters** - Set proper contexts for web-accessible files
4. **Test with actual browser** - Not just curl
5. **Use Django's {% url %} tags** - Handles language prefixes automatically
6. **Quote special characters in .env** - Bash parsing issues
7. **Use su instead of sudo for PostgreSQL** - Avoids nested sudo issues
8. **Collect static files** - Django doesn't serve them in production
9. **Log everything** - Makes debugging much easier
10. **Verify each step** - Don't assume services started successfully

## Performance Notes

- Nginx serves static files ~100x faster than Django
- Gunicorn on localhost only improves security
- Django-Q2 prevents request timeouts for long operations
- Browser caching (30 days) reduces server load

## Security Improvements

1. Gunicorn not exposed to public (localhost only)
2. Nginx as security layer
3. SELinux enforcing proper file access
4. Services run as non-root user (almita)
5. Firewall only allows necessary ports
