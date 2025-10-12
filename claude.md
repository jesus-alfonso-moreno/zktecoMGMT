# ZKTeco K40 Django Integration Project

## Project Goal
Build a Django web application that connects to ZKTeco K40 biometric attendance devices using the pyzk library (https://github.com/fananimi/pyzk). The system should manage employee data, synchronize with the device, and track attendance events.

## Critical Requirements

### 1. MOCK Mode for Development
**IMPORTANT**: Since we don't have access to the physical K40 device during development, implement a MOCK mode:
- Create a `MockZK` class that simulates all pyzk device responses
- Add `ZK_TEST_MODE` setting (default: True) to switch between mock and real device
- All features must work fully with mock data
- Include fake users, attendance events, and fingerprints in mock
- Document how to switch to real device (set `ZK_TEST_MODE=False` and configure actual IP)

### 2. Core Functionality
- **Device Management**: Connect to K40 devices, store configurations, test connections
- **Employee Sync**: Upload/download employees with fingerprints to/from device
- **Attendance Tracking**: Download attendance events, store in database, generate reports
- **Web Interface**: User-friendly interface for all operations

### 3. Technology Stack
- **Backend**: Python 3.10+, Django 4.2+
- **Device Library**: pyzk
- **Database**: SQLite (development), PostgreSQL (production-ready)
- **Frontend**: Bootstrap 5 with Django templates
- **Background Tasks**: Django-Q (for periodic sync)

## Project Structure
```
zkteco_project/
├── manage.py
├── requirements.txt
├── README.md
├── .env.example
├── zkteco_project/          # Main project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── device/                  # Device management app
│   ├── models.py           # Device model
│   ├── views.py            # Device CRUD, test connection
│   ├── zk_connector.py     # Pyzk wrapper with MOCK support
│   ├── mocks.py            # Mock device implementation
│   └── management/
│       └── commands/
│           └── test_device.py  # CLI command to test device
├── employees/               # Employee management app
│   ├── models.py           # Employee, Fingerprint models
│   ├── views.py            # Employee CRUD, sync views
│   └── forms.py
├── attendance/              # Attendance tracking app
│   ├── models.py           # AttendanceEvent model
│   ├── views.py            # Event list, reports
│   └── reports.py          # Report generation
├── templates/
│   ├── base.html
│   ├── device/
│   ├── employees/
│   └── attendance/
└── static/
    ├── css/
    └── js/
```

## Database Models

### Device Model
```python
class Device(models.Model):
    """Stores ZKTeco K40 device connection information"""
    name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    port = models.IntegerField(default=4370)
    device_id = models.IntegerField(default=1)
    serial_number = models.CharField(max_length=100, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Employee Model
```python
class Employee(models.Model):
    """Employee/User that exists in Django and on device"""
    user_id = models.IntegerField(unique=True)  # Device user ID (1-65535)
    employee_id = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    department = models.CharField(max_length=100, blank=True)
    card_number = models.CharField(max_length=50, blank=True)
    password = models.CharField(max_length=50, blank=True)  # Device password, not web login
    privilege = models.IntegerField(default=0)  # 0=User, 14=Admin
    is_active = models.BooleanField(default=True)
    synced_to_device = models.BooleanField(default=False)
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
```

### Fingerprint Model
```python
class Fingerprint(models.Model):
    """Stores fingerprint templates for employees"""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='fingerprints')
    finger_index = models.IntegerField()  # 0-9 for 10 fingers
    template = models.TextField()  # Base64 encoded fingerprint template
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['employee', 'finger_index']
```

### AttendanceEvent Model
```python
class AttendanceEvent(models.Model):
    """Attendance punch events from device"""
    PUNCH_TYPES = (
        (0, 'Check In'),
        (1, 'Check Out'),
        (2, 'Break Out'),
        (3, 'Break In'),
        (4, 'Overtime In'),
        (5, 'Overtime Out'),
    )
    
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    user_id = models.IntegerField()  # Device user ID
    timestamp = models.DateTimeField()
    punch_type = models.IntegerField(choices=PUNCH_TYPES, default=0)
    verify_mode = models.IntegerField(default=0)  # 1=Fingerprint, 2=Card, etc.
    work_code = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['device', 'user_id', 'timestamp']
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['employee', '-timestamp']),
        ]
