"""
Wrapper for pyzk library with mock support for development
"""
import logging
import time
from django.conf import settings
from .mocks import MockZK

logger = logging.getLogger('device.auth')

# Import Finger class for real device operations
try:
    from zk.finger import Finger
except ImportError:
    Finger = None


class ZKDeviceConnector:
    """Wrapper for pyzk library with mock support"""

    def __init__(self, device, use_mock=None, user=None, ip_address=None):
        """
        Initialize connector for a device

        Args:
            device: Device model instance
            use_mock: Override test mode (None = use settings.ZK_TEST_MODE)
            user: User instance for logging
            ip_address: User's IP address for logging
        """
        self.device = device
        self.user = user
        self.ip_address = ip_address

        # Use mock if in test mode or explicitly requested
        if use_mock is None:
            use_mock = getattr(settings, 'ZK_TEST_MODE', True)

        self.use_mock = use_mock

        mode = "MOCK" if use_mock else "REAL"
        logger.info(f"Initializing {mode} connector for device {device.name} ({device.ip_address})")

        if use_mock:
            self.zk = MockZK(device.ip_address, device.port)
        else:
            try:
                from zk import ZK

                # Parse password - convert to int if numeric, otherwise use 0
                password = 0
                if device.password:
                    try:
                        password = int(device.password)
                    except ValueError:
                        logger.warning(f"Invalid password format for device {device.name}, using 0")

                self.zk = ZK(
                    ip=device.ip_address,
                    port=device.port,
                    timeout=5,
                    password=password,
                    force_udp=device.force_udp,
                    ommit_ping=device.ommit_ping
                )

                # Log connection parameters
                conn_info = []
                if password != 0:
                    conn_info.append("password authentication")
                if device.force_udp:
                    conn_info.append("UDP protocol")
                if device.ommit_ping:
                    conn_info.append("ping omitted")

                if conn_info:
                    logger.info(f"Connection options for {device.name}: {', '.join(conn_info)}")

            except ImportError:
                logger.error("pyzk library not found")
                raise ImportError(
                    "pyzk library not found. Install it with: pip install pyzk"
                )

    def _log_to_database(self, action, status, message, details=None, duration=None):
        """
        Log operation to database

        Args:
            action: Action type (from DeviceLog.ACTION_CHOICES)
            status: Status (success/failed/error)
            message: Log message
            details: Additional details dict
            duration: Operation duration in seconds
        """
        try:
            from .models import DeviceLog
            DeviceLog.objects.create(
                device=self.device,
                action=action,
                status=status,
                user=self.user,
                message=message,
                details=details or {},
                ip_address=self.ip_address,
                duration=duration
            )
        except Exception as e:
            logger.error(f"Failed to log to database: {e}")

    def test_connection(self):
        """
        Test if device is reachable

        Returns:
            tuple: (success: bool, message: str)
        """
        start_time = time.time()
        logger.info(f"Testing connection to device {self.device.name}")

        try:
            conn = self.connect()
            conn.disconnect()
            duration = time.time() - start_time

            message = "Connection successful"
            logger.info(f"✓ {message} (took {duration:.2f}s)")
            self._log_to_database('test', 'success', message, duration=duration)

            return True, message
        except Exception as e:
            duration = time.time() - start_time
            message = str(e)

            logger.error(f"✗ Connection failed: {message}")
            self._log_to_database('test', 'failed', message, duration=duration)

            return False, message

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

    # Fingerprint management methods

    def enroll_user_fingerprint(self, conn, uid, temp_id):
        """
        Start fingerprint enrollment on device for specific finger

        Args:
            conn: Active connection object
            uid: User ID (must exist on device)
            temp_id: Finger slot (0-9, see FINGER_MAP)

        Returns:
            bool: Success status
        """
        logger.info(f"[FINGERPRINT_ENROLL] Starting enrollment for user {uid}, finger {temp_id}")
        logger.debug(f"[FINGERPRINT_ENROLL] Device: {self.device.name} ({self.device.ip_address}), Mode: {'MOCK' if self.use_mock else 'REAL'}")

        try:
            result = conn.enroll_user(uid, temp_id=temp_id)
            logger.info(f"[FINGERPRINT_ENROLL] ✓ Enrollment initiated successfully for user {uid}, finger {temp_id}")
            logger.info(f"[FINGERPRINT_ENROLL] User should now scan finger on device")
            return result
        except Exception as e:
            logger.error(f"[FINGERPRINT_ENROLL] ✗ Failed to start enrollment for user {uid}, finger {temp_id}: {type(e).__name__}: {str(e)}")
            logger.exception(f"[FINGERPRINT_ENROLL] Full traceback:")
            raise

    def get_fingerprint_template(self, conn, uid, temp_id):
        """
        Download fingerprint template from device

        Args:
            conn: Active connection object
            uid: User ID
            temp_id: Finger slot (0-9)

        Returns:
            bytes: Template data or None if not found
        """
        logger.debug(f"[FINGERPRINT_DOWNLOAD] Requesting template for user {uid}, finger {temp_id}")

        try:
            result = conn.get_user_template(uid, temp_id)

            if result:
                # Real device returns Finger object, extract template data
                if hasattr(result, 'template'):
                    logger.debug(f"[FINGERPRINT_DOWNLOAD] Received Finger object, extracting template data")
                    template = result.template
                    logger.info(f"[FINGERPRINT_DOWNLOAD] ✓ Downloaded template for user {uid}, finger {temp_id}: {len(template)} bytes")
                    logger.debug(f"[FINGERPRINT_DOWNLOAD] Finger object: uid={result.uid}, fid={result.fid}, valid={result.valid}")
                    return template
                else:
                    # Mock or direct bytes
                    logger.debug(f"[FINGERPRINT_DOWNLOAD] Received direct template data")
                    logger.info(f"[FINGERPRINT_DOWNLOAD] ✓ Downloaded template for user {uid}, finger {temp_id}: {len(result)} bytes")
                    logger.debug(f"[FINGERPRINT_DOWNLOAD] Template type: {type(result)}")
                    return result
            else:
                logger.debug(f"[FINGERPRINT_DOWNLOAD] No template found for user {uid}, finger {temp_id}")
                return None
        except Exception as e:
            logger.error(f"[FINGERPRINT_DOWNLOAD] ✗ Error downloading template for user {uid}, finger {temp_id}: {type(e).__name__}: {str(e)}")
            logger.exception(f"[FINGERPRINT_DOWNLOAD] Full traceback:")
            raise

    def get_all_fingerprint_templates(self, conn, uid):
        """
        Download all fingerprint templates for a user (slots 0-9)

        Args:
            conn: Active connection object
            uid: User ID

        Returns:
            dict: {temp_id: template_data} for all enrolled fingers
        """
        logger.info(f"[FINGERPRINT_DOWNLOAD_ALL] Starting bulk download for user {uid}")
        templates = {}

        try:
            for temp_id in range(10):
                template = self.get_fingerprint_template(conn, uid, temp_id)
                if template:
                    templates[temp_id] = template

            logger.info(f"[FINGERPRINT_DOWNLOAD_ALL] ✓ Downloaded {len(templates)} templates for user {uid}")
            if templates:
                logger.debug(f"[FINGERPRINT_DOWNLOAD_ALL] Finger slots with templates: {list(templates.keys())}")

            return templates
        except Exception as e:
            logger.error(f"[FINGERPRINT_DOWNLOAD_ALL] ✗ Error during bulk download for user {uid}: {type(e).__name__}: {str(e)}")
            logger.exception(f"[FINGERPRINT_DOWNLOAD_ALL] Full traceback:")
            raise

    def set_fingerprint_template(self, conn, uid, temp_id, template):
        """
        Upload fingerprint template to device

        Args:
            conn: Active connection object
            uid: User ID
            temp_id: Finger slot (0-9)
            template: Binary template data (bytes, memoryview, or Finger object)

        Returns:
            bool: Success status
        """
        logger.info(f"[FINGERPRINT_UPLOAD] Starting upload for user {uid}, finger {temp_id}")
        logger.debug(f"[FINGERPRINT_UPLOAD] Template type: {type(template)}, size: {len(template) if template else 0} bytes")
        logger.debug(f"[FINGERPRINT_UPLOAD] Mode: {'MOCK' if self.use_mock else 'REAL'}, Finger class available: {Finger is not None}")

        try:
            # If using real device and Finger class is available, create Finger object
            if not self.use_mock and Finger is not None:
                logger.debug(f"[FINGERPRINT_UPLOAD] Using Finger object for real device")

                # Ensure template is bytes (not memoryview or other type)
                original_type = type(template)
                if isinstance(template, memoryview):
                    logger.debug(f"[FINGERPRINT_UPLOAD] Converting memoryview to bytes")
                    template = template.tobytes()
                elif not isinstance(template, bytes):
                    logger.debug(f"[FINGERPRINT_UPLOAD] Converting {original_type} to bytes")
                    template = bytes(template)

                logger.debug(f"[FINGERPRINT_UPLOAD] Template after conversion: {type(template)}, size: {len(template)}")

                # Create Finger object for pyzk library
                finger = Finger(uid=uid, fid=temp_id, valid=1, template=template)
                logger.debug(f"[FINGERPRINT_UPLOAD] Created Finger object: uid={finger.uid}, fid={finger.fid}, valid={finger.valid}")

                result = conn.set_user_template(finger)
                logger.info(f"[FINGERPRINT_UPLOAD] ✓ Successfully uploaded template for user {uid}, finger {temp_id}")
                return result
            else:
                # Mock mode or fallback - use direct template
                logger.debug(f"[FINGERPRINT_UPLOAD] Using direct template (mock mode)")

                if isinstance(template, memoryview):
                    template = template.tobytes()
                elif not isinstance(template, bytes):
                    template = bytes(template)

                result = conn.set_user_template(uid, temp_id, valid=1, template=template)
                logger.info(f"[FINGERPRINT_UPLOAD] ✓ Successfully uploaded template (mock) for user {uid}, finger {temp_id}")
                return result

        except Exception as e:
            logger.error(f"[FINGERPRINT_UPLOAD] ✗ Failed to upload template for user {uid}, finger {temp_id}: {type(e).__name__}: {str(e)}")
            logger.exception(f"[FINGERPRINT_UPLOAD] Full traceback:")
            raise

    def delete_fingerprint_template(self, conn, uid, temp_id):
        """
        Delete fingerprint from device

        Args:
            conn: Active connection object
            uid: User ID
            temp_id: Finger slot (0-9)

        Returns:
            bool: Success status
        """
        logger.info(f"[FINGERPRINT_DELETE] Deleting template for user {uid}, finger {temp_id}")

        try:
            result = conn.delete_user_template(uid, temp_id)
            logger.info(f"[FINGERPRINT_DELETE] ✓ Successfully deleted template for user {uid}, finger {temp_id}")
            return result
        except Exception as e:
            logger.error(f"[FINGERPRINT_DELETE] ✗ Error deleting template for user {uid}, finger {temp_id}: {type(e).__name__}: {str(e)}")
            logger.exception(f"[FINGERPRINT_DELETE] Full traceback:")
            raise
