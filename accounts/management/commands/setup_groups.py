"""
Management command to set up default groups and permissions
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = 'Sets up default permission groups'

    def handle(self, *args, **options):
        self.stdout.write('Setting up default permission groups...')

        # Get content types
        device_ct = ContentType.objects.get(app_label='device', model='device')
        employee_ct = ContentType.objects.get(app_label='employees', model='employee')
        attendance_ct = ContentType.objects.get(app_label='attendance', model='attendanceevent')

        # Get our custom permissions
        device_section_perm = Permission.objects.get(codename='view_device_section', content_type=device_ct)
        manage_devices_perm = Permission.objects.get(codename='manage_devices', content_type=device_ct)

        employee_section_perm = Permission.objects.get(codename='view_employee_section', content_type=employee_ct)
        manage_employees_perm = Permission.objects.get(codename='manage_employees', content_type=employee_ct)
        manage_fingerprints_perm = Permission.objects.get(codename='manage_fingerprints', content_type=employee_ct)

        attendance_section_perm = Permission.objects.get(codename='view_attendance_section', content_type=attendance_ct)
        manage_attendance_perm = Permission.objects.get(codename='manage_attendance', content_type=attendance_ct)
        download_attendance_perm = Permission.objects.get(codename='download_attendance', content_type=attendance_ct)

        # 1. Administrators Group
        admin_group, created = Group.objects.get_or_create(name='Administrators')
        admin_group.permissions.clear()
        admin_group.permissions.add(
            device_section_perm, manage_devices_perm,
            employee_section_perm, manage_employees_perm, manage_fingerprints_perm,
            attendance_section_perm, manage_attendance_perm, download_attendance_perm,
        )
        self.stdout.write(self.style.SUCCESS(f'{"Created" if created else "Updated"} Administrators group'))

        # 2. HR Managers Group
        hr_group, created = Group.objects.get_or_create(name='HR Managers')
        hr_group.permissions.clear()
        hr_group.permissions.add(
            device_section_perm,
            employee_section_perm, manage_employees_perm, manage_fingerprints_perm,
            attendance_section_perm, manage_attendance_perm, download_attendance_perm,
        )
        self.stdout.write(self.style.SUCCESS(f'{"Created" if created else "Updated"} HR Managers group'))

        # 3. Device Managers Group
        device_manager_group, created = Group.objects.get_or_create(name='Device Managers')
        device_manager_group.permissions.clear()
        device_manager_group.permissions.add(
            device_section_perm, manage_devices_perm,
            employee_section_perm,
            attendance_section_perm,
        )
        self.stdout.write(self.style.SUCCESS(f'{"Created" if created else "Updated"} Device Managers group'))

        # 4. Attendance Operators Group
        attendance_operator_group, created = Group.objects.get_or_create(name='Attendance Operators')
        attendance_operator_group.permissions.clear()
        attendance_operator_group.permissions.add(
            employee_section_perm,
            attendance_section_perm, download_attendance_perm,
        )
        self.stdout.write(self.style.SUCCESS(f'{"Created" if created else "Updated"} Attendance Operators group'))

        # 5. Viewers Group
        viewer_group, created = Group.objects.get_or_create(name='Viewers')
        viewer_group.permissions.clear()
        viewer_group.permissions.add(
            device_section_perm,
            employee_section_perm,
            attendance_section_perm,
        )
        self.stdout.write(self.style.SUCCESS(f'{"Created" if created else "Updated"} Viewers group'))

        self.stdout.write(self.style.SUCCESS('\nSuccessfully set up all permission groups!'))
        self.stdout.write('\nAvailable groups:')
        self.stdout.write('  - Administrators: Full access to all sections')
        self.stdout.write('  - HR Managers: Full access to employees & attendance, view devices')
        self.stdout.write('  - Device Managers: Full access to devices, view employees & attendance')
        self.stdout.write('  - Attendance Operators: Can download attendance, view employees')
        self.stdout.write('  - Viewers: Read-only access to all sections')
        self.stdout.write('\nAssign users to groups in the Django admin panel.')
