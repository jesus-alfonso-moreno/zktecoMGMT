# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Django web application for managing ZKTeco K40 biometric attendance devices. The system manages devices, syncs employee data, tracks attendance events, and generates reports.

**Key Feature**: The project includes a MOCK mode for development without physical hardware. All device operations can be tested using simulated data.

## Development Commands

### Setup and Installation

```bash
# First time setup
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

### Testing

```bash
# Run all tests
python manage.py test

# Test specific app
python manage.py test device
python manage.py test employees
python manage.py test attendance

# Test device connection (uses mock by default)
python manage.py test_device 1

# Test with real device
python manage.py test_device 1 --real
```

### Database Operations

```bash
# Create migrations after model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Access Django shell
python manage.py shell

# Reset database (SQLite)
rm db.sqlite3
python manage.py migrate
```

### Management Commands

```bash
# Sync employees with device
python manage.py sync_employees <device_id> --direction=both

# Download attendance from device
python manage.py sync_attendance <device_id>

# Clear device attendance after download
python manage.py sync_attendance <device_id> --clear
```

## Architecture

### App Structure

The project follows Django's app-based architecture with three main apps:

1. **device**: Manages ZKTeco K40 device configurations and connections
2. **employees**: Handles employee records and synchronization with devices
3. **attendance**: Tracks attendance events and generates reports

### Key Design Patterns

**Mock/Real Device Abstraction**: The `ZKDeviceConnector` class (device/zk_connector.py) provides a unified interface that automatically switches between MockZK and real pyzk ZK class based on the `ZK_TEST_MODE` setting.

**Connector Pattern**: `device/zk_connector.py` wraps the pyzk library, providing:
- Consistent error handling
- Mock mode support
- Simplified device operations
- Connection management

**Service Layer**: Each app has views that use the connector to perform device operations:
- Device operations are isolated in the connector
- Views handle HTTP and user interaction
- Models handle data persistence

### Database Relationships

```
Device (1) ─── (M) Employee
Device (1) ─── (M) AttendanceEvent
Employee (1) ─── (M) Fingerprint
Employee (1) ─── (M) AttendanceEvent
```

**Important**: AttendanceEvent links to both Device (required) and Employee (optional) because events may exist for users not in the local database.

### Mock Implementation

**Location**: `device/mocks.py`

The mock system simulates:
- MockZK class (mimics pyzk ZK interface)
- MockConnection (mimics device connection)
- MockUser, MockAttendance (mimics device data)
- Realistic sample data (5 employees, 7 days of attendance)

**Usage**: All features work identically in mock and real mode. Mock mode is enabled by default via `ZK_TEST_MODE=True` in settings.

## File Organization

### Critical Files

- **device/zk_connector.py**: Main abstraction layer for device communication
- **device/mocks.py**: Complete mock implementation for development
- **zkteco_project/settings.py**: Django settings including `ZK_TEST_MODE`
- **requirements.txt**: Python dependencies

### Models

- **device/models.py**: Device model (IP, port, serial number, etc.)
- **employees/models.py**: Employee and Fingerprint models
- **attendance/models.py**: AttendanceEvent model with indexes

### Views

All apps use Django class-based views where appropriate:
- ListView for listing with pagination
- CreateView/UpdateView for forms
- DeleteView for confirmations
- Function views for custom operations (sync, download, export)

### Templates

Bootstrap 5 templates with:
- **templates/base.html**: Base layout with navbar, messages, footer
- App-specific templates in templates/{app}/ folders
- Responsive design with Bootstrap utilities

## Common Development Tasks

### Adding a New Device Field

1. Update `device/models.py` - add field to Device model
2. Update `device/forms.py` - add field to DeviceForm if user-editable
3. Create migration: `python manage.py makemigrations device`
4. Apply migration: `python manage.py migrate`
5. Update templates if field should be displayed
6. Update admin.py if needed

### Adding a New Report Type

1. Add report logic to `attendance/reports.py`
2. Add view handler in `attendance/views.py`
3. Update `attendance/urls.py` if new URL needed
4. Create/update template in `templates/attendance/`
5. Add navigation link in templates

### Modifying Mock Data

Edit `device/mocks.py`:
- **MockConnection.__init__()**: Modify sample employees
- **MockConnection.__init__()**: Modify attendance generation logic
- Keep mock data realistic for testing

### Switching Between Mock and Real Mode

**Mock Mode** (default):
```bash
# In .env
ZK_TEST_MODE=True
```

**Real Mode**:
```bash
# In .env
ZK_TEST_MODE=False
```

**Per-command override**:
```bash
python manage.py test_device 1 --real
python manage.py sync_employees 1 --real
```

## Important Conventions

### User ID vs Employee ID

- **user_id**: Integer (1-65535) used by the ZKTeco device
- **employee_id**: String (e.g., "EMP001") used for human-readable identification
- Both must be unique

### Device Operations Pattern

Always use try/except when connecting to devices:

```python
connector = ZKDeviceConnector(device)
try:
    conn = connector.connect()
    # perform operations
    conn.disconnect()
except Exception as e:
    # handle error
```

### Sync Status

Employees have a `synced_to_device` boolean:
- Set to `True` after successful upload to device
- Set to `False` when employee data changes
- Helps track which employees need syncing

## Environment Variables

Set in `.env` file:

- **ZK_TEST_MODE**: `True` for mock, `False` for real devices
- **SECRET_KEY**: Django secret key (required for production)
- **DEBUG**: `True` for development, `False` for production
- **ALLOWED_HOSTS**: Comma-separated list of allowed hosts

## Testing Strategy

The project is designed to work fully in mock mode:
- All tests should pass without physical devices
- Tests use `ZK_TEST_MODE=True` automatically
- Mock data provides realistic scenarios

## Production Considerations

When deploying to production:

1. Set `ZK_TEST_MODE=False`
2. Use PostgreSQL instead of SQLite
3. Set `DEBUG=False`
4. Configure ALLOWED_HOSTS
5. Use Gunicorn/uWSGI with Nginx
6. Set up Django-Q workers for background tasks
7. Configure proper logging
8. Use environment variables for secrets

## Dependencies

### Critical Dependencies

- **Django 4.2+**: Web framework
- **pyzk**: ZKTeco device communication library
- **python-dotenv**: Environment variable management
- **django-crispy-forms + crispy-bootstrap5**: Form rendering

### Optional Dependencies

- **django-q**: Background task processing (for scheduled syncs)
- **openpyxl**: Excel export (if adding Excel report feature)

## Troubleshooting

### Common Issues

**"No module named 'django'"**: Virtual environment not activated
```bash
source venv/bin/activate
```

**"Connection refused"**:
- Check device IP and port
- Verify network connectivity
- Confirm ZK_TEST_MODE setting

**"User ID must be unique"**: Each employee needs unique user_id (1-65535)

**"Employee not syncing"**:
- Check employee is active (`is_active=True`)
- Verify device connection first
- Check device has available memory

## Code Style

- Follow PEP 8 for Python code
- Use Django naming conventions (models: PascalCase, views: snake_case)
- Add docstrings to classes and complex functions
- Keep views thin, move business logic to models or separate services
- Use meaningful variable names
- Add comments for complex device operations
