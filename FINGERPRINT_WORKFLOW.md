# Fingerprint Management Workflow

## Overview

This document describes how to manage fingerprint enrollment and synchronization for ZKTeco K40 devices. Fingerprints can only be added to **existing users** that are already registered on the device.

## Important Concepts

### Fingerprint Slots (FINGER_MAP)

Each user can have up to **10 fingerprint templates**, one for each finger:

```python
FINGER_MAP = {
      0: "Left thumb",
      1: "Left index",
      2: "Left middle",
      3: "Left ring",
      4: "Left pinky",
      5: "Right thumb",
      6: "Right index",
      7: "Right middle",
      8: "Right ring",
      9: "Right pinky"
  })
```

### Parameters Explained

The ZKTeco SDK (pyzk library) uses these parameters:

| Parameter | Meaning | Typical Range | Notes |
|-----------|---------|---------------|-------|
| `uid` | Internal device user ID | 1-9999 | Must match Employee.user_id |
| `temp_id` | Finger index / template slot | 0-9 | Maps to FINGER_MAP (0=thumb, 1=index, etc.) |
| `valid` | Whether template is valid | 0 or 1 | 1 = valid, 0 = invalid/empty |
| `template` | Fingerprint binary template data | bytes/hex string | Device-specific format |

## PyZK Methods Available

The `pyzk` library provides these methods for fingerprint operations:

| Method | Purpose |
|--------|---------|
| `conn.enroll_user(uid, temp_id=0)` | Start fingerprint enrollment directly on the device for the given user and finger |
| `conn.set_user_template(uid, temp_id, valid, template)` | Upload an existing fingerprint template to a specific finger slot |
| `conn.get_user_template(uid, temp_id)` | Download a fingerprint template from a specific finger slot |
| `conn.delete_user_template(uid, temp_id)` | Delete a fingerprint for a specific finger |
| `conn.delete_user(uid)` | Delete user (and all fingerprints, passwords, faces, etc.) |

## Workflows

### Workflow 1: Enroll New Fingerprint via Device Scanner

**Prerequisites:**
- User must already exist on the device
- Physical access to the ZKTeco K40 device required

**Web Interface Process:**

1. Navigate to **Employees** → Select an employee
2. Click **Manage Fingerprints** button
3. Select the target **device** from dropdown
4. Select the **finger** from dropdown (e.g., "Right index" = temp_id 1)
5. Click **Enroll Fingerprint on Device**

**System Behavior:**

```python
# If fingerprint already exists for this finger:
conn.delete_user_template(uid, temp_id)

# Start enrollment on device
conn.enroll_user(uid, temp_id=temp_id)
```

6. Device will enter enrollment mode
7. User must place selected finger on device scanner
8. Follow device prompts (usually 3 scans of same finger)
9. Device will beep/flash when complete
10. Click **Download Templates** to save to local database

**Important Notes:**
- User must be physically present at the device
- Enrollment happens on the device hardware itself
- Web application initiates the process remotely
- Device will prompt for multiple scans for quality

### Workflow 2: Download Fingerprints from Device to Database

**Purpose:** Backup fingerprint templates from device to local database

**Web Interface Process:**

1. Navigate to **Employees** → Select an employee
2. Click **Manage Fingerprints** button
3. Select the target **device** from dropdown
4. Click **Download All Fingerprints from Device**

**System Behavior:**

```python
for temp_id in range(10):  # Check all 10 finger slots
    template = conn.get_user_template(uid, temp_id)
    if template:
        # Save or update in database
        Fingerprint.objects.update_or_create(
            employee=employee,
            finger_index=temp_id,
            defaults={
                'template': template,
                'device': device
            }
        )
```

**Result:**
- All fingerprint templates from device are saved locally
- Existing local templates are **replaced** with device data
- Empty slots on device are skipped
- Useful for backup and disaster recovery

### Workflow 3: Upload Fingerprints from Database to Device

