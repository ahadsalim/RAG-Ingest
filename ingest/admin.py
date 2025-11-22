from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _
from django.urls import path

class CustomAdminSite(AdminSite):
    site_header = "سیستم مدیریت اسناد"
    site_title = "مدیریت اسناد"
    index_title = "پنل مدیریت"

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


class CustomUserAdmin(UserAdmin):
    """
    سفارشی‌سازی UserAdmin برای نمایش فقط لینک تغییر رمز
    """
    
    def get_readonly_fields(self, request, obj=None):
        """Add custom password display to readonly fields when editing."""
        readonly = list(super().get_readonly_fields(request, obj))
        if obj:  # در حال ویرایش
            if 'password_display' not in readonly:
                readonly.append('password_display')
        return readonly
    
    def get_fieldsets(self, request, obj=None):
        """Override fieldsets to replace password with password_display."""
        fieldsets = super().get_fieldsets(request, obj)
        
        if obj:  # در حال ویرایش
            fieldsets = list(fieldsets)
            for i, (name, data) in enumerate(fieldsets):
                if 'password' in data.get('fields', []):
                    # جایگزین کردن password با password_display
                    fields = list(data['fields'])
                    if 'password' in fields:
                        idx = fields.index('password')
                        fields[idx] = 'password_display'
                    fieldsets[i] = (name, {**data, 'fields': tuple(fields)})
        
        return fieldsets
    
    def password_display(self, obj):
        """Display only password change link."""
        from django.urls import reverse
        from django.utils.html import format_html
        
        change_password_url = reverse('admin:auth_user_password_change', args=[obj.pk])
        return format_html(
            '<a href="{}">تغییر رمز عبور</a>',
            change_password_url
        )
    password_display.short_description = 'گذرواژه'


admin_site.register(User, CustomUserAdmin)
admin_site.register(Group, GroupAdmin)

# Django Celery Beat models are now registered through proxy models in accounts app
# This section is kept for reference but models are no longer registered here

# Embedding model is registered in apps.py IngestConfig.ready() method
