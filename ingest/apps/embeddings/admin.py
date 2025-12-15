from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render
from django.db.models import Count
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
import requests

from simple_history.admin import SimpleHistoryAdmin
from ingest.apps.embeddings.models import Embedding, CoreConfig, SyncLog, SyncStats
from ingest.apps.embeddings.models_synclog import DeletionLog
from ingest.admin import admin_site
from ingest.apps.documents.models import Chunk, QAEntry, LegalUnit, TextEntry
from ingest.core.admin_mixins import JalaliAdminMixin as SimpleJalaliAdminMixin
from django.contrib import messages
from django.utils.html import format_html_join


# Simple Embedding Admin - Read-only with stats
class EmbeddingAdmin(SimpleJalaliAdminMixin, SimpleHistoryAdmin):
    """Embedding admin - Read-only, shows reports only"""
    list_display = ('content_object', 'model_id', 'dim', 'synced_status_display', 'jalali_created_at_display')
    list_filter = ('model_id', 'dim', 'content_type', 'synced_to_core', 'created_at')
    search_fields = ('text_content', 'model_id', 'sync_error')
    readonly_fields = ('id', 'vector', 'model_id', 'dim', 'created_at', 'updated_at', 
                       'synced_to_core', 'synced_at', 'sync_error', 'metadata_hash')
    actions = ['sync_to_core', 'reset_sync_status', 'verify_nodes_in_core']
    
    def synced_status_display(self, obj):
        """Display sync status with color"""
        if obj.synced_to_core:
            return format_html('<span style="color: green;">✓ Synced</span>')
        elif obj.sync_error:
            return format_html('<span style="color: red;">✗ Error</span>')
        else:
            return format_html('<span style="color: orange;">⧗ Pending</span>')
    synced_status_display.short_description = 'Sync Status'
    
    def sync_to_core(self, request, queryset):
        """Action to sync selected embeddings to Core"""
        from ingest.core.sync.sync_service import CoreSyncService
        from ingest.core.sync.payload_builder import build_summary_payload, calculate_metadata_hash
        from django.db import transaction
        
        service = CoreSyncService()
        config = CoreConfig.get_config()
        
        if not config.is_active or not config.auto_sync_enabled:
            self.message_user(request, 'Core sync is disabled in settings', level=messages.ERROR)
            return
        
        # Build payloads
        payloads = []
        embedding_map = {}
        
        for emb in queryset:
            payload = build_summary_payload(emb)
            if payload:
                payloads.append(payload)
                embedding_map[str(emb.id)] = emb
                emb.metadata_hash = calculate_metadata_hash(payload)
        
        if not payloads:
            self.message_user(request, 'No valid payloads to sync', level=messages.WARNING)
            return
        
        # Send to Core
        result = service._send_to_core(payloads)
        
        if result['success']:
            with transaction.atomic():
                for payload in payloads:
                    emb = embedding_map[payload['id']]
                    emb.synced_to_core = True
                    emb.synced_at = timezone.now()
                    emb.sync_error = ''
                    emb.save()
            
            self.message_user(request, f'Successfully synced {len(payloads)} embeddings', level=messages.SUCCESS)
        else:
            self.message_user(request, f'Sync failed: {result.get("error")}', level=messages.ERROR)
    
    sync_to_core.short_description = 'Sync selected embeddings to Core'
    
    def reset_sync_status(self, request, queryset):
        """Action to reset sync status for re-syncing"""
        count = queryset.update(
            synced_to_core=False,
            synced_at=None,
            sync_error='',
            sync_retry_count=0
        )
        self.message_user(request, f'Reset sync status for {count} embeddings', level=messages.SUCCESS)
    
    reset_sync_status.short_description = 'Reset sync status (for re-sync)'
    
    def verify_nodes_in_core(self, request, queryset):
        """Action to verify nodes in Core"""
        from ingest.core.sync.node_verifier import create_verifier_from_config
        from ingest.apps.documents.models import Chunk
        
        verifier = create_verifier_from_config()
        
        # فیلتر کردن فقط embeddings که sync شده‌اند
        synced_embeddings = queryset.filter(synced_to_core=True)
        
        if not synced_embeddings.exists():
            self.message_user(request, 'هیچ embedding همگام‌سازی شده‌ای انتخاب نشده', level=messages.WARNING)
            return
        
        verified_count = 0
        not_found_count = 0
        error_count = 0
        
        for emb in synced_embeddings[:50]:  # محدود به 50 برای جلوگیری از timeout
            chunk = emb.content_object
            
            if isinstance(chunk, Chunk) and chunk.node_id:
                try:
                    exists = verifier.node_exists(str(chunk.node_id))
                    
                    if exists:
                        verified_count += 1
                    else:
                        not_found_count += 1
                except Exception as e:
                    error_count += 1
        
        # نمایش نتیجه
        message = f'✅ تایید شد: {verified_count}'
        if not_found_count > 0:
            message += f' | ❌ یافت نشد: {not_found_count}'
        if error_count > 0:
            message += f' | ⚠️ خطا: {error_count}'
        
        level = messages.SUCCESS if not_found_count == 0 and error_count == 0 else messages.WARNING
        self.message_user(request, message, level=level)
    
    verify_nodes_in_core.short_description = 'تایید نودها در Core (حداکثر 50 عدد)'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('content_type')
    
    def has_add_permission(self, request):
        return False  # Auto-generated
    
    def has_change_permission(self, request, obj=None):
        return True  # Allow viewing details
    
    def changelist_view(self, request, extra_context=None):
        """Add custom buttons to changelist"""
        extra_context = extra_context or {}
        extra_context['show_core_viewer_button'] = True
        # show_reports_button را حذف کردیم چون حالا در sidebar داریم
        return super().changelist_view(request, extra_context=extra_context)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('reports/', self.admin_site.admin_view(self.view_reports), name='embedding_reports'),
            path('core-node-viewer/', self.admin_site.admin_view(self.core_node_viewer), name='core_node_viewer'),
        ]
        return custom_urls + urls
    
    def view_reports(self, request):
        """Show embedding statistics and system reports"""
        from ingest.apps.embeddings.models_synclog import SyncLog, SyncStats
        
        context = self.admin_site.each_context(request)
        context['title'] = 'گزارش بردارسازی'
        
        # Handle rebuild action
        if request.method == 'POST' and 'rebuild_all_embeddings' in request.POST:
            try:
                # Delete all embeddings and sync data
                embedding_count = Embedding.objects.count()
                Embedding.objects.all().delete()
                SyncLog.objects.all().delete()
                SyncStats.objects.all().delete()
                Chunk.objects.filter(node_id__isnull=False).update(node_id=None)
                
                # Reset CoreConfig stats
                config = CoreConfig.get_config()
                config.total_synced = 0
                config.total_errors = 0
                config.last_successful_sync = None
                config.last_sync_error = ''
                config.save()
                
                # Start re-embedding using celery task
                from ingest.apps.embeddings.tasks import generate_missing_embeddings
                task = generate_missing_embeddings.delay()
                
                messages.success(
                    request, 
                    f'✅ {embedding_count} Embedding حذف شد و بردارسازی مجدد شروع شد (Task: {task.id})'
                )
            except Exception as e:
                messages.error(request, f'❌ خطا: {str(e)}')
        
        # Get content types
        chunk_ct = ContentType.objects.get_for_model(Chunk)
        
        # === آمار LegalUnit ===
        total_legal_units = LegalUnit.objects.count()
        lu_chunks = Chunk.objects.filter(unit__isnull=False).count()
        lu_chunks_with_embeddings = Chunk.objects.filter(
            unit__isnull=False,
            embeddings__isnull=False
        ).distinct().count()
        
        # === آمار QAEntry ===
        total_qa = QAEntry.objects.count()
        qa_chunks = Chunk.objects.filter(qaentry__isnull=False).count()
        qa_chunks_with_embeddings = Chunk.objects.filter(
            qaentry__isnull=False,
            embeddings__isnull=False
        ).distinct().count()
        
        # === آمار TextEntry ===
        total_text = TextEntry.objects.count()
        text_chunks = Chunk.objects.filter(textentry__isnull=False).count()
        text_chunks_with_embeddings = Chunk.objects.filter(
            textentry__isnull=False,
            embeddings__isnull=False
        ).distinct().count()
        
        # === آمار کلی Chunks ===
        total_chunks = Chunk.objects.count()
        chunks_with_embeddings = Embedding.objects.filter(content_type=chunk_ct).count()
        
        # Recent activity (last 24 hours)
        yesterday = datetime.now() - timedelta(days=1)
        recent_chunks = Chunk.objects.filter(created_at__gte=yesterday).count()
        recent_embeddings = Embedding.objects.filter(created_at__gte=yesterday).count()
        
        # Stats by model
        embedding_by_model = Embedding.objects.values('model_id').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Calculate percentages
        chunks_percentage = round((chunks_with_embeddings / total_chunks * 100), 1) if total_chunks > 0 else 0
        lu_percentage = round((lu_chunks_with_embeddings / lu_chunks * 100), 1) if lu_chunks > 0 else 0
        qa_percentage = round((qa_chunks_with_embeddings / qa_chunks * 100), 1) if qa_chunks > 0 else 0
        text_percentage = round((text_chunks_with_embeddings / text_chunks * 100), 1) if text_chunks > 0 else 0
        
        # === آمار Sync ===
        synced_embeddings = Embedding.objects.filter(synced_to_core=True).count()
        pending_sync = Embedding.objects.filter(synced_to_core=False).count()
        sync_percentage = round((synced_embeddings / chunks_with_embeddings * 100), 1) if chunks_with_embeddings > 0 else 0
        
        context.update({
            # LegalUnit stats
            'total_legal_units': total_legal_units,
            'lu_chunks': lu_chunks,
            'lu_chunks_with_embeddings': lu_chunks_with_embeddings,
            'lu_chunks_missing': lu_chunks - lu_chunks_with_embeddings,
            'lu_percentage': lu_percentage,
            
            # QAEntry stats
            'total_qa': total_qa,
            'qa_chunks': qa_chunks,
            'qa_chunks_with_embeddings': qa_chunks_with_embeddings,
            'qa_chunks_missing': qa_chunks - qa_chunks_with_embeddings,
            'qa_percentage': qa_percentage,
            
            # TextEntry stats
            'total_text': total_text,
            'text_chunks': text_chunks,
            'text_chunks_with_embeddings': text_chunks_with_embeddings,
            'text_chunks_missing': text_chunks - text_chunks_with_embeddings,
            'text_percentage': text_percentage,
            
            # Overall chunk stats
            'total_chunks': total_chunks,
            'chunks_with_embeddings': chunks_with_embeddings,
            'chunks_missing': total_chunks - chunks_with_embeddings,
            'chunks_percentage': chunks_percentage,
            
            # Sync stats
            'synced_embeddings': synced_embeddings,
            'pending_sync': pending_sync,
            'sync_percentage': sync_percentage,
            
            # Recent activity
            'recent_chunks': recent_chunks,
            'recent_embeddings': recent_embeddings,
            'embedding_by_model': embedding_by_model,
            
            # Settings
            'current_model': settings.EMBEDDING_E5_MODEL_NAME,
            'current_dimension': settings.EMBEDDING_DIMENSION,
            'chunk_size': settings.DEFAULT_CHUNK_SIZE,
            'chunk_overlap': settings.DEFAULT_CHUNK_OVERLAP,
        })
        
        return render(request, 'admin/embeddings/embedding_reports.html', context)
    
    def core_node_viewer(self, request):
        """نمایش اطلاعات Node از Core API"""
        context = self.admin_site.each_context(request)
        context['title'] = 'مشاهده نود در سیستم مرکزی'
        
        # دریافت لیست node_id های موجود
        chunks_with_nodes = Chunk.objects.filter(node_id__isnull=False).select_related('unit', 'qaentry')[:100]
        context['available_nodes'] = chunks_with_nodes
        
        node_data = None  # کل JSON خام Core
        node_json = None  # نسخه pretty برای نمایش
        error = None
        node_id = request.GET.get('node_id')

        if node_id:
            # دریافت اطلاعات از Core
            config = CoreConfig.get_config()
            url = f"{config.core_api_url}/api/v1/sync/node/{node_id}"
            
            try:
                response = requests.get(
                    url,
                    headers={'X-API-Key': config.core_api_key},
                    timeout=30
                )

                if response.status_code == 200:
                    # JSON خام Core (همان چیزی که در انتهای صفحه می‌دیدی)
                    raw = response.json() or {}
                    node_data = raw

                    # JSON خام برای نمایش توسعه‌دهندگان به‌صورت pretty
                    try:
                        import json
                        node_json = json.dumps(raw, ensure_ascii=False, indent=2)
                    except Exception:
                        node_json = str(raw)

                    # اطلاعات Chunk مرتبط (سمت ingest)
                    try:
                        chunk = Chunk.objects.get(node_id=node_id)
                        context['chunk'] = chunk
                    except Chunk.DoesNotExist:
                        pass
                else:
                    error = f"خطا {response.status_code}: {response.text[:200]}"

            except Exception as e:
                error = f"خطا در اتصال: {str(e)}"

        context['node_data'] = node_data
        context['node_json'] = node_json
        context['error'] = error
        context['requested_node_id'] = node_id

        return render(request, 'admin/embeddings/core_node_viewer.html', context)


