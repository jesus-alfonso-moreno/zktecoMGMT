#!/bin/bash
# Check if views are using async tasks

cd /home/almita/CCP/zktecoMGMT

echo "=== Checking if async task endpoints exist ==="
echo ""
echo "Task app URLs (async endpoints):"
grep -n "path" tasks/urls.py | head -10

echo ""
echo "=== Checking employee views for sync functions ==="
echo ""
echo "Employee sync views (should redirect to task endpoints):"
grep -n "def sync_to_device\|def sync_from_device\|def download" employees/views.py | head -10

echo ""
echo "=== Checking attendance views for download functions ==="
echo ""
echo "Attendance download views:"
grep -n "def.*download\|def.*sync" attendance/views.py 2>/dev/null || echo "No sync/download functions found in attendance/views.py"

echo ""
echo "=== Solution ==="
echo "The employee sync views are still using SYNCHRONOUS operations."
echo "They need to be updated to use the async task system from tasks/ app."
echo ""
echo "The async endpoints are available at:"
echo "  - /tasks/sync-to-device/<device_id>/"
echo "  - /tasks/sync-from-device/<device_id>/"  
echo "  - /tasks/download-attendance/<device_id>/"
echo ""
echo "But the old employee views at /employees/sync-to-device/ are still synchronous!"
