#!/bin/bash
# Test task endpoint with proper authentication

PROJECT_DIR="/opt/CCP/zktecoMGMT"

cd "$PROJECT_DIR"
source zkteco_env/bin/activate

echo "=== Testing Task Endpoint ==="
echo ""

# Create a test to call the view directly
python manage.py shell << 'PYEOF'
from django.test import Client
from django.contrib.auth.models import User

# Get a user
user = User.objects.first()
if not user:
    print("✗ No users found")
    exit(1)

print(f"✓ Testing with user: {user.username}")

# Create a test client and login
client = Client()
client.force_login(user)

# Try to start a sync task
print("\nTesting POST to /tasks/sync-to-device/1/...")
response = client.post('/en/tasks/sync-to-device/1/')

print(f"Status Code: {response.status_code}")
print(f"Content-Type: {response.get('Content-Type', 'N/A')}")
print(f"Content Length: {len(response.content)}")
print(f"Content: {response.content.decode('utf-8')}")

if response.status_code == 200:
    import json
    try:
        data = json.loads(response.content)
        print(f"\n✓ JSON Response:")
        print(f"  Success: {data.get('success')}")
        print(f"  Task ID: {data.get('task_id')}")
        print(f"  Message: {data.get('message')}")
    except json.JSONDecodeError as e:
        print(f"\n✗ JSON Parse Error: {e}")
else:
    print(f"\n✗ Unexpected status code: {response.status_code}")

PYEOF