# Register with admin site
admin_site.register(Embedding, EmbeddingAdmin)


# Fake models for menu display
from django.db import models as fake_models

class CoreNodeViewer(fake_models.Model):
    """Fake model for admin menu - Node Viewer"""
    class Meta:
        verbose_name = 'مشاهده نود در سیستم مرکزی'
        verbose_name_plural = 'مشاهده نود در سیستم مرکزی'
        app_label = 'embeddings'
        managed = False


class CoreSyncManager(fake_models.Model):
    """Fake model for admin menu - Sync Manager"""
    class Meta:
        verbose_name = 'همگام‌سازی با سیستم مرکزی'
        verbose_name_plural = 'همگام‌سازی با سیستم مرکزی'
        app_label = 'embeddings'
        managed = False


class EmbeddingReports(fake_models.Model):
    """Fake model for admin menu - Embedding Reports"""
    class Meta:
        verbose_name = 'گزارش بردارسازی'
        verbose_name_plural = 'گزارش بردارسازی'
        app_label = 'embeddings'
        managed = False


@admin.register(CoreNodeViewer, site=admin_site)
class CoreNodeViewerAdmin(admin.ModelAdmin):
    """Admin class for Core Node Viewer menu item"""
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return True
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_module_permission(self, request):
        return True
    
    def changelist_view(self, request, extra_context=None):
        """Display node viewer"""
        # Get the EmbeddingAdmin instance and call its core_node_viewer method
        embedding_admin = EmbeddingAdmin(Embedding, admin_site)
        return embedding_admin.core_node_viewer(request)


