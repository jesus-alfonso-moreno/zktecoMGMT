#!/usr/bin/env python
"""
Test fingerprint operations with detailed logging
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zkteco_project.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from device.models import Device
from device.zk_connector import ZKDeviceConnector
from employees.models import Employee, Fingerprint

def test_fingerprint_operations():
    print("=" * 70)
    print("FINGERPRINT OPERATIONS TEST WITH LOGGING")
    print("=" * 70)
    print("\nThis test will generate detailed logs in logs/device_auth.log")
    print("All operations use MOCK mode for safety\n")

    # Get device and employee
    device = Device.objects.first()
    employee = Employee.objects.first()

    if not device or not employee:
        print("ERROR: No device or employee found in database")
        return

    print(f"Device: {device.name} ({device.ip_address})")
    print(f"Employee: {employee.full_name} (UID: {employee.user_id})")
    print()

    # Initialize connector in MOCK mode
    connector = ZKDeviceConnector(device, use_mock=True)
    print("✓ Connector initialized in MOCK mode")
    print()

    try:
        conn = connector.connect()
        print("✓ Connected to device")
        print()

        # Test 1: Download existing fingerprints
        print("TEST 1: Download All Fingerprints")
        print("-" * 50)
        templates = connector.get_all_fingerprint_templates(conn, employee.user_id)
        print(f"Result: Found {len(templates)} fingerprint(s)")
        for temp_id in templates.keys():
            finger_name = {
                0: "Left thumb", 1: "Left index", 2: "Left middle",
                3: "Left ring", 4: "Left pinky", 5: "Right thumb",
                6: "Right index", 7: "Right middle", 8: "Right ring",
                9: "Right pinky"
            }.get(temp_id, f"Finger {temp_id}")
            print(f"  - {finger_name}")
        print()

        # Test 2: Upload fingerprint (if we have any in database)
        print("TEST 2: Upload Fingerprint Template")
        print("-" * 50)
        fp = Fingerprint.objects.filter(employee=employee).first()
        if fp:
            print(f"Uploading template for finger {fp.finger_index}")
            result = connector.set_fingerprint_template(
                conn,
                employee.user_id,
                fp.finger_index,
                fp.template
            )
            print(f"Result: {'SUCCESS' if result else 'FAILED'}")
        else:
            print("No fingerprints in database to upload")
        print()

        # Test 3: Enroll new fingerprint
        print("TEST 3: Start Fingerprint Enrollment")
        print("-" * 50)
        test_finger = 7  # Right middle
        print(f"Starting enrollment for finger {test_finger}")
        result = connector.enroll_user_fingerprint(conn, employee.user_id, test_finger)
        print(f"Result: {'SUCCESS' if result else 'FAILED'}")
        print()

        # Test 4: Delete fingerprint
        print("TEST 4: Delete Fingerprint Template")
        print("-" * 50)
        delete_finger = 7
        print(f"Deleting template for finger {delete_finger}")
        result = connector.delete_fingerprint_template(conn, employee.user_id, delete_finger)
        print(f"Result: {'SUCCESS' if result else 'FAILED'}")
        print()

        conn.disconnect()
        print("✓ Disconnected from device")
        print()

    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")
        print()

    print("=" * 70)
    print("TEST COMPLETED")
    print("=" * 70)
    print("\nCheck detailed logs in:")
    print("  - logs/device_auth.log (all operations)")
    print("  - logs/device_errors.log (errors only)")
    print()

if __name__ == '__main__':
    test_fingerprint_operations()
