#!/bin/bash
# Verify Django-Q2 configuration in settings

cd /home/almita/CCP/zktecoMGMT
source zkteco_env/bin/activate

echo "Checking if Q_CLUSTER is configured in settings.py..."
echo ""

if grep -q "Q_CLUSTER" zkteco_project/settings.py; then
    echo "✓ Q_CLUSTER found in settings.py"
    echo ""
    echo "Current configuration:"
    grep -A 20 "Q_CLUSTER" zkteco_project/settings.py
else
    echo "✗ Q_CLUSTER NOT found in settings.py"
    echo ""
    echo "Django-Q2 requires Q_CLUSTER configuration!"
    echo "Adding default configuration now..."
    
    cat >> zkteco_project/settings.py << 'PYEOF'

# Django-Q2 Configuration
Q_CLUSTER = {
    'name': 'zkteco',
    'workers': 4,
    'recycle': 500,
    'timeout': 300,  # 5 minutes - important for long-running tasks
    'compress': True,
    'save_limit': 250,
    'queue_limit': 500,
    'cpu_affinity': 1,
    'label': 'Django Q2',
    'redis': {
        'host': '127.0.0.1',
        'port': 6379,
        'db': 0,
    },
    'orm': 'default',  # Use Django ORM as broker (no Redis needed)
}
PYEOF
    
    echo "✓ Q_CLUSTER configuration added to settings.py"
fi

echo ""
echo "Restarting django-q service..."
sudo systemctl restart django-q

echo ""
echo "Checking service status..."
sleep 2
sudo systemctl status django-q --no-pager | head -15