@admin.register(EmbeddingReports, site=admin_site)
class EmbeddingReportsAdmin(admin.ModelAdmin):
    """Admin class for Embedding Reports menu item"""
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return True
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_module_permission(self, request):
        return True
    
    def changelist_view(self, request, extra_context=None):
        """Display embedding reports"""
        # Get the EmbeddingAdmin instance and call its view_reports method
        embedding_admin = EmbeddingAdmin(Embedding, admin_site)
        return embedding_admin.view_reports(request)


@admin.register(CoreSyncManager, site=admin_site)
class CoreSyncManagerAdmin(admin.ModelAdmin):
    """Admin class for Core Sync Manager menu item"""
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return True
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_module_permission(self, request):
        return True
    
    def changelist_view(self, request, extra_context=None):
        """Display sync manager"""
        context = admin_site.each_context(request)
        context['title'] = 'همگام‌سازی با سیستم مرکزی'
        
        # Handle sync actions
        if request.method == 'POST':
            if 'trigger_sync' in request.POST:
                from ingest.apps.embeddings.tasks import auto_sync_new_embeddings
                try:
                    task = auto_sync_new_embeddings.delay()
                    messages.success(request, f'✅ همگام‌سازی جدیدها شروع شد (Task: {task.id})')
                except Exception as e:
                    messages.error(request, f'❌ خطا در شروع همگام‌سازی: {str(e)}')
            
            elif 'full_sync' in request.POST:
                from ingest.apps.embeddings.tasks import full_sync_all_embeddings
                try:
                    task = full_sync_all_embeddings.delay()
                    messages.success(request, f'✅ همگام‌سازی کامل شروع شد (Task: {task.id})')
                except Exception as e:
                    messages.error(request, f'❌ خطا در شروع همگام‌سازی: {str(e)}')
        
        # Get stats
        config = CoreConfig.get_config()
        total_embeddings = Embedding.objects.count()
        synced_embeddings = Embedding.objects.filter(synced_to_core=True).count()
        pending_embeddings = total_embeddings - synced_embeddings
        failed_embeddings = Embedding.objects.filter(sync_error__isnull=False).exclude(sync_error='').count()
        
        # Recent sync logs
        recent_logs = SyncLog.objects.select_related('chunk').order_by('-synced_at')[:20]
        
        context.update({
            'config': config,
            'total_embeddings': total_embeddings,
            'synced_embeddings': synced_embeddings,
            'pending_embeddings': pending_embeddings,
            'failed_embeddings': failed_embeddings,
            'sync_percentage': round((synced_embeddings / total_embeddings * 100) if total_embeddings > 0 else 0, 1),
            'recent_logs': recent_logs,
            # اطلاعات وضعیت و آمار از CoreConfig
            'is_active': config.is_active,
            'last_sync_error': config.last_sync_error,
            'total_synced': config.total_synced,
            'total_errors': config.total_errors,
        })
        
        return render(request, 'admin/embeddings/core_sync_manager.html', context)


