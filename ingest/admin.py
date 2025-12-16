from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _
from django.urls import path

class CustomAdminSite(AdminSite):
    site_header = "سیستم مدیریت اسناد"
    site_title = "مدیریت اسناد"
    index_title = "پنل مدیریت"
    login_url = '/accounts/login/'  # OTP login page

    def get_app_list(self, request, app_label=None):
        """
        Return a sorted list of all the installed apps that have been
        registered in this site.
        """
        app_dict = self._build_app_dict(request, app_label)
        
        # Customize embeddings app section
        if 'embeddings' in app_dict:
            embeddings_app = app_dict['embeddings']
            embeddings_app['name'] = '🤖 مدیریت بردارها'
            
            # Custom ordering for embeddings models
            model_order = {
                'لیست بردارها': 1,
                'گزارش بردارسازی': 2,
                'همگام‌سازی با سیستم مرکزی': 3,
                'مشاهده نود در سیستم مرکزی': 4,
                'گزارشات سیستم مرکزی': 5,
                'تنظیمات اتصال به سیستم مرکزی': 6,
                'Sync Logs': 7,
                'Sync Stats': 8,
            }
            
            # Sort models by custom order
            embeddings_app['models'] = sorted(
                embeddings_app['models'],
                key=lambda x: model_order.get(x['name'], 999)
            )
            
            # Update app_dict with customized embeddings app
            app_dict['embeddings'] = embeddings_app
        
        # Custom ordering for apps
        app_order = [
            'documents',      # 📄 Documents (مدیریت اسناد)
            'basedata',       # 📊 Base Data (اطلاعات پایه) - Virtual app
            'masterdata',     # 🗂️ Masterdata (جداول پایه)
            'auth',           # 🔐 Authentication and Authorization
            'embeddings',     # 🤖 مدیریت بردارها (dedicated section)
            'accounts',       # ⚙️ سیستم
        ]
        
        # Sort apps according to custom order
        app_list = []
        
        for app_name in app_order:
            if app_name in app_dict:
                app_list.append(app_dict[app_name])
            elif app_name == 'basedata':
                # Create virtual app for "اطلاعات پایه" section
                virtual_app = {
                    'name': '📊 اطلاعات پایه',
                    'app_label': 'basedata',
                    'app_url': None,
                    'has_module_perms': True,
                    'models': []
                }
                
                # Move InstrumentWork, InstrumentExpression, InstrumentManifestation, InstrumentRelation models from documents to basedata section
                if 'documents' in app_dict:
                    documents_app = app_dict['documents']
                    basedata_models = []
                    remaining_models = []
                    
                    for model in documents_app.get('models', []):
                        if model.get('object_name') in ['InstrumentWork', 'InstrumentExpression', 'InstrumentManifestation', 'InstrumentRelation']:
                            basedata_models.append(model)
                        else:
                            remaining_models.append(model)
                    
                    virtual_app['models'] = basedata_models
                    documents_app['models'] = remaining_models
                
                app_list.append(virtual_app)
        
        # Add any remaining apps not in custom order
        for app_name, app in app_dict.items():
            if app_name not in app_order:
                app_list.append(app)
        
        # Custom app names and icons
        for app in app_list:
            if app['app_label'] == 'documents':
                app['name'] = '📄 مدیریت اسناد'
            elif app['app_label'] == 'embeddings':
                # Name is already set above, keep it as is
                pass
            elif app['app_label'] == 'masterdata':
                app['name'] = '🗂️ جداول پایه'
            elif app['app_label'] == 'auth':
                app['name'] = '🔐 احراز هویت و مجوزها'
            elif app['app_label'] == 'accounts':
                app['name'] = '⚙️ سیستم'
                # Add custom report link to accounts app at the top
                app['models'].insert(0, {
                    'name': '📊 گزارش فعالیت کاربران',
                    'object_name': 'UserActivityReport',
                    'admin_url': '/admin/accounts/user-activity-report/',
                    'add_url': None,
                    'view_only': True,
                })
            elif app['app_label'] == 'django_celery_beat':
                app['name'] = '⏰ برنامه‌ریز وظایف'
                # Farsi names for models
                model_names = {
                    'periodic task': 'وظیفه دوره‌ای',
                    'periodic tasks': 'وظایف دوره‌ای',
                    'crontab': 'زمان‌بندی Crontab',
                    'crontabs': 'زمان‌بندی‌های Crontab',
                    'interval': 'زمان‌بندی بازه‌ای',
                    'intervals': 'زمان‌بندی‌های بازه‌ای',
                    'clocked': 'زمان‌بندی یکباره',
                    'clockeds': 'زمان‌بندی‌های یکباره',
                }
                for model in app.get('models', []):
                    model_name_lower = model['name'].lower()
                    if model_name_lower in model_names:
                        model['name'] = model_names[model_name_lower]
        
        return app_list

    def get_urls(self):
        """Override to add custom admin URLs."""
        urls = super().get_urls()
        
        # Import here to avoid circular imports
        from ingest.apps.accounts import admin_views
        
        custom_urls = [
            path(
                'accounts/user-activity-report/',
                self.admin_view(admin_views.user_activity_report),
                name='user_activity_report',
            ),
        ]
        
        # Embedding management now handled directly in EmbeddingAdmin.get_urls()
        
        # Prepend custom URLs so they take precedence
        return custom_urls + urls

