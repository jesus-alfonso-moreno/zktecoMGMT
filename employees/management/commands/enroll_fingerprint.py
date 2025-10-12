"""
Management command to start fingerprint enrollment on device
"""
from django.core.management.base import BaseCommand, CommandError
from device.models import Device
from device.zk_connector import ZKDeviceConnector
from employees.models import Employee


class Command(BaseCommand):
    help = 'Start fingerprint enrollment on device for an employee'

    def add_arguments(self, parser):
        parser.add_argument(
            'employee_id',
            type=int,
            help='Employee ID to enroll fingerprint for'
        )
        parser.add_argument(
            'device_id',
            type=int,
            help='Device ID to use for enrollment'
        )
        parser.add_argument(
            '--finger',
            type=int,
            required=True,
            choices=range(10),
            metavar='{0-9}',
            help='Finger index (0-9): 0=L.thumb, 1=L.index, 2=L.middle, 3=L.ring, 4=L.pinky, '
                 '5=R.thumb, 6=R.index, 7=R.middle, 8=R.ring, 9=R.pinky'
        )
        parser.add_argument(
            '--real',
            action='store_true',
            help='Use real device (override ZK_TEST_MODE setting)'
        )

    def handle(self, *args, **options):
        employee_id = options['employee_id']
        device_id = options['device_id']
        temp_id = options['finger']
        use_real = options['real']

        # Get employee
        try:
            employee = Employee.objects.get(pk=employee_id)
        except Employee.DoesNotExist:
            raise CommandError(f'Employee with ID {employee_id} does not exist')

        # Get device
        try:
            device = Device.objects.get(pk=device_id)
        except Device.DoesNotExist:
            raise CommandError(f'Device with ID {device_id} does not exist')

        # Get finger name
        finger_name = self.get_finger_name(temp_id)

        self.stdout.write('=' * 60)
        self.stdout.write('Fingerprint Enrollment')
        self.stdout.write('=' * 60)
        self.stdout.write(f'Employee: {employee.full_name} (UID: {employee.user_id})')
        self.stdout.write(f'Device: {device.name} ({device.ip_address})')
        self.stdout.write(f'Finger: {finger_name} (temp_id: {temp_id})')

        # Initialize connector
        use_mock = not use_real
        connector = ZKDeviceConnector(device, use_mock=use_mock)
        mode = "REAL" if use_real else "MOCK"
        self.stdout.write(f'Mode: {mode}\n')

        try:
            conn = connector.connect()
            self.stdout.write(self.style.SUCCESS('✓ Connected to device'))

            # Check if fingerprint already exists
            existing = connector.get_fingerprint_template(conn, employee.user_id, temp_id)
            if existing:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠ Fingerprint already exists for {finger_name}. It will be replaced.'
                    )
                )
                # Delete existing template
                connector.delete_fingerprint_template(conn, employee.user_id, temp_id)
                self.stdout.write('  Deleted existing template')

            # Start enrollment
            self.stdout.write(f'\nStarting enrollment for {finger_name}...')
            result = connector.enroll_user_fingerprint(conn, employee.user_id, temp_id)

            if result:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✓ Enrollment initiated successfully!\n'
                    )
                )
                self.stdout.write('INSTRUCTIONS:')
                self.stdout.write('1. Go to the physical device')
                self.stdout.write(f'2. Place your {finger_name.lower()} on the scanner')
                self.stdout.write('3. Follow the device prompts (usually scan 3 times)')
                self.stdout.write('4. Wait for device confirmation beep/flash')
                self.stdout.write('\nAfter enrollment completes on device, run:')
                self.stdout.write(
                    self.style.WARNING(
                        f'  python manage.py sync_fingerprints {device_id} '
                        f'--employee={employee_id} --direction=from'
                    )
                )
            else:
                raise CommandError('Failed to start enrollment on device')

            conn.disconnect()
            self.stdout.write(self.style.SUCCESS('\n✓ Disconnected from device'))

        except Exception as e:
            raise CommandError(f'Error during enrollment: {str(e)}')

    def get_finger_name(self, temp_id):
        """Get human-readable finger name"""
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
        }
        return FINGER_MAP.get(temp_id, f"Finger {temp_id}")
