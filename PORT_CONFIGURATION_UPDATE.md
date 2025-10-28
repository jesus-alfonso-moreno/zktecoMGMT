# Port Configuration Update - Summary

## Date: 2025-10-27

## Overview

Updated deployment scripts to ask for **two separate ports**:
1. **Nginx Port** (public-facing) - Default: 80
2. **Gunicorn Port** (internal) - Default: 8000

This change allows users to deploy on custom ports and properly configures Nginx and firewall accordingly.

---

## Problem Addressed

### Previous Behavior:
- Script asked for "Enter server port [8000]"
- Ambiguous - users didn't know if this was public or internal port
- Nginx was hardcoded to port 80
- Firewall always opened port 80/443, regardless of actual configuration
- No way to deploy on custom ports (e.g., 8080, 3000)

### New Behavior:
- Script clearly asks for **Nginx public port** (with explanation)
- Script asks for **Gunicorn internal port** separately
- Nginx configured to listen on user-specified port
- Firewall opens the correct port (standard or custom)
- Full flexibility for deployment scenarios

---

## Changes Made

### 1. Updated Port Prompts in deploy.sh

**New Section** (lines 226-244):

```bash
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
```

**Benefits**:
- Clear explanation of what each port is for
- Separate variables for clarity
- Backward compatibility maintained via `SERVER_PORT`

---

### 2. Updated Nginx Configuration in deploy_rhel.sh

**Before**:
```nginx
server {
    listen 80;
    # ...
    location / {
        proxy_pass http://127.0.0.1:$SERVER_PORT;
    }
}
```

**After**:
```nginx
server {
    listen $NGINX_PORT;
    # ...
    location / {
        proxy_pass http://127.0.0.1:$GUNICORN_PORT;
    }
}
```

**Impact**:
- Nginx listens on user-specified public port
- Proxies to user-specified Gunicorn port
- Works with any port combination

---

### 3. Updated Firewall Configuration in deploy_rhel.sh

**New Logic**:

```bash
# Handle standard ports (80/443) vs custom ports
if [ "$NGINX_PORT" -eq 80 ] || [ "$NGINX_PORT" -eq 443 ]; then
    # Use service names (http/https)
    if [ "$NGINX_PORT" -eq 80 ]; then
        firewall-cmd --permanent --add-service=http
    fi
    if [ "$NGINX_PORT" -eq 443 ]; then
        firewall-cmd --permanent --add-service=https
    fi
else
    # Use port number
    firewall-cmd --permanent --add-port=$NGINX_PORT/tcp
fi
```

**Benefits**:
- Standard ports (80/443) use service names (cleaner)
- Custom ports use explicit port numbers
- Firewall opens exactly what's needed
- No unnecessary ports opened

---

### 4. Updated Deployment Summary in deploy.sh

**Configuration Summary**:
```
Configuration Summary:
  Project Directory: /opt/CCP/zktecoMGMT
  Virtual Environment: /opt/CCP/zktecoMGMT/zkteco_env
  Database: zkteco_db
  Database User: kb_db
  Nginx Port (public): 80          <-- NEW
  Gunicorn Port (internal): 8000   <-- NEW
  Test Mode: False
  Allowed Hosts: localhost,127.0.0.1
```

**Application Access** (shows correct URLs):
```
# If Nginx port is 80:
Main application:    http://localhost/

# If Nginx port is custom (e.g., 8080):
Main application:    http://localhost:8080/
```

**Important Notes**:
```
Important Notes:
  - Nginx runs on port 80 (public) and proxies to Gunicorn on localhost:8000
  - Gunicorn serves Django on localhost:8000 (not publicly exposed)
  - Django-Q2 processes background tasks
```

---

## Deployment Scenarios

### Scenario 1: Default Ports (Most Common)

**User Input**:
```
Enter Nginx public port [80]: <Enter>
Enter Gunicorn internal port [8000]: <Enter>
```

**Result**:
- Nginx listens on port 80
- Gunicorn listens on localhost:8000
- Firewall opens HTTP (port 80)
- Access: `http://localhost/`