# Create custom admin site instance  
admin_site = CustomAdminSite(name='custom_admin')

# Register built-in Django models immediately
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin


class UserProfileInline(admin.StackedInline):
    """Inline for UserProfile in User admin."""
    from ingest.apps.accounts.models import UserProfile
    model = UserProfile
    can_delete = False
    verbose_name = 'پروفایل'
    verbose_name_plural = 'پروفایل'
    fields = ('mobile', 'is_mobile_verified')
    
    def get_queryset(self, request):
        from ingest.apps.accounts.models import UserProfile
        return UserProfile.objects.all()


class CustomUserAdmin(UserAdmin):
    """
    سفارشی‌سازی UserAdmin برای سیستم احراز هویت OTP
    - حذف فیلد password (لاگین با OTP)
    - اضافه کردن UserProfile inline برای شماره موبایل
    """
    inlines = [UserProfileInline]
    
    # حذف فیلد password از لیست نمایش
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'get_mobile')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'profile__mobile')
    
    def get_mobile(self, obj):
        """نمایش شماره موبایل از پروفایل"""
        try:
            return obj.profile.mobile
        except:
            return '-'
    get_mobile.short_description = 'شماره موبایل'
    get_mobile.admin_order_field = 'profile__mobile'
    
    def get_fieldsets(self, request, obj=None):
        """Override fieldsets to remove password field for OTP-based auth."""
        if not obj:
            # Creating new user - simplified form
            return (
                (None, {
                    'classes': ('wide',),
                    'fields': ('username', 'first_name', 'last_name', 'email'),
                }),
            )
        
        # Editing existing user - no password field
        return (
            (None, {'fields': ('username',)}),
            ('اطلاعات شخصی', {'fields': ('first_name', 'last_name', 'email')}),
            ('دسترسی‌ها', {
                'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            }),
            ('تاریخ‌های مهم', {'fields': ('last_login', 'date_joined')}),
        )
    
    def get_readonly_fields(self, request, obj=None):
        """Make some fields readonly when editing."""
        if obj:
            return ('username', 'last_login', 'date_joined')
        return ()
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'first_name', 'last_name', 'email'),
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """
        Set unusable password for new users (OTP-based auth).
        Also auto-add SyncLog delete permission for LUnit editors.
        """
        if not change:
            # New user - set unusable password
            obj.set_unusable_password()
        super().save_model(request, obj, form, change)
        
        # بررسی permissions برای اضافه کردن خودکار permission حذف SyncLog
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.auth.models import Permission
        
        try:
            lunit_ct = ContentType.objects.get(app_label='documents', model='lunit')
            legalunit_ct = ContentType.objects.get(app_label='documents', model='legalunit')
            
            has_lunit_change = obj.user_permissions.filter(
                content_type=lunit_ct, codename='change_lunit'
            ).exists() or obj.groups.filter(
                permissions__content_type=lunit_ct, permissions__codename='change_lunit'
            ).exists()
            
            has_legalunit_change = obj.user_permissions.filter(
                content_type=legalunit_ct, codename='change_legalunit'
            ).exists() or obj.groups.filter(
                permissions__content_type=legalunit_ct, permissions__codename='change_legalunit'
            ).exists()
            
            if has_lunit_change or has_legalunit_change:
                synclog_ct = ContentType.objects.get(app_label='embeddings', model='synclog')
                delete_synclog_perm = Permission.objects.get(
                    content_type=synclog_ct, codename='delete_synclog'
                )
                if not obj.user_permissions.filter(pk=delete_synclog_perm.pk).exists():
                    obj.user_permissions.add(delete_synclog_perm)
        except ContentType.DoesNotExist:
            pass
    
    def save_related(self, request, form, formsets, change):
        """
        بعد از save کردن permissions/groups، دوباره چک کن.
        """
        super().save_related(request, form, formsets, change)
        
        # بررسی permissions برای اضافه کردن خودکار permission حذف SyncLog
        obj = form.instance
        
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.auth.models import Permission
        
        try:
            lunit_ct = ContentType.objects.get(app_label='documents', model='lunit')
            legalunit_ct = ContentType.objects.get(app_label='documents', model='legalunit')
            
            has_lunit_change = obj.user_permissions.filter(
                content_type=lunit_ct, codename='change_lunit'
            ).exists() or obj.groups.filter(
                permissions__content_type=lunit_ct, permissions__codename='change_lunit'
            ).exists()
            
            has_legalunit_change = obj.user_permissions.filter(
                content_type=legalunit_ct, codename='change_legalunit'
            ).exists() or obj.groups.filter(
                permissions__content_type=legalunit_ct, permissions__codename='change_legalunit'
            ).exists()
            
            if has_lunit_change or has_legalunit_change:
                synclog_ct = ContentType.objects.get(app_label='embeddings', model='synclog')
                delete_synclog_perm = Permission.objects.get(
                    content_type=synclog_ct, codename='delete_synclog'
                )
                if not obj.user_permissions.filter(pk=delete_synclog_perm.pk).exists():
                    obj.user_permissions.add(delete_synclog_perm)
        except ContentType.DoesNotExist:
            pass


admin_site.register(User, CustomUserAdmin)
admin_site.register(Group, GroupAdmin)

# Django Celery Beat models are now registered through proxy models in accounts app
# This section is kept for reference but models are no longer registered here

# Embedding model is registered in apps.py IngestConfig.ready() method
