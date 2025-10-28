#!/bin/bash
# Fix virtual environment hardcoded paths after moving to /opt/CCP/zktecoMGMT

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Variables
PROJECT_DIR="/opt/CCP/zktecoMGMT"
OLD_PATH="/home/almita/CCP/zktecoMGMT"
NEW_PATH="/opt/CCP/zktecoMGMT"
VENV_NAME="zkteco_env"

# =============================================================================
# Logging Setup
# =============================================================================
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/fix_venv_paths_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

log "${BLUE}========================================${NC}"
log "${BLUE}   Fix Virtual Environment Paths${NC}"
log "${BLUE}========================================${NC}"
log ""
log "${GREEN}Log file: $LOG_FILE${NC}"
log "Started at: $(date '+%Y-%m-%d %H:%M:%S')"
log ""

# =============================================================================
# Step 1: Fix all Python shebangs in venv/bin
# =============================================================================
log "${YELLOW}Step 1: Fixing Python shebangs in $VENV_NAME/bin...${NC}"

FIXED_COUNT=0
BIN_DIR="$PROJECT_DIR/$VENV_NAME/bin"

cd "$BIN_DIR"

for file in *; do
    if [ -f "$file" ] && [ -x "$file" ]; then
        # Check if file has the old shebang
        if head -n 1 "$file" 2>/dev/null | grep -q "$OLD_PATH"; then
            log "  Fixing: $file"
            # Replace old path with new path in first line
            sed -i "1s|$OLD_PATH|$NEW_PATH|" "$file"
            FIXED_COUNT=$((FIXED_COUNT + 1))
        fi
    fi
done

log "${GREEN}✓ Fixed $FIXED_COUNT files${NC}"

# =============================================================================
# Step 2: Fix activate scripts
# =============================================================================
log ""
log "${YELLOW}Step 2: Fixing activate scripts...${NC}"

# Fix activate
if [ -f "$BIN_DIR/activate" ]; then
    sed -i "s|$OLD_PATH|$NEW_PATH|g" "$BIN_DIR/activate"
    log "${GREEN}✓ Fixed activate${NC}"
fi

# Fix activate.csh
if [ -f "$BIN_DIR/activate.csh" ]; then
    sed -i "s|$OLD_PATH|$NEW_PATH|g" "$BIN_DIR/activate.csh"
    log "${GREEN}✓ Fixed activate.csh${NC}"
fi

# Fix activate.fish
if [ -f "$BIN_DIR/activate.fish" ]; then
    sed -i "s|$OLD_PATH|$NEW_PATH|g" "$BIN_DIR/activate.fish"
    log "${GREEN}✓ Fixed activate.fish${NC}"
fi

# Fix Activate.ps1
if [ -f "$BIN_DIR/Activate.ps1" ]; then
    sed -i "s|$OLD_PATH|$NEW_PATH|g" "$BIN_DIR/Activate.ps1"
    log "${GREEN}✓ Fixed Activate.ps1${NC}"
fi

# =============================================================================
# Step 3: Fix pyvenv.cfg
# =============================================================================
log ""
log "${YELLOW}Step 3: Fixing pyvenv.cfg...${NC}"

PYVENV_CFG="$PROJECT_DIR/$VENV_NAME/pyvenv.cfg"

if [ -f "$PYVENV_CFG" ]; then
    sed -i "s|$OLD_PATH|$NEW_PATH|g" "$PYVENV_CFG"
    log "${GREEN}✓ Fixed pyvenv.cfg${NC}"
    log "  Content:" | tee -a "$LOG_FILE"
    cat "$PYVENV_CFG" | tee -a "$LOG_FILE"
else
    log "${YELLOW}~ pyvenv.cfg not found${NC}"
fi

# =============================================================================
# Step 4: Set correct ownership
# =============================================================================
log ""
log "${YELLOW}Step 4: Setting ownership to almita:almita...${NC}"

sudo chown -R almita:almita "$PROJECT_DIR/$VENV_NAME"

if [ $? -eq 0 ]; then
    log "${GREEN}✓ Ownership updated${NC}"
else
    log "${RED}✗ Failed to update ownership${NC}"
fi

# =============================================================================
# Step 5: Verify fixes
# =============================================================================
log ""
log "${YELLOW}Step 5: Verifying fixes...${NC}"

# Check gunicorn shebang
GUNICORN_SHEBANG=$(head -n 1 "$BIN_DIR/gunicorn")
log "  gunicorn shebang: $GUNICORN_SHEBANG"

if echo "$GUNICORN_SHEBANG" | grep -q "$NEW_PATH"; then
    log "${GREEN}✓ gunicorn shebang is correct${NC}"
else
    log "${RED}✗ gunicorn shebang still has old path${NC}"
fi

# Check if gunicorn is executable
if [ -x "$BIN_DIR/gunicorn" ]; then
    log "${GREEN}✓ gunicorn is executable${NC}"
else
    log "${RED}✗ gunicorn is not executable${NC}"
fi

# Check python3 symlink
if [ -L "$BIN_DIR/python3" ]; then
    PYTHON3_TARGET=$(readlink -f "$BIN_DIR/python3")
    log "  python3 points to: $PYTHON3_TARGET"
    log "${GREEN}✓ python3 symlink exists${NC}"
else
    log "${RED}✗ python3 symlink not found${NC}"
fi

# Test if gunicorn can be executed
log ""
log "  Testing gunicorn execution..."
if "$BIN_DIR/gunicorn" --version 2>&1 | tee -a "$LOG_FILE"; then
    log "${GREEN}✓ gunicorn executes successfully${NC}"
else
    log "${RED}✗ gunicorn execution failed${NC}"
fi

# =============================================================================
# Completion
# =============================================================================
log ""
log "${BLUE}========================================${NC}"
log "${GREEN}✓ Virtual Environment Paths Fixed!${NC}"
log "${BLUE}========================================${NC}"
log ""
log "Completed at: $(date '+%Y-%m-%d %H:%M:%S')"
log ""
log "${YELLOW}Summary:${NC}"
log "  Old path: $OLD_PATH"
log "  New path: $NEW_PATH"
log "  Files fixed: $FIXED_COUNT"
log ""
log "${YELLOW}Next step:${NC}"
log "  Run the update_configs.sh script again:"
log "  ${BLUE}sudo $PROJECT_DIR/update_configs.sh${NC}"
log ""
log "${YELLOW}Log file:${NC}"
log "  ${BLUE}$LOG_FILE${NC}"
log ""
