"""
Management command to sync employees with device
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from employees.models import Employee
from device.models import Device
from device.zk_connector import ZKDeviceConnector


class Command(BaseCommand):
    help = 'Sync employees with ZKTeco device'

    def add_arguments(self, parser):
        parser.add_argument('device_id', type=int, help='Device ID to sync with')
        parser.add_argument(
            '--direction',
            choices=['to', 'from', 'both'],
            default='both',
            help='Sync direction: to (upload), from (download), or both'
        )
        parser.add_argument(
            '--real',
            action='store_true',
            help='Use real device (ignore ZK_TEST_MODE setting)'
        )

    def handle(self, *args, **options):
        device_id = options['device_id']
        direction = options['direction']
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

        self.stdout.write(f'Syncing with device: {device.name} ({device.ip_address})')

        try:
            conn = connector.connect()

            if direction in ['to', 'both']:
                self.sync_to_device(conn, connector, device)

            if direction in ['from', 'both']:
                self.sync_from_device(conn, connector, device)

            conn.disconnect()

            device.last_sync = timezone.now()
            device.save()

            self.stdout.write(self.style.SUCCESS('✓ Sync completed successfully'))

        except Exception as e:
            raise CommandError(f'Sync failed: {e}')

    def sync_to_device(self, conn, connector, device):
        """Upload employees to device"""
        self.stdout.write('\nUploading employees to device...')
        employees = Employee.objects.filter(is_active=True)

        success_count = 0
        for emp in employees:
            try:
                connector.set_user(
                    conn=conn,
                    uid=emp.user_id,
                    name=emp.full_name,
                    privilege=emp.privilege,
                    password=emp.password or '',
                    group_id='0',
                    user_id=emp.employee_id
                )
                emp.synced_to_device = True
                emp.device = device
                emp.save()
                success_count += 1
                self.stdout.write(f'  ✓ {emp.full_name}')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ {emp.full_name}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Uploaded {success_count} employees'))

    def sync_from_device(self, conn, connector, device):
        """Download employees from device"""
        self.stdout.write('\nDownloading employees from device...')
        users = connector.get_users(conn)

        new_count = 0
        updated_count = 0

        for user in users:
            try:
                employee, created = Employee.objects.update_or_create(
                    user_id=user.uid,
                    defaults={
                        'employee_id': user.user_id or f'EMP{user.uid:04d}',
                        'first_name': user.name.split()[0] if user.name else f'User{user.uid}',
                        'last_name': ' '.join(user.name.split()[1:]) if len(user.name.split()) > 1 else '',
                        'privilege': user.privilege,
                        'password': user.password or '',
                        'synced_to_device': True,
                        'device': device,
                    }
                )
                if created:
                    new_count += 1
                    self.stdout.write(f'  + {employee.full_name} (new)')
                else:
                    updated_count += 1
                    self.stdout.write(f'  ↻ {employee.full_name} (updated)')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ {user.name}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Downloaded: {new_count} new, {updated_count} updated'))