# CoreConfig Admin - Settings for Core sync
@admin.register(CoreConfig, site=admin_site)
class CoreConfigAdmin(SimpleJalaliAdminMixin, admin.ModelAdmin):
    """Admin for Core configuration settings"""
    
    change_form_template = 'admin/embeddings/coreconfig/change_form.html'
    
    fieldsets = (
        ('اتصال به Core', {
            'fields': ('core_api_url', 'core_api_key')
        }),
        ('تنظیمات Sync', {
            'fields': ('auto_sync_enabled', 'sync_batch_size', 'sync_interval_minutes', 
                      'retry_on_error', 'max_retries', 'track_metadata_changes')
        }),
    )
    
    readonly_fields = ()
    
    def has_add_permission(self, request):
        # Only allow one config (Singleton)
        return CoreConfig.objects.count() == 0
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Redirect to the single config if it exists"""
        config = CoreConfig.get_config()
        from django.shortcuts import redirect
        from django.urls import reverse
        return redirect(reverse('admin:embeddings_coreconfig_change', args=[config.pk]))
    
    def get_urls(self):
        """Add custom URL for AJAX test connection"""
        urls = super().get_urls()
        custom_urls = [
            path('test-connection/', self.admin_site.admin_view(self.test_connection_ajax), name='coreconfig_test_connection'),
        ]
        return custom_urls + urls
    
    def test_connection_ajax(self, request):
        """AJAX endpoint for testing connection"""
        from django.http import JsonResponse
        import requests
        
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'فقط POST قابل قبول است'}, status=405)
        
        try:
            config = CoreConfig.get_config()
            
            # Test connection
            try:
                url = f"{config.core_api_url}/api/v1/health"
                headers = {}
                if config.core_api_key:
                    headers['X-API-Key'] = config.core_api_key
                
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    return JsonResponse({
                        'success': True,
                        'message': f'✅ اتصال به Core موفق بود\n\nURL: {config.core_api_url}\nوضعیت: فعال'
                    })
                elif response.status_code == 401:
                    return JsonResponse({
                        'success': False,
                        'error': f'❌ خطای احراز هویت (401)\n\nAPI Key نادرست است. لطفاً کلید API را بررسی کنید.'
                    })
                elif response.status_code == 404:
                    return JsonResponse({
                        'success': False,
                        'error': f'❌ API یافت نشد (404)\n\nEndpoint: {url}\n\nلطفاً آدرس Core را بررسی کنید.'
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'error': f'❌ خطای سرور ({response.status_code})\n\n{response.text[:200]}'
                    })
                    
            except requests.exceptions.ConnectionError as e:
                return JsonResponse({
                    'success': False,
                    'error': f'❌ خطای اتصال\n\nسرور Core در آدرس زیر در دسترس نیست:\n{config.core_api_url}\n\nجزئیات: {str(e)[:200]}'
                })
            except requests.exceptions.Timeout:
                return JsonResponse({
                    'success': False,
                    'error': f'❌ خطای Timeout\n\nسرور Core پاسخ نمی‌دهد (بیش از 10 ثانیه):\n{config.core_api_url}'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'❌ خطای غیرمنتظره\n\n{str(e)}'
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'خطا در پردازش درخواست: {str(e)}'
            }, status=500)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Add custom buttons and test connection"""
        extra_context = extra_context or {}
        extra_context['show_test_button'] = True
        
        return super().change_view(request, object_id, form_url, extra_context)
    


