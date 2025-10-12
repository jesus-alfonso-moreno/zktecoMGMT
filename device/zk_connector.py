"""
Wrapper for pyzk library with mock support for development
"""
from django.conf import settings
from .mocks import MockZK


class ZKDeviceConnector:
    """Wrapper for pyzk library with mock support"""

    def __init__(self, device, use_mock=None):
        """
        Initialize connector for a device

        Args:
            device: Device model instance
            use_mock: Override test mode (None = use settings.ZK_TEST_MODE)
        """
        self.device = device

        # Use mock if in test mode or explicitly requested
        if use_mock is None:
            use_mock = getattr(settings, 'ZK_TEST_MODE', True)

        self.use_mock = use_mock

        if use_mock:
            self.zk = MockZK(device.ip_address, device.port)
        else:
            try:
                from zk import ZK
                self.zk = ZK(device.ip_address, port=device.port, timeout=5)
            except ImportError:
                raise ImportError(
                    "pyzk library not found. Install it with: pip install pyzk"
                )

    def test_connection(self):
        """
        Test if device is reachable

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            conn = self.connect()
            conn.disconnect()
            return True, "Connection successful"
        except Exception as e:
            return False, str(e)

    def connect(self):
        """
        Connect to device

        Returns:
            Connection object
        """
        return self.zk.connect()

    def get_device_info(self, conn):
        """
        Get device serial number and firmware

        Args:
            conn: Active connection object

        Returns:
            dict: Device information
        """
        return {
            'serial_number': conn.get_serialnumber(),
            'firmware_version': conn.get_firmware_version(),
            'platform': conn.get_platform(),
        }

    def get_users(self, conn):
        """
        Download all users from device

        Args:
            conn: Active connection object

        Returns:
            list: User objects from device
        """
        return conn.get_users()

    def set_user(self, conn, uid, name, privilege, password, group_id, user_id):
        """
        Upload user to device

        Args:
            conn: Active connection object
            uid: User ID (1-65535)
            name: User name
            privilege: User privilege (0=User, 14=Admin)
            password: Device password
            group_id: Group ID
            user_id: Employee ID

        Returns:
            bool: Success status
        """
        return conn.set_user(uid, name, privilege, password, group_id, user_id)

    def delete_user(self, conn, uid):
        """
        Delete user from device

        Args:
            conn: Active connection object
            uid: User ID to delete

        Returns:
            bool: Success status
        """
        return conn.delete_user(uid)

    def get_attendance(self, conn):
        """
        Download attendance events

        Args:
            conn: Active connection object

        Returns:
            list: Attendance objects from device
        """
        return conn.get_attendance()

    def clear_attendance(self, conn):
        """
        Clear attendance records from device

        Args:
            conn: Active connection object

        Returns:
            bool: Success status
        """
        return conn.clear_attendance()

    def disable_device(self, conn):
        """Disable device (for operations)"""
        return conn.disable_device()

    def enable_device(self, conn):
        """Enable device"""
        return conn.enable_device()
