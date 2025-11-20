"""
Management command to grant SyncLog delete permissions to all staff users.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType
from ingest.apps.embeddings.models import SyncLog


class Command(BaseCommand):
    help = 'Grant SyncLog delete permissions to all staff users'

    def handle(self, *args, **options):
        # Get SyncLog content type
        content_type = ContentType.objects.get_for_model(SyncLog)
        
        # Get or create delete permission
        delete_permission, created = Permission.objects.get_or_create(
            codename='delete_synclog',
            content_type=content_type,
            defaults={'name': 'Can delete sync log'}
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created permission: {delete_permission}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Permission exists: {delete_permission}'))
        
        # Get or create Staff group
        staff_group, created = Group.objects.get_or_create(name='Staff')
        
        if created:
            self.stdout.write(self.style.SUCCESS('Created Staff group'))
        
        # Add permission to Staff group
        staff_group.permissions.add(delete_permission)
        self.stdout.write(self.style.SUCCESS(f'Added delete_synclog permission to Staff group'))
        
        # Add all staff users to Staff group
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        staff_users = User.objects.filter(is_staff=True)
        for user in staff_users:
            user.groups.add(staff_group)
            self.stdout.write(self.style.SUCCESS(f'Added {user.username} to Staff group'))
        
        self.stdout.write(self.style.SUCCESS(f'\nTotal: {staff_users.count()} staff users granted SyncLog delete permission'))
