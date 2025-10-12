# ZKTeco K40 Django Integration

A comprehensive Django web application for managing ZKTeco K40 biometric attendance devices. This system allows you to manage devices, sync employee data, track attendance events, and generate detailed reports.

## Features

- **Device Management**: Configure and test connections to multiple ZKTeco K40 devices
- **Employee Management**: Create, update, and sync employee data with biometric devices
- **Attendance Tracking**: Download and view attendance events from devices
- **Reports**: Generate daily, weekly, and monthly attendance reports
- **Mock Mode**: Full development and testing capability without physical hardware
- **Web Interface**: User-friendly Bootstrap 5 interface for all operations
- **Export**: Export attendance data to CSV format
- **CLI Commands**: Management commands for automation and scripting

## Technology Stack

- **Backend**: Python 3.10+, Django 4.2+
- **Device Library**: pyzk (ZKTeco device communication)
- **Database**: SQLite (development), PostgreSQL (production-ready)
- **Frontend**: Bootstrap 5 with Django templates
- **Background Tasks**: Django-Q for periodic synchronization

## Installation

### 1. Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### 2. Clone and Setup

```bash
cd zktecoMGMT
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Edit `.env` and set your values:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ZK_TEST_MODE=True  # Set to False when using real devices
```

### 4. Database Setup

Run migrations to create the database:

```bash
python manage.py migrate
```

### 5. Create Admin User

```bash
python manage.py createsuperuser
```

Follow the prompts to create your admin account.

### 6. Run Development Server

```bash
python manage.py runserver
```

Visit http://127.0.0.1:8000 in your browser.

## Usage

### Mock Mode (Development)

By default, the system runs in **MOCK mode** with simulated device data. This allows you to:

- Test all features without a physical device
- Develop and demo the system
- View simulated employees and attendance data

Mock mode generates:
- 5 sample employees
- 7 days of attendance events
- Realistic check-in/check-out patterns

### Working with Real Devices

To connect to actual ZKTeco K40 devices:

1. **Update Environment**:
   ```bash
   # In .env file
   ZK_TEST_MODE=False
   ```

2. **Add Device**:
   - Navigate to Devices → Add Device
   - Enter device IP address and port (default: 4370)
   - Click "Save Device"

3. **Test Connection**:
   ```bash
   python manage.py test_device 1 --real
   ```

4. **Sync Employees**:
   ```bash
   python manage.py sync_employees 1 --direction=both --real
   ```

5. **Download Attendance**:
   ```bash
   python manage.py sync_attendance 1 --real
   ```

## Web Interface

### Dashboard (`/`)
- Overview of all modules
- Quick access to devices, employees, and attendance
- System status information

### Device Management (`/device/`)
- List all configured devices
- Add/edit/delete devices
- Test device connections
- View device information (serial number, firmware)

### Employee Management (`/employees/`)
- List all employees with search and filtering
- Add/edit/delete employee records
- Sync employees TO device (upload)
- Sync employees FROM device (download)
- Track sync status

### Attendance Tracking (`/attendance/`)
- View all attendance events
- Filter by employee, device, date range
- Download attendance from devices
- Export to CSV
- Generate reports

### Admin Interface (`/admin/`)
- Full Django admin for advanced management
- Direct database access
- Bulk operations

## Management Commands

### Test Device Connection

```bash
python manage.py test_device <device_id> [--real]
```

Example:
```bash
python manage.py test_device 1
```

### Sync Employees

```bash
python manage.py sync_employees <device_id> [--direction=to|from|both] [--real]
```

Examples:
```bash
# Upload employees to device
python manage.py sync_employees 1 --direction=to

# Download employees from device
python manage.py sync_employees 1 --direction=from

# Both directions
python manage.py sync_employees 1 --direction=both
```

### Download Attendance

```bash
python manage.py sync_attendance <device_id> [--clear] [--real]
```

Examples:
```bash
# Download attendance events
python manage.py sync_attendance 1

# Download and clear device memory
python manage.py sync_attendance 1 --clear
```

## Project Structure