---

### Scenario 2: Custom Public Port (Development/Testing)

**User Input**:
```
Enter Nginx public port [80]: 8080
Enter Gunicorn internal port [8000]: <Enter>
```

**Result**:
- Nginx listens on port 8080
- Gunicorn listens on localhost:8000
- Firewall opens port 8080/tcp
- Access: `http://localhost:8080/`

**Use Case**: Multiple apps on same server, port 80 already in use

---

### Scenario 3: HTTPS Port

**User Input**:
```
Enter Nginx public port [80]: 443
Enter Gunicorn internal port [8000]: <Enter>
```

**Result**:
- Nginx listens on port 443
- Gunicorn listens on localhost:8000
- Firewall opens HTTPS (port 443)
- Access: `https://localhost/` (requires SSL certificate)

**Use Case**: Production deployment with SSL

---

### Scenario 4: Custom Both Ports (Advanced)

**User Input**:
```
Enter Nginx public port [80]: 3000
Enter Gunicorn internal port [8000]: 9000
```

**Result**:
- Nginx listens on port 3000
- Gunicorn listens on localhost:9000
- Firewall opens port 3000/tcp
- Access: `http://localhost:3000/`

**Use Case**: Specific port requirements, multiple deployments

---

## Benefits

### 1. **Clarity**
- Users now understand what each port is for
- Clear separation between public and internal ports
- Helpful explanations during deployment

### 2. **Flexibility**
- Can deploy on any port combination
- Supports multiple deployments on same server
- Works with existing infrastructure (reverse proxies, load balancers)

### 3. **Security**
- Gunicorn always on localhost only (never exposed)
- Firewall only opens the actual public port
- No unnecessary ports exposed

### 4. **Standards Compliance**
- Standard ports (80/443) use service names in firewall
- Custom ports use explicit port numbers
- Follows Linux best practices

### 5. **Backward Compatibility**
- `SERVER_PORT` still exists (maps to `GUNICORN_PORT`)
- Existing scripts continue to work
- .env file still uses `SERVER_PORT`

---

## Files Modified

### 1. `/opt/CCP/zktecoMGMT/deploy.sh`
- Added separate prompts for NGINX_PORT and GUNICORN_PORT
- Added explanatory text for port configuration
- Updated configuration summary to show both ports
- Updated application access URLs to use correct port
- Updated "Important Notes" to show correct ports

### 2. `/opt/CCP/zktecoMGMT/deploy_rhel.sh`
- Updated Nginx configuration to use `$NGINX_PORT`
- Updated proxy_pass to use `$GUNICORN_PORT`
- Added smart firewall logic (standard vs custom ports)
- Updated firewall messages to show actual port

### 3. `/opt/CCP/zktecoMGMT/PORT_CONFIGURATION_UPDATE.md` (This file)
- Documentation of changes

---

## Testing Recommendations

### Test 1: Default Ports
```bash
sudo ./deploy.sh
# When prompted:
# - Nginx port: <Enter> (default 80)
# - Gunicorn port: <Enter> (default 8000)

# Verify:
curl http://localhost/
sudo firewall-cmd --list-services | grep http
sudo netstat -tlnp | grep :80
sudo netstat -tlnp | grep :8000
```

**Expected**:
- Application accessible on port 80
- Firewall shows "http" service
- Nginx listening on 0.0.0.0:80
- Gunicorn listening on 127.0.0.1:8000

---

### Test 2: Custom Public Port
```bash
sudo ./deploy.sh
# When prompted:
# - Nginx port: 8080
# - Gunicorn port: <Enter> (default 8000)

# Verify:
curl http://localhost:8080/
sudo firewall-cmd --list-ports | grep 8080
sudo netstat -tlnp | grep :8080
```

**Expected**:
- Application accessible on port 8080
- Firewall shows "8080/tcp"
- Nginx listening on 0.0.0.0:8080
- Gunicorn listening on 127.0.0.1:8000

---

