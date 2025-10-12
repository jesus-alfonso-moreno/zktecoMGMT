"""
Management command to test device connection
"""
from django.core.management.base import BaseCommand, CommandError
from device.models import Device
from device.zk_connector import ZKDeviceConnector


class Command(BaseCommand):
    help = 'Test connection to a ZKTeco device'

    def add_arguments(self, parser):
        parser.add_argument('device_id', type=int, help='Device ID to test')
        parser.add_argument(
            '--real',
            action='store_true',
            help='Use real device (ignore ZK_TEST_MODE setting)'
        )

    def handle(self, *args, **options):
        device_id = options['device_id']
        use_real = options['real']

        try:
            device = Device.objects.get(pk=device_id)
        except Device.DoesNotExist:
            raise CommandError(f'Device with ID {device_id} does not exist')

        self.stdout.write(f'Testing connection to: {device.name} ({device.ip_address}:{device.port})')

        if use_real:
            self.stdout.write(self.style.WARNING('Using REAL device mode'))
            connector = ZKDeviceConnector(device, use_mock=False)
        else:
            connector = ZKDeviceConnector(device)
            if connector.use_mock:
                self.stdout.write(self.style.WARNING('Using MOCK mode'))

        success, message = connector.test_connection()

        if success:
            self.stdout.write(self.style.SUCCESS(f'✓ {message}'))

            # Try to get device info
            try:
                conn = connector.connect()
                info = connector.get_device_info(conn)
                conn.disconnect()

                self.stdout.write('\nDevice Information:')
                self.stdout.write(f'  Serial Number: {info["serial_number"]}')
                self.stdout.write(f'  Firmware: {info["firmware_version"]}')
                self.stdout.write(f'  Platform: {info["platform"]}')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Could not retrieve device info: {e}'))
        else:
            self.stdout.write(self.style.ERROR(f'✗ {message}'))
            raise CommandError('Connection test failed')
