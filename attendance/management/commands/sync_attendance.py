"""
Management command to download attendance events from device
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from attendance.models import AttendanceEvent
from employees.models import Employee
from device.models import Device
from device.zk_connector import ZKDeviceConnector


class Command(BaseCommand):
    help = 'Download attendance events from ZKTeco device'

    def add_arguments(self, parser):
        parser.add_argument('device_id', type=int, help='Device ID to download from')
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear attendance records from device after download'
        )
        parser.add_argument(
            '--real',
            action='store_true',
            help='Use real device (ignore ZK_TEST_MODE setting)'
        )

    def handle(self, *args, **options):
        device_id = options['device_id']
        clear_device = options['clear']
        use_real = options['real']

        try:
            device = Device.objects.get(pk=device_id)
        except Device.DoesNotExist:
            raise CommandError(f'Device with ID {device_id} does not exist')

        if use_real:
            self.stdout.write(self.style.WARNING('Using REAL device mode'))
            connector = ZKDeviceConnector(device, use_mock=False)
        else:
            connector = ZKDeviceConnector(device)
            if connector.use_mock:
                self.stdout.write(self.style.WARNING('Using MOCK mode'))

        self.stdout.write(f'Downloading attendance from: {device.name} ({device.ip_address})')

        success_count = 0
        duplicate_count = 0
        error_count = 0

        try:
            conn = connector.connect()
            attendance_records = connector.get_attendance(conn)

            self.stdout.write(f'Found {len(attendance_records)} attendance records on device')

            for record in attendance_records:
                try:
                    # Try to match employee
                    employee = None
                    try:
                        employee = Employee.objects.get(user_id=record.user_id)
                    except Employee.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(f'  No employee found for user_id {record.user_id}')
                        )

                    # Create or skip if duplicate
                    event, created = AttendanceEvent.objects.get_or_create(
                        device=device,
                        user_id=record.user_id,
                        timestamp=record.timestamp,
                        defaults={
                            'employee': employee,
                            'punch_type': record.punch,
                            'verify_mode': getattr(record, 'status', 0),
                            'work_code': 0,
                        }
                    )

                    if created:
                        success_count += 1
                        emp_name = employee.full_name if employee else f'User {record.user_id}'
                        self.stdout.write(f'  + {record.timestamp} - {emp_name}')
                    else:
                        duplicate_count += 1

                except Exception as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(f'  ✗ Error: {e}'))

            # Clear device if requested
            if clear_device and success_count > 0:
                self.stdout.write('\nClearing attendance records from device...')
                connector.clear_attendance(conn)
                self.stdout.write(self.style.SUCCESS('✓ Device records cleared'))

            conn.disconnect()

            device.last_sync = timezone.now()
            device.save()

            # Summary
            self.stdout.write('\n' + '=' * 50)
            self.stdout.write(self.style.SUCCESS(f'✓ Downloaded: {success_count} new records'))
            if duplicate_count > 0:
                self.stdout.write(f'  Skipped: {duplicate_count} duplicates')
            if error_count > 0:
                self.stdout.write(self.style.ERROR(f'  Errors: {error_count}'))
            self.stdout.write('=' * 50)

        except Exception as e:
            raise CommandError(f'Download failed: {e}')