### Test 3: HTTPS Port
```bash
sudo ./deploy.sh
# When prompted:
# - Nginx port: 443
# - Gunicorn port: <Enter> (default 8000)

# Verify:
sudo firewall-cmd --list-services | grep https
sudo netstat -tlnp | grep :443
```

**Expected**:
- Firewall shows "https" service
- Nginx listening on 0.0.0.0:443
- (Will need SSL certificate for actual HTTPS)

---

### Test 4: Firewall Behavior
```bash
# Test standard port
sudo firewall-cmd --list-services  # Should show: http, https, etc.

# Test custom port
sudo firewall-cmd --list-ports     # Should show: 8080/tcp, etc.
```

---

## Edge Cases Handled

### 1. Port Already in Use
**Scenario**: Port 80 already used by another service

**Solution**: User can specify different port (e.g., 8080)
```
Enter Nginx public port [80]: 8080
```

---

### 2. Non-Root Ports (<1024)
**Scenario**: User tries to use port 80 without sudo

**Handling**: Script requires sudo, so this works correctly
```bash
sudo ./deploy.sh  # Required
```

---

### 3. Port Conflicts
**Scenario**: Gunicorn port conflicts with Nginx port

**Validation**: Not validated (rare, but could be added)

**Current Behavior**: Would fail during service start

**Future Enhancement**:
```bash
if [ "$NGINX_PORT" -eq "$GUNICORN_PORT" ]; then
    log "${RED}Error: Nginx and Gunicorn ports cannot be the same${NC}"
    exit 1
fi
```

---

### 4. Invalid Port Numbers
**Scenario**: User enters invalid port (e.g., 99999)

**Current Behavior**: Bash accepts it, Nginx/firewall will fail

**Future Enhancement**: Add validation
```bash
if [ "$NGINX_PORT" -lt 1 ] || [ "$NGINX_PORT" -gt 65535 ]; then
    log "${RED}Error: Port must be between 1-65535${NC}"
    exit 1
fi
```

---

## Backward Compatibility

### Environment Variables:
- ✅ `SERVER_PORT` still exists (maps to `GUNICORN_PORT`)
- ✅ `.env` file still uses `SERVER_PORT`
- ✅ Existing scripts continue to work

### Configuration Files:
- ✅ Gunicorn service uses `$SERVER_PORT` (from export)
- ✅ Nginx uses new variables but works correctly
- ✅ No breaking changes to existing deployments

---

## Future Enhancements

### 1. Port Validation
Add validation for port ranges and conflicts:
```bash
validate_port() {
    local port=$1
    if [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
        return 1
    fi
    return 0
}
```

### 2. Port Conflict Detection
Check if port is already in use:
```bash
if netstat -tlnp | grep -q ":$NGINX_PORT "; then
    log "${YELLOW}Warning: Port $NGINX_PORT appears to be in use${NC}"
    read -p "Continue anyway? (y/n): " CONTINUE
fi
```

### 3. SSL Certificate Setup
Automatically configure SSL if port 443 is chosen:
```bash
if [ "$NGINX_PORT" -eq 443 ]; then
    log "${YELLOW}HTTPS port detected. Would you like to configure SSL?${NC}"
    # Offer Let's Encrypt setup
fi
```

### 4. UFW Firewall Support (Debian)
Similar port handling for UFW:
```bash
if [ "$NGINX_PORT" -eq 80 ]; then
    ufw allow http
else
    ufw allow $NGINX_PORT/tcp
fi
```

---

## Summary

The deployment scripts now:

✅ Ask for two separate ports with clear explanations
✅ Configure Nginx to listen on user-specified port
✅ Configure firewall to open only necessary ports
✅ Show correct URLs in deployment summary
✅ Support standard ports (80/443) and custom ports
✅ Maintain backward compatibility
✅ Provide better user experience

**Result**: More flexible, clearer, and production-ready deployment.

---

**Last Updated**: 2025-10-27
**Applies To**: deploy.sh, deploy_rhel.sh
**Status**: Complete (deploy_debian.sh needs similar updates)