```

## ZKDeviceConnector Implementation

Create `device/zk_connector.py` with mock support:

```python
from django.conf import settings
from zk import ZK
from .mocks import MockZK

class ZKDeviceConnector:
    """Wrapper for pyzk library with mock support"""
    
    def __init__(self, device, use_mock=None):
        self.device = device
        
        # Use mock if in test mode or explicitly requested
        if use_mock is None:
            use_mock = getattr(settings, 'ZK_TEST_MODE', True)
        
        self.use_mock = use_mock
        
        if use_mock:
            self.zk = MockZK(device.ip_address, device.port)
        else:
            self.zk = ZK(device.ip_address, port=device.port, timeout=5)
    
    def test_connection(self):
        """Test if device is reachable"""
        try:
            conn = self.connect()
            conn.disconnect()
            return True, "Connection successful"
        except Exception as e:
            return False, str(e)
    
    def connect(self):
        """Connect to device"""
        return self.zk.connect()
    
    def get_device_info(self, conn):
        """Get device serial number and firmware"""
        return {
            'serial_number': conn.get_serialnumber(),
            'firmware_version': conn.get_firmware_version(),
            'platform': conn.get_platform(),
        }
    
    def get_users(self, conn):
        """Download all users from device"""
        return conn.get_users()
    
    def set_user(self, conn, uid, name, privilege, password, group_id, user_id):
        """Upload user to device"""
        return conn.set_user(uid, name, privilege, password, group_id, user_id)
    
    def delete_user(self, conn, uid):
        """Delete user from device"""
        return conn.delete_user(uid)
    
    def get_attendance(self, conn):
        """Download attendance events"""
        return conn.get_attendance()
    
    def clear_attendance(self, conn):
        """Clear attendance records from device"""
        return conn.clear_attendance()
```

## Mock Implementation

Create `device/mocks.py`:

```python
from datetime import datetime, timedelta
import random

class MockUser:
    def __init__(self, uid, name, privilege, password, group_id, user_id):
        self.uid = uid
        self.name = name
        self.privilege = privilege
        self.password = password
        self.group_id = group_id
        self.user_id = user_id

class MockAttendance:
    def __init__(self, user_id, timestamp, punch):
        self.user_id = user_id
        self.timestamp = timestamp
        self.punch = punch
        self.status = 0

class MockConnection:
    def __init__(self):
        # Generate fake users
        self.users = [
            MockUser(1, "John Doe", 0, "", "0", "EMP001"),
            MockUser(2, "Jane Smith", 0, "", "0", "EMP002"),
            MockUser(3, "Bob Johnson", 0, "", "0", "EMP003"),
            MockUser(4, "Alice Williams", 14, "", "0", "EMP004"),
        ]
        
        # Generate fake attendance for last 7 days
        self.attendance = []
        base_time = datetime.now() - timedelta(days=7)
        for day in range(7):
            for user_id in [1, 2, 3, 4]:
                # Check in
                check_in = base_time + timedelta(days=day, hours=9, minutes=random.randint(0, 30))
                self.attendance.append(MockAttendance(user_id, check_in, 0))
                
                # Check out
                check_out = base_time + timedelta(days=day, hours=17, minutes=random.randint(0, 30))
                self.attendance.append(MockAttendance(user_id, check_out, 1))
    
    def get_users(self):
        return self.users
    
    def set_user(self, uid, name, privilege, password, group_id, user_id):
        print(f"[MOCK] Would set user: {name}")
        return True
    
    def delete_user(self, uid):
        print(f"[MOCK] Would delete user: {uid}")
        return True
    
    def get_attendance(self):
        return self.attendance
    
    def clear_attendance(self):
        print("[MOCK] Would clear attendance")
        return True
    
    def get_serialnumber(self):
        return "MOCK-K40-12345"
    
    def get_firmware_version(self):
        return "Ver 6.60 Apr 28 2018"
    
    def get_platform(self):
        return "ZEM560"
    
    def disconnect(self):
        pass

