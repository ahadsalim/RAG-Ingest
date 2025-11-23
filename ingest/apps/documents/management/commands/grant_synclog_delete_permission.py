"""
Management command برای دادن permission حذف SyncLog به کاربران با permission ویرایش LUnit/LegalUnit.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission

User = get_user_model()


class Command(BaseCommand):
    help = 'Grant delete_synclog permission to users with change_lunit or change_legalunit permission'

    def handle(self, *args, **options):
        # دریافت content types
        lunit_ct = ContentType.objects.get(app_label='documents', model='lunit')
        legalunit_ct = ContentType.objects.get(app_label='documents', model='legalunit')
        synclog_ct = ContentType.objects.get(app_label='embeddings', model='synclog')
        
        # دریافت permission حذف SyncLog
        delete_synclog_perm = Permission.objects.get(
            content_type=synclog_ct, codename='delete_synclog'
        )
        
        # پیدا کردن همه کاربران با permission ویرایش LUnit یا LegalUnit
        users_to_grant = set()
        
        # کاربران با permission مستقیم
        users_with_lunit = User.objects.filter(
            user_permissions__content_type=lunit_ct,
            user_permissions__codename='change_lunit'
        )
        users_with_legalunit = User.objects.filter(
            user_permissions__content_type=legalunit_ct,
            user_permissions__codename='change_legalunit'
        )
        
        for user in users_with_lunit:
            users_to_grant.add(user)
        for user in users_with_legalunit:
            users_to_grant.add(user)
        
        # کاربران با permission از طریق group
        users_with_lunit_group = User.objects.filter(
            groups__permissions__content_type=lunit_ct,
            groups__permissions__codename='change_lunit'
        )
        users_with_legalunit_group = User.objects.filter(
            groups__permissions__content_type=legalunit_ct,
            groups__permissions__codename='change_legalunit'
        )
        
        for user in users_with_lunit_group:
            users_to_grant.add(user)
        for user in users_with_legalunit_group:
            users_to_grant.add(user)
        
        # اضافه کردن permission به کاربران
        granted_count = 0
        already_had_count = 0
        
        for user in users_to_grant:
            if user.user_permissions.filter(pk=delete_synclog_perm.pk).exists():
                already_had_count += 1
                self.stdout.write(f'  {user.username}: قبلاً داشت')
            else:
                user.user_permissions.add(delete_synclog_perm)
                granted_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ {user.username}: permission داده شد'))
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ تعداد کاربران: {len(users_to_grant)}'))
        self.stdout.write(self.style.SUCCESS(f'✅ permission جدید داده شد: {granted_count}'))
        self.stdout.write(f'  قبلاً داشتند: {already_had_count}')
