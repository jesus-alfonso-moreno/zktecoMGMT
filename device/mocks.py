"""
Mock implementation of ZKTeco device for development without physical hardware
"""
from datetime import datetime, timedelta
import random


class MockUser:
    """Mock user object matching pyzk User structure"""
    def __init__(self, uid, name, privilege, password, group_id, user_id):
        self.uid = uid
        self.name = name
        self.privilege = privilege
        self.password = password
        self.group_id = group_id
        self.user_id = user_id


class MockAttendance:
    """Mock attendance object matching pyzk Attendance structure"""
    def __init__(self, user_id, timestamp, punch):
        self.user_id = user_id
        self.timestamp = timestamp
        self.punch = punch
        self.status = 0


class MockConnection:
    """Mock connection object that simulates device responses"""

    def __init__(self):
        # Generate fake users
        self.users = [
            MockUser(1, "John Doe", 0, "", "0", "EMP001"),
            MockUser(2, "Jane Smith", 0, "", "0", "EMP002"),
            MockUser(3, "Bob Johnson", 0, "", "0", "EMP003"),
            MockUser(4, "Alice Williams", 14, "", "0", "EMP004"),
            MockUser(5, "Charlie Brown", 0, "", "0", "EMP005"),
        ]

        # Generate fake attendance for last 7 days
        self.attendance = []
        base_time = datetime.now() - timedelta(days=7)
        for day in range(7):
            for user_id in [1, 2, 3, 4, 5]:
                # Skip some days randomly to make it realistic
                if random.random() > 0.1:  # 90% attendance rate
                    # Check in
                    check_in = base_time + timedelta(
                        days=day,
                        hours=9,
                        minutes=random.randint(0, 30)
                    )
                    self.attendance.append(MockAttendance(user_id, check_in, 0))

                    # Check out
                    check_out = base_time + timedelta(
                        days=day,
                        hours=17,
                        minutes=random.randint(0, 30)
                    )
                    self.attendance.append(MockAttendance(user_id, check_out, 1))

    def get_users(self):
        """Return mock users"""
        print("[MOCK] Getting users from device")
        return self.users

    def set_user(self, uid, name, privilege, password, group_id, user_id):
        """Simulate setting user on device"""
        print(f"[MOCK] Would set user: {name} (uid={uid})")
        return True

    def delete_user(self, uid):
        """Simulate deleting user from device"""
        print(f"[MOCK] Would delete user with uid={uid}")
        return True

    def get_attendance(self):
        """Return mock attendance records"""
        print("[MOCK] Getting attendance records from device")
        return self.attendance

    def clear_attendance(self):
        """Simulate clearing attendance from device"""
        print("[MOCK] Would clear attendance records")
        return True

    def get_serialnumber(self):
        """Return mock serial number"""
        return "MOCK-K40-12345"

    def get_firmware_version(self):
        """Return mock firmware version"""
        return "Ver 6.60 Apr 28 2018"

    def get_platform(self):
        """Return mock platform info"""
        return "ZEM560"

    def disable_device(self):
        """Simulate disabling device"""
        print("[MOCK] Device disabled")
        return True

    def enable_device(self):
        """Simulate enabling device"""
        print("[MOCK] Device enabled")
        return True

    def disconnect(self):
        """Simulate disconnection"""
        print("[MOCK] Disconnected from device")
        pass


class MockZK:
    """Mock ZK class matching pyzk ZK interface"""

    def __init__(self, ip, port=4370, timeout=5):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        print(f"[MOCK] Initialized MockZK for {ip}:{port}")

    def connect(self):
        """Simulate connection to device"""
        print(f"[MOCK] Connecting to {self.ip}:{self.port}")
        return MockConnection()