```
zktecoMGMT/
├── manage.py                      # Django management script
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variables template
├── README.md                      # This file
│
├── zkteco_project/                # Main project configuration
│   ├── settings.py               # Django settings
│   ├── urls.py                   # URL routing
│   └── wsgi.py                   # WSGI configuration
│
├── device/                        # Device management app
│   ├── models.py                 # Device model
│   ├── views.py                  # Device views
│   ├── mocks.py                  # Mock device implementation
│   ├── zk_connector.py           # Device connector wrapper
│   └── management/commands/
│       └── test_device.py        # Test device CLI command
│
├── employees/                     # Employee management app
│   ├── models.py                 # Employee & Fingerprint models
│   ├── views.py                  # Employee views
│   ├── forms.py                  # Employee forms
│   └── management/commands/
│       └── sync_employees.py     # Sync employees CLI command
│
├── attendance/                    # Attendance tracking app
│   ├── models.py                 # AttendanceEvent model
│   ├── views.py                  # Attendance views
│   ├── reports.py                # Report generation utilities
│   └── management/commands/
│       └── sync_attendance.py    # Sync attendance CLI command
│
├── templates/                     # HTML templates
│   ├── base.html                 # Base template
│   ├── home.html                 # Dashboard
│   ├── device/                   # Device templates
│   ├── employees/                # Employee templates
│   └── attendance/               # Attendance templates
│
└── static/                        # Static files
    └── css/
        └── custom.css            # Custom styles
```

## Database Models

### Device
Stores ZKTeco K40 device connection information:
- Name, IP address, port
- Serial number, firmware version
- Active status, last sync timestamp

### Employee
Employee/user records synced with devices:
- Employee ID, user ID (1-65535)
- Name, department
- Device password, privilege level
- Sync status, assigned device

### Fingerprint
Fingerprint templates for employees:
- Associated employee
- Finger index (0-9)
- Template data

### AttendanceEvent
Punch events downloaded from devices:
- Device, employee, timestamp
- Punch type (check in/out, break, overtime)
- Verification mode (fingerprint, card, face)

## API Endpoints

While this is primarily a web application, these AJAX endpoints are available:

- `GET /device/<id>/test/` - Test device connection (returns JSON)

## Troubleshooting

### Device Connection Issues

**Problem**: Cannot connect to device
**Solutions**:
- Verify device IP address and port
- Check network connectivity (ping device)
- Ensure device is powered on
- Verify firewall settings
- Confirm ZK_TEST_MODE setting

### Sync Issues

**Problem**: Employees not syncing
**Solutions**:
- Check device connection first
- Verify user_id is unique (1-65535)
- Ensure device has available memory
- Check employee is marked as active

### Attendance Not Downloading

**Problem**: No attendance events downloaded
**Solutions**:
- Verify device has attendance records
- Check date/time on device is correct
- Ensure employees are synced first
- Try clearing device memory after download

## Development

### Running Tests

```bash
python manage.py test
```

### Creating Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Collecting Static Files

```bash
python manage.py collectstatic
```

## Production Deployment

### PostgreSQL Setup

1. Install PostgreSQL
2. Create database:
   ```sql
   CREATE DATABASE zkteco_db;
   CREATE USER zkteco_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE zkteco_db TO zkteco_user;
   ```

3. Update `.env`:
   ```env
   DATABASE_URL=postgresql://zkteco_user:your_password@localhost/zkteco_db
   ```

### Production Settings

Update `.env` for production:
```env
DEBUG=False
SECRET_KEY=<generate-strong-secret-key>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
ZK_TEST_MODE=False
```

### Running with Gunicorn

```bash
pip install gunicorn
gunicorn zkteco_project.wsgi:application --bind 0.0.0.0:8000
```

### Nginx Configuration

Example nginx configuration:
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location /static/ {
        alias /path/to/zktecoMGMT/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
- Check the troubleshooting section
- Review device documentation
- Check pyzk library documentation: https://github.com/fananimi/pyzk

## Acknowledgments

- Built with Django framework
- Uses pyzk library for ZKTeco device communication
- Bootstrap 5 for UI components