class MockZK:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
    
    def connect(self):
        return MockConnection()
```

## Key Features to Implement

### 1. Device Management Views
- **List Devices** (`/device/`) - Show all configured devices with status
- **Add Device** (`/device/add/`) - Form to add new device
- **Edit Device** (`/device/<id>/edit/`) - Edit device configuration
- **Test Connection** (`/device/<id>/test/`) - AJAX endpoint to test connection
- **Device Info** (`/device/<id>/info/`) - Show device details (serial, firmware)

### 2. Employee Management Views
- **List Employees** (`/employees/`) - Paginated list with search
- **Add Employee** (`/employees/add/`) - Create new employee
- **Edit Employee** (`/employees/<id>/edit/`) - Update employee
- **Delete Employee** (`/employees/<id>/delete/`) - Remove employee
- **Sync to Device** (`/employees/sync-to-device/`) - Upload employees to K40
- **Sync from Device** (`/employees/sync-from-device/`) - Download from K40

### 3. Attendance Views
- **List Events** (`/attendance/`) - Show all events with filters
- **Download Events** (`/attendance/download/`) - Fetch from device
- **Reports** (`/attendance/reports/`) - Generate attendance reports
- **Export** (`/attendance/export/`) - Export to CSV

### 4. Management Commands
- `python manage.py test_device <id>` - Test device connection
- `python manage.py sync_attendance` - Download attendance events
- `python manage.py sync_employees` - Sync employees with device

## Settings Configuration

Add to `settings.py`:

```python
# ZKTeco Device Settings
ZK_TEST_MODE = os.getenv('ZK_TEST_MODE', 'True').lower() == 'true'

# Background task settings (Django-Q)
Q_CLUSTER = {
    'name': 'zkteco',
    'workers': 2,
    'timeout': 300,
    'retry': 600,
    'queue_limit': 50,
    'bulk': 10,
    'orm': 'default',
}
```

## Environment Variables (.env.example)

```bash
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=sqlite:///db.sqlite3

# ZKTeco Settings
ZK_TEST_MODE=True

# When ready for real device, set:
# ZK_TEST_MODE=False
# DEVICE_IP=192.168.1.201
# DEVICE_PORT=4370
```

## Installation Requirements (requirements.txt)

```
Django>=4.2.0
pyzk>=0.9
python-dotenv>=1.0.0
django-crispy-forms>=2.0
crispy-bootstrap5>=0.7
django-q>=1.3.9
openpyxl>=3.1.0
```

## Build Instructions for Claude Code

1. Create Django project structure
2. Implement all models with migrations
3. Create mock implementation (MockZK, MockConnection)
4. Build ZKDeviceConnector wrapper
5. Implement all views (device, employee, attendance)
6. Create Bootstrap 5 templates
7. Add Django admin configuration
8. Create management commands
9. Write tests using mock data
10. Create comprehensive README with setup instructions

## Testing Strategy

- All tests should use MOCK mode by default
- Test device operations without real hardware
- Test employee CRUD operations
- Test attendance event processing
- Test synchronization logic with mock data

## Success Criteria

✅ Project runs with `python manage.py runserver`  
✅ All features work with mock data  
✅ Can add/edit/delete employees via web interface  
✅ Can view mock attendance events  
✅ Clear documentation on switching to real device  
✅ Tests pass with mock data  
✅ Management commands work  

## Post-Build Steps (for user with real device)

1. Set `ZK_TEST_MODE=False` in `.env`
2. Add real K40 device via admin panel
3. Test connection: `python manage.py test_device 1 --real`
4. Sync employees: `python manage.py sync_employees`
5. Download attendance: `python manage.py sync_attendance`