# SyncLog Admin
@admin.register(SyncLog, site=admin_site)
class SyncLogAdmin(SimpleJalaliAdminMixin, admin.ModelAdmin):
    """Admin برای SyncLog"""
    
    list_display = ('node_id', 'get_source_type', 'get_chunk_ref', 'status', 'synced_at', 'verified_at', 'retry_count')
    list_filter = ('status', 'synced_at', 'verified_at')
    search_fields = ('node_id', 'error_message')
    readonly_fields = ('node_id', 'chunk', 'synced_at', 'verified_at', 
                      'status', 'retry_count', 'error_message', 'core_response',
                      'created_at', 'updated_at', 'get_source_type')
    
    fieldsets = (
        ('محتوا', {
            'fields': ('chunk', 'get_source_type', 'node_id')
        }),
        ('وضعیت', {
            'fields': ('status', 'synced_at', 'verified_at', 'retry_count')
        }),
        ('خطا', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Core Response', {
            'fields': ('core_response',),
            'classes': ('collapse',)
        }),
        ('سیستم', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_source_type(self, obj):
        """نمایش نوع منبع (LegalUnit یا QAEntry)"""
        return obj.get_source_type().upper()
    get_source_type.short_description = 'نوع منبع'
    
    def get_chunk_ref(self, obj):
        """نمایش reference به Chunk"""
        if obj.chunk.unit:
            return f"Chunk (LU {obj.chunk.unit_id})"
        elif obj.chunk.qaentry:
            return f"Chunk (QA {obj.chunk.qaentry_id})"
        return f"Chunk {obj.chunk_id}"
    get_chunk_ref.short_description = 'Chunk'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    actions = ['verify_selected']
    
    def verify_selected(self, request, queryset):
        """Verify selected sync logs"""
        from ingest.core.sync.sync_service import CoreSyncService
        
        service = CoreSyncService()
        verified = 0
        failed = 0
        
        for sync_log in queryset.filter(status='synced'):
            if service.verify_and_update_log(sync_log):
                verified += 1
            else:
                failed += 1
        
        self.message_user(
            request,
            f'✅ {verified} verified, ❌ {failed} failed',
            level=messages.SUCCESS if failed == 0 else messages.WARNING
        )
    
    verify_selected.short_description = 'Verify selected logs'


# DeletionLog Admin
@admin.register(DeletionLog, site=admin_site)
class DeletionLogAdmin(SimpleJalaliAdminMixin, admin.ModelAdmin):
    """Admin برای DeletionLog - نمایش و مدیریت حذف‌های pending"""
    
    list_display = ('chunk_id', 'deletion_status_display', 'node_id', 'retry_count', 
                   'jalali_deleted_from_ingest_at_display', 'jalali_deleted_from_core_at_display')
    list_filter = ('deletion_status', 'retry_count', 'deleted_from_ingest_at')
    search_fields = ('chunk_id', 'embedding_id', 'node_id', 'error_message')
    readonly_fields = ('chunk_id', 'embedding_id', 'node_id', 'deleted_from_ingest_at',
                      'deleted_from_core_at', 'retry_count', 'last_retry_at', 
                      'error_message', 'chunk_metadata', 'created_at', 'updated_at')
    
    actions = ['retry_deletion_action', 'mark_as_success']
    
    def deletion_status_display(self, obj):
        """نمایش وضعیت با رنگ"""
        colors = {
            'success': 'green',
            'pending': 'orange',
            'failed': 'red',
            'local_only': 'gray',
        }
        icons = {
            'success': '✓',
            'pending': '⧗',
            'failed': '✗',
            'local_only': '○',
        }
        color = colors.get(obj.deletion_status, 'black')
        icon = icons.get(obj.deletion_status, '?')
        label = obj.get_deletion_status_display()
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, icon, label
        )
    deletion_status_display.short_description = 'وضعیت حذف'
    
    def jalali_deleted_from_ingest_at_display(self, obj):
        """نمایش تاریخ حذف از Ingest"""
        if obj.deleted_from_ingest_at:
            from ingest.core.jalali import to_jalali_datetime
            return to_jalali_datetime(obj.deleted_from_ingest_at)
        return '-'
    jalali_deleted_from_ingest_at_display.short_description = 'حذف از Ingest'
    
    def jalali_deleted_from_core_at_display(self, obj):
        """نمایش تاریخ حذف از Core"""
        if obj.deleted_from_core_at:
            from ingest.core.jalali import to_jalali_datetime
            return to_jalali_datetime(obj.deleted_from_core_at)
        return '-'
    jalali_deleted_from_core_at_display.short_description = 'حذف از Core'
    
    def retry_deletion_action(self, request, queryset):
        """تلاش مجدد برای حذف از Core"""
        success_count = 0
        failed_count = 0
        
        for deletion_log in queryset.filter(deletion_status__in=['pending', 'failed']):
            if deletion_log.retry_count >= 5:
                continue
            
            success, message = deletion_log.retry_deletion()
            if success:
                success_count += 1
            else:
                failed_count += 1
        
        if success_count > 0:
            self.message_user(
                request,
                f'✅ {success_count} مورد با موفقیت از Core حذف شد',
                level=messages.SUCCESS
            )
        if failed_count > 0:
            self.message_user(
                request,
                f'❌ {failed_count} مورد با خطا مواجه شد',
                level=messages.WARNING
            )
    
    retry_deletion_action.short_description = 'تلاش مجدد برای حذف از Core'
    
    def mark_as_success(self, request, queryset):
        """علامت‌گذاری به عنوان موفق (برای موارد manual)"""
        count = queryset.filter(deletion_status__in=['pending', 'failed']).update(
            deletion_status='success',
            deleted_from_core_at=timezone.now()
        )
        self.message_user(
            request,
            f'✅ {count} مورد به عنوان موفق علامت‌گذاری شد',
            level=messages.SUCCESS
        )
    
    mark_as_success.short_description = 'علامت‌گذاری به عنوان موفق'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


# SyncStats Admin
@admin.register(SyncStats, site=admin_site)
class SyncStatsAdmin(SimpleJalaliAdminMixin, admin.ModelAdmin):
    """Admin برای SyncStats"""
    
    list_display = ('timestamp', 'total_embeddings', 'synced_count', 'verified_count', 
                   'failed_count', 'sync_percentage', 'verification_percentage')
    list_filter = ('timestamp',)
    readonly_fields = ('timestamp', 'total_embeddings', 'synced_count', 'verified_count',
                      'failed_count', 'pending_count', 'core_total_nodes',
                      'sync_percentage', 'verification_percentage')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
