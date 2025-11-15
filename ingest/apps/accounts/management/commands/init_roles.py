from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = 'Initialize user groups and permissions'

    def handle(self, *args, **options):
        self.stdout.write('Creating user groups and permissions...')
        
        # Create groups
        operator_group, created = Group.objects.get_or_create(name='Operator')
        if created:
            self.stdout.write(f'Created group: {operator_group.name}')
        
        reviewer_group, created = Group.objects.get_or_create(name='Reviewer')
        if created:
            self.stdout.write(f'Created group: {reviewer_group.name}')
        
        admin_group, created = Group.objects.get_or_create(name='Admin')
        if created:
            self.stdout.write(f'Created group: {admin_group.name}')
        
        # Get content types
        from ingest.apps.documents.models import LegalUnit, FileAsset
        from ingest.apps.masterdata.models import Jurisdiction, IssuingAuthority, Vocabulary, VocabularyTerm
        from ingest.apps.syncbridge.models import SyncJob
        
        # Operator permissions (can create/edit own content)
        operator_permissions = [
            # Documents
            'add_legalunit', 'change_legalunit', 'view_legalunit',
            'add_fileasset', 'change_fileasset', 'view_fileasset',
            # Masterdata (view only)
            'view_jurisdiction', 'view_issuingauthority', 'view_vocabulary', 'view_vocabularyterm',
            # Sync (view only)
            'view_syncjob',
        ]
        
        # Reviewer permissions (can approve/reject)
        reviewer_permissions = operator_permissions + [
            'delete_legalunit', 'delete_fileasset',
            # Masterdata (add/change)
            'add_jurisdiction', 'change_jurisdiction',
            'add_issuingauthority', 'change_issuingauthority',
            'add_vocabulary', 'change_vocabulary',
            'add_vocabularyterm', 'change_vocabularyterm',
        ]
        
        # Admin permissions (full access)
        admin_permissions = reviewer_permissions + [
            'delete_jurisdiction', 'delete_issuingauthority', 'delete_vocabulary', 'delete_vocabularyterm',
            'add_syncjob', 'change_syncjob', 'delete_syncjob',
        ]
        
        # Assign permissions to groups
        self._assign_permissions(operator_group, operator_permissions)
        self._assign_permissions(reviewer_group, reviewer_permissions)
        self._assign_permissions(admin_group, admin_permissions)
        
        self.stdout.write(
            self.style.SUCCESS('Successfully initialized user groups and permissions')
        )
    
    def _assign_permissions(self, group, permission_codenames):
        """Assign permissions to a group."""
        permissions = Permission.objects.filter(codename__in=permission_codenames)
        group.permissions.set(permissions)
        self.stdout.write(f'Assigned {permissions.count()} permissions to {group.name}')