**Purpose:** Restore fingerprint templates from local database to device

**Web Interface Process:**

1. Navigate to **Employees** → Select an employee
2. Click **Manage Fingerprints** button
3. Select the target **device** from dropdown
4. Click **Upload All Fingerprints to Device**

**System Behavior:**

```python
fingerprints = Fingerprint.objects.filter(employee=employee)
for fingerprint in fingerprints:
    conn.set_user_template(
        uid=employee.user_id,
        temp_id=fingerprint.finger_index,
        valid=1,
        template=fingerprint.template
    )
```

**Result:**
- All local fingerprint templates are uploaded to device
- Existing device templates are **replaced** with local data
- Useful for:
  - Disaster recovery (device reset)
  - Migrating user to new device
  - Restoring from backup

### Workflow 4: Replace Existing Fingerprint

**Scenario:** User wants to re-enroll a finger with a new reading

**Web Interface Process:**

1. Navigate to **Employees** → Select an employee
2. Click **Manage Fingerprints** button
3. Select the target **device** from dropdown
4. Select the **finger** to replace (e.g., "Right index" = temp_id 1)
5. Click **Re-enroll Fingerprint on Device**

**System Behavior:**

```python
# Always delete existing template first
conn.delete_user_template(uid, temp_id)

# Start new enrollment
conn.enroll_user(uid, temp_id=temp_id)
```

6. Device enters enrollment mode
7. User scans finger multiple times
8. New template replaces old template
9. Download to sync with local database

### Workflow 5: Delete Fingerprint

**Purpose:** Remove a fingerprint template from specific finger slot

**Web Interface Process:**

1. Navigate to **Employees** → Select an employee
2. Click **Manage Fingerprints** button
3. Select the target **device** from dropdown
4. Select the **finger** to delete
5. Click **Delete Fingerprint**

**System Behavior:**

```python
# Delete from device
conn.delete_user_template(uid, temp_id)

# Delete from local database
Fingerprint.objects.filter(
    employee=employee,
    finger_index=temp_id
).delete()
```

## Complete User Onboarding Process

```
1. Create Employee in Web App
   └─> Employee record with unique user_id (1-9999)

2. Sync Employee TO Device
   └─> User exists on device, no fingerprints yet

3. Enroll Fingerprints
   ├─> Option A: Via web interface (enroll_user)
   │   └─> User goes to device, follows prompts
   └─> Option B: Directly on device menu
       └─> Navigate device menu, enroll manually

4. Download Templates to Database (Backup)
   └─> Templates saved locally for disaster recovery

5. Test Fingerprint
   └─> User punches in/out on device

6. Download Attendance Events
   └─> Verify events appear in web interface
```

## Fingerprint Management UI (To Be Implemented)

### Employee Fingerprint Management Page

**URL:** `/employees/<employee_id>/fingerprints/`

**Interface Elements:**

