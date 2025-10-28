#!/bin/bash
# Restart Gunicorn and test static file serving

echo "=== Restarting Gunicorn ==="
sudo systemctl restart gunicorn
sleep 3

echo ""
echo "=== Checking Gunicorn Status ==="
sudo systemctl status gunicorn --no-pager | head -20

echo ""
echo "=== Testing Static File Access ==="
echo "Testing: http://localhost:8000/static/js/task_progress.js"
curl -I http://localhost:8000/static/js/task_progress.js

echo ""
echo "=== First 30 lines of JavaScript file ==="
curl -s http://localhost:8000/static/js/task_progress.js | head -n 30

echo ""
echo "=== Testing Alternative Static URL ==="
echo "Testing: http://localhost:8000/en/static/js/task_progress.js"
curl -I http://localhost:8000/en/static/js/task_progress.js
