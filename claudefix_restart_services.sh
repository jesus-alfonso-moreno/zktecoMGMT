#!/bin/bash
# Restart Django services after migrations

echo "Restarting gunicorn and django-q services..."
sudo systemctl restart gunicorn django-q

echo ""
echo "Waiting for services to start..."
sleep 2

echo ""
echo "Checking service status..."
sudo systemctl status gunicorn django-q --no-pager

echo ""
echo "✓ Services restarted!"
echo ""
echo "Now you can access the website at:"
echo "  http://localhost:8000"
echo ""
echo "Note: You need to create a superuser to access /admin"
echo "Run: ./claudefix_create_superuser.sh"
