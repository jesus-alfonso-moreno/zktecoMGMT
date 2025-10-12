# Quick Start Guide

Get the ZKTeco K40 Django application running in 5 minutes!

## Prerequisites

- Python 3.10+ installed
- Basic terminal/command line knowledge

## Installation Steps

### 1. Create Virtual Environment

```bash
python3 -m venv venv
```

### 2. Activate Virtual Environment

**Linux/Mac:**
```bash
source venv/bin/activate
```

**Windows:**
```cmd
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment

```bash
cp .env.example .env
```

The default `.env` has `ZK_TEST_MODE=True` which enables mock mode for testing without hardware.

### 5. Initialize Database

```bash
python manage.py migrate
```

### 6. Create Admin User

```bash
python manage.py createsuperuser
```

Follow the prompts to create your admin account (username, email, password).

### 7. Run the Server

```bash
python manage.py runserver
```

### 8. Access the Application

Open your browser and visit:

- **Main App**: http://127.0.0.1:8000
- **Admin Panel**: http://127.0.0.1:8000/admin

## First Steps in the App

### 1. Add a Device

1. Go to **Devices** → **Add Device**
2. Enter:
   - Name: "Test Device"
   - IP Address: 192.168.1.201 (any valid IP in mock mode)
   - Port: 4370
3. Click **Save Device**
4. Click the **Test Connection** button to verify (it will succeed in mock mode)

### 2. View Mock Employees

1. Click **Employees** → **Sync FROM Device**
2. Select your device from dropdown
3. Click **Sync FROM Device**
4. You'll see 5 mock employees imported

### 3. View Mock Attendance

1. Go to **Attendance** → **Download Events**
2. Select your device
3. Click **Download Events**
4. View 7 days of sample attendance data

### 4. Generate a Report

1. Go to **Attendance** → **Reports**
2. Select report type (Daily/Weekly/Monthly)
3. Pick a date
4. Click **Generate Report**

## Testing CLI Commands

### Test Device Connection
```bash
python manage.py test_device 1
```

### Sync Employees
```bash
python manage.py sync_employees 1 --direction=both
```

### Download Attendance
```bash
python manage.py sync_attendance 1
```

## Using with Real Devices

When ready to connect to actual ZKTeco K40 devices:

1. Edit `.env` and set:
   ```
   ZK_TEST_MODE=False
   ```

2. Add your real device with correct IP address

3. Use `--real` flag with CLI commands:
   ```bash
   python manage.py test_device 1 --real
   ```

## Troubleshooting

**"No module named 'django'"**
- Make sure virtual environment is activated: `source venv/bin/activate`

**"Port already in use"**
- Use a different port: `python manage.py runserver 8001`

**"Cannot connect to device"**
- In mock mode, connections always succeed
- In real mode, check device IP, network, and firewall

## Next Steps

- Read the full **README.md** for detailed documentation
- Check **CLAUDE.md** for development guidance
- Explore the Django admin panel for database management
- Try exporting attendance to CSV
- Customize the mock data in `device/mocks.py`

## Support

For issues, check:
1. Console output for error messages
2. README.md troubleshooting section
3. CLAUDE.md for architecture details

Enjoy managing your ZKTeco devices!
