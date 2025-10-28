#!/bin/bash
# Create Django superuser

cd /home/almita/CCP/zktecoMGMT
source zkteco_env/bin/activate

echo "Creating Django superuser..."
echo ""
python manage.py createsuperuser

echo ""
echo "✓ Superuser created!"
echo ""
echo "You can now log in at:"
echo "  http://localhost:8000/admin"