```
┌─────────────────────────────────────────────────────┐
│ Manage Fingerprints: John Doe (EMP001)             │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Device: [Select Device ▼] [K40-Main]               │
│                                                     │
│ ┌─────────────────────────────────────────────┐   │
│ │ Right Hand                                   │   │
│ │ ┌──────────────┐  ┌──────────────┐         │   │
│ │ │ Right Thumb  │  │ Right Index  │         │   │
│ │ │    (0)       │  │    (1)       │         │   │
│ │ │ ✓ Enrolled   │  │ ✗ Empty      │         │   │
│ │ │ [Re-enroll]  │  │ [Enroll]     │         │   │
│ │ │ [Delete]     │  │              │         │   │
│ │ └──────────────┘  └──────────────┘         │   │
│ │ ... (fingers 2-4)                           │   │
│ └─────────────────────────────────────────────┘   │
│                                                     │
│ ┌─────────────────────────────────────────────┐   │
│ │ Left Hand                                    │   │
│ │ ┌──────────────┐  ┌──────────────┐         │   │
│ │ │ Left Thumb   │  │ Left Index   │         │   │
│ │ │    (5)       │  │    (6)       │         │   │
│ │ │ ✓ Enrolled   │  │ ✓ Enrolled   │         │   │
│ │ │ [Re-enroll]  │  │ [Re-enroll]  │         │   │
│ │ │ [Delete]     │  │ [Delete]     │         │   │
│ │ └──────────────┘  └──────────────┘         │   │
│ │ ... (fingers 7-9)                           │   │
│ └─────────────────────────────────────────────┘   │
│                                                     │
│ [Download All from Device]                         │
│ [Upload All to Device]                             │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Actions Available

**Per-Finger Actions:**
- **Enroll**: Start enrollment on device (for empty slot)
- **Re-enroll**: Delete existing + start new enrollment
- **Delete**: Remove fingerprint from device and database

**Bulk Actions:**
- **Download All from Device**: Backup all templates to database
- **Upload All to Device**: Restore all templates from database

## Database Schema

### Fingerprint Model

```python
class Fingerprint(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True)
    finger_index = models.IntegerField()  # 0-9 (temp_id)
    template = models.BinaryField()  # Binary fingerprint data
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['employee', 'device', 'finger_index']
```

**Key Points:**
- `finger_index` maps to FINGER_MAP (0-9)
- `template` stores raw binary template data
- Unique constraint prevents duplicate finger enrollments
- Can store templates from multiple devices per employee

## Command Line Interface

### Management Commands (To Be Implemented)

```bash
# Enroll fingerprint via device
python manage.py enroll_fingerprint <employee_id> <device_id> --finger=<0-9>

# Download all fingerprints for an employee
python manage.py download_fingerprints <employee_id> <device_id>

# Upload all fingerprints for an employee
python manage.py upload_fingerprints <employee_id> <device_id>

# Download fingerprints for all employees on a device
python manage.py sync_fingerprints <device_id> --direction=from

# Upload all local fingerprints to device
python manage.py sync_fingerprints <device_id> --direction=to

# Bidirectional sync (download from device, overwrite local)
python manage.py sync_fingerprints <device_id> --direction=both
```

## Error Handling

### Common Errors

**"User not found on device"**
```
Solution: Sync employee to device first
Command: python manage.py sync_employees <device_id> --direction=to
```

**"Fingerprint enrollment timeout"**
```
Cause: User did not scan finger within timeout period
Solution: Restart enrollment, ensure user is at device
```

**"Template data invalid"**
```
Cause: Corrupted template data or incompatible format
Solution: Re-enroll fingerprint on device, download fresh template
```

**"Device memory full"**
```
Cause: Device storage capacity reached
Solution:
1. Download attendance data
2. Clear attendance from device
3. Remove unused users/templates
```

## Security Considerations

### Template Data Security

- **Binary Format**: Templates are stored as binary data
- **Not Reversible**: Cannot recreate actual fingerprint from template
- **Device-Specific**: Templates may not work across different device models
- **Encryption**: Consider encrypting template data in database for production

### Access Control

- Fingerprint management should require authentication
- Only authorized users should enroll/delete fingerprints
- Log all fingerprint operations for audit trail
- Implement device-level passwords for enrollment operations

### Best Practices

1. **Backup Regularly**: Download templates to database periodically
2. **Multiple Fingers**: Enroll 2-3 fingers per employee for redundancy
3. **Test After Enrollment**: Verify fingerprint works on device
4. **Version Control**: Track when templates were last updated
5. **Audit Logs**: Log all enrollment, deletion, and sync operations

## Device-Specific Notes

### ZKTeco K40 Capacity

- **Maximum Users**: ~3,000
- **Maximum Templates**: ~10,000 (varies by model)
- **Template Size**: ~600 bytes each
- **Enrollment Time**: 10-15 seconds per finger

### Enrollment Quality Tips

- Clean the scanner surface regularly
- Ensure finger is dry (not too sweaty)
- Apply consistent pressure
- Use center of fingerprint pad
- Avoid partial prints
- Re-enroll if recognition rate is poor

## Troubleshooting

### Fingerprint Not Recognized After Enrollment

**Possible Causes:**
- Poor quality enrollment (partial scans)
- Scanner surface dirty
- Finger condition changed (cuts, dryness)
- Device sensitivity settings

**Solutions:**
1. Re-enroll with better quality scans
2. Clean scanner surface
3. Enroll additional backup fingers
4. Adjust device sensitivity settings

### Templates Not Downloading

**Possible Causes:**
- Network connection issues
- Device timeout
- Template data corruption
- No templates enrolled on device

**Solutions:**
1. Test device connection first
2. Check if templates exist on device
3. Download individual templates (temp_id 0-9)
4. Review device logs for errors

### Upload Fails

**Possible Causes:**
- Device memory full
- Template format incompatible
- User not on device
- Network issues

**Solutions:**
1. Ensure user exists on device first
2. Clear device memory if full
3. Verify template data is valid
4. Use set_user_template with valid=1

## API Reference

### ZKDeviceConnector Methods (To Be Added)

```python
class ZKDeviceConnector:
    def enroll_fingerprint(self, conn, uid, temp_id):
        """Start enrollment on device for specific finger"""

    def get_fingerprint_template(self, conn, uid, temp_id):
        """Download single fingerprint template"""

    def get_all_fingerprint_templates(self, conn, uid):
        """Download all templates for a user (0-9)"""

    def set_fingerprint_template(self, conn, uid, temp_id, template):
        """Upload single fingerprint template"""

    def delete_fingerprint_template(self, conn, uid, temp_id):
        """Delete single fingerprint"""

    def sync_fingerprints(self, conn, employee, direction='both'):
        """Sync fingerprints between device and database"""
