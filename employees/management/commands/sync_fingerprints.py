"""
Management command to sync fingerprint templates between device and database
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from device.models import Device
from device.zk_connector import ZKDeviceConnector
from employees.models import Employee, Fingerprint


class Command(BaseCommand):
    help = 'Sync fingerprint templates between device and database'

    def add_arguments(self, parser):
        parser.add_argument(
            'device_id',
            type=int,
            help='Device ID to sync with'
        )
        parser.add_argument(
            '--employee',
            type=int,
            help='Specific employee ID to sync (default: all employees)'
        )
        parser.add_argument(
            '--direction',
            choices=['from', 'to', 'both'],
            default='from',
            help='Sync direction: from (device→db), to (db→device), both'
        )
        parser.add_argument(
            '--real',
            action='store_true',
            help='Use real device (override ZK_TEST_MODE setting)'
        )

    def handle(self, *args, **options):
        device_id = options['device_id']
        employee_id = options.get('employee')
        direction = options['direction']
        use_real = options['real']

        # Get device
        try:
            device = Device.objects.get(pk=device_id)
        except Device.DoesNotExist:
            raise CommandError(f'Device with ID {device_id} does not exist')

        self.stdout.write(f'Using device: {device.name} ({device.ip_address})')

        # Get employees to sync
        if employee_id:
            try:
                employees = [Employee.objects.get(pk=employee_id)]
                self.stdout.write(f'Syncing single employee: {employees[0].full_name}')
            except Employee.DoesNotExist:
                raise CommandError(f'Employee with ID {employee_id} does not exist')
        else:
            employees = Employee.objects.filter(is_active=True)
            self.stdout.write(f'Syncing {employees.count()} active employees')

        # Initialize connector
        use_mock = not use_real
        connector = ZKDeviceConnector(device, use_mock=use_mock)
        mode = "REAL" if use_real else "MOCK"
        self.stdout.write(f'Mode: {mode}')

        # Execute sync based on direction
        if direction in ['from', 'both']:
            self.sync_from_device(connector, device, employees)

        if direction in ['to', 'both']:
            self.sync_to_device(connector, device, employees)

        self.stdout.write(self.style.SUCCESS('✓ Fingerprint sync completed'))

    def sync_from_device(self, connector, device, employees):
        """Download fingerprints from device to database"""
        self.stdout.write('\n--- Downloading fingerprints FROM device ---')

        try:
            conn = connector.connect()
            total_downloaded = 0

            for employee in employees:
                self.stdout.write(f'\nEmployee: {employee.full_name} (UID: {employee.user_id})')

                # Download all fingerprint templates (0-9)
                templates = connector.get_all_fingerprint_templates(conn, employee.user_id)

                if not templates:
                    self.stdout.write('  No fingerprints found on device')
                    continue

                # Save to database
                with transaction.atomic():
                    for temp_id, template_data in templates.items():
                        Fingerprint.objects.update_or_create(
                            employee=employee,
                            finger_index=temp_id,
                            defaults={
                                'template': template_data,
                                'device': device
                            }
                        )
                        finger_name = self.get_finger_name(temp_id)
                        self.stdout.write(f'  ✓ Downloaded: {finger_name} ({len(template_data)} bytes)')
                        total_downloaded += 1

            conn.disconnect()

            self.stdout.write(
                self.style.SUCCESS(f'\n✓ Downloaded {total_downloaded} fingerprint templates')
            )

        except Exception as e:
            raise CommandError(f'Error downloading fingerprints: {str(e)}')

    def sync_to_device(self, connector, device, employees):
        """Upload fingerprints from database to device"""
        self.stdout.write('\n--- Uploading fingerprints TO device ---')

        try:
            conn = connector.connect()
            total_uploaded = 0

            for employee in employees:
                fingerprints = Fingerprint.objects.filter(employee=employee)

                if not fingerprints.exists():
                    self.stdout.write(
                        f'\n{employee.full_name}: No fingerprints in database'
                    )
                    continue

                self.stdout.write(f'\nEmployee: {employee.full_name} (UID: {employee.user_id})')

                for fingerprint in fingerprints:
                    try:
                        result = connector.set_fingerprint_template(
                            conn,
                            employee.user_id,
                            fingerprint.finger_index,
                            fingerprint.template
                        )

                        if result:
                            finger_name = self.get_finger_name(fingerprint.finger_index)
                            self.stdout.write(f'  ✓ Uploaded: {finger_name}')
                            total_uploaded += 1
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'  ✗ Failed: {self.get_finger_name(fingerprint.finger_index)}'
                                )
                            )

                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'  ✗ Error uploading fingerprint: {str(e)}')
                        )

            conn.disconnect()

            self.stdout.write(
                self.style.SUCCESS(f'\n✓ Uploaded {total_uploaded} fingerprint templates')
            )

        except Exception as e:
            raise CommandError(f'Error uploading fingerprints: {str(e)}')

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