```

## Testing Strategy

### Mock Mode

The mock implementation should simulate:

```python
class MockConnection:
    def __init__(self):
        self.templates = {}  # {uid: {temp_id: template_data}}

    def enroll_user(self, uid, temp_id=0):
        # Simulate enrollment (generate fake template)
        self.templates.setdefault(uid, {})[temp_id] = b'MOCK_TEMPLATE_' + bytes(f'{uid}_{temp_id}', 'utf-8')
        return True

    def get_user_template(self, uid, temp_id):
        return self.templates.get(uid, {}).get(temp_id)

    def set_user_template(self, uid, temp_id, valid, template):
        self.templates.setdefault(uid, {})[temp_id] = template
        return True

    def delete_user_template(self, uid, temp_id):
        if uid in self.templates and temp_id in self.templates[uid]:
            del self.templates[uid][temp_id]
        return True
```

### Unit Tests

```python
def test_enroll_fingerprint():
    """Test fingerprint enrollment"""

def test_download_templates():
    """Test downloading templates from device"""

def test_upload_templates():
    """Test uploading templates to device"""

def test_delete_template():
    """Test deleting fingerprint"""

def test_replace_template():
    """Test replacing existing fingerprint"""
```

## Summary

**Key Points to Remember:**

1. ✅ Fingerprints can only be added to **existing users**
2. ✅ Each user can have up to **10 fingerprints** (one per finger)
3. ✅ Fingerprints can be **replaced** by deleting + re-enrolling
4. ✅ Templates can be **downloaded** from device (backup)
5. ✅ Templates can be **uploaded** to device (restore)
6. ✅ Enrollment happens on the **physical device** hardware
7. ✅ Web interface **initiates** enrollment remotely
8. ✅ Always use `temp_id` (0-9) to identify finger slot

**Implementation Priority:**

1. Add fingerprint download functionality
2. Add fingerprint upload functionality
3. Create fingerprint management UI
4. Add enroll_user remote trigger
5. Add delete_user_template functionality
6. Create management commands
7. Add bulk operations
8. Implement audit logging
