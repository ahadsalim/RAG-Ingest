"""
Management command to setup periodic tasks from settings to database.
این command باید بعد از نصب مجدد یا تغییر سرور اجرا شود.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
import json


class Command(BaseCommand):
    help = 'Setup periodic tasks from CELERY_BEAT_SCHEDULE to database'

    def handle(self, *args, **options):
        self.stdout.write('🔧 تنظیم task های دوره‌ای...')
        self.stdout.write('=' * 70)
        
        beat_schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', {})
        
        if not beat_schedule:
            self.stdout.write(self.style.WARNING('⚠️  هیچ CELERY_BEAT_SCHEDULE در settings یافت نشد'))
            return
        
        created_count = 0
        updated_count = 0
        
        for task_name, task_config in beat_schedule.items():
            try:
                # Parse schedule
                schedule = task_config['schedule']
                
                # Create or get schedule object
                if hasattr(schedule, 'minute'):  # CrontabSchedule
                    schedule_obj, _ = CrontabSchedule.objects.get_or_create(
                        minute=str(schedule.minute),
                        hour=str(schedule.hour),
                        day_of_week=str(schedule.day_of_week),
                        day_of_month=str(schedule.day_of_month),
                        month_of_year=str(schedule.month_of_year),
                    )
                    schedule_type = 'crontab'
                elif hasattr(schedule, 'run_every'):  # IntervalSchedule
                    total_seconds = int(schedule.run_every.total_seconds())
                    schedule_obj, _ = IntervalSchedule.objects.get_or_create(
                        every=total_seconds,
                        period=IntervalSchedule.SECONDS,
                    )
                    schedule_type = 'interval'
                else:
                    self.stdout.write(
                        self.style.ERROR(f'❌ نوع schedule برای {task_name} شناخته نشده')
                    )
                    continue
                
                # Create or update PeriodicTask
                task, created = PeriodicTask.objects.get_or_create(
                    name=task_name,
                    defaults={
                        'task': task_config['task'],
                        schedule_type: schedule_obj,
                        'enabled': True,
                    }
                )
                
                if not created:
                    # Update existing task
                    task.task = task_config['task']
                    if schedule_type == 'crontab':
                        task.crontab = schedule_obj
                        task.interval = None
                    else:
                        task.interval = schedule_obj
                        task.crontab = None
                    task.enabled = True
                    task.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'🔄 بروزرسانی: {task_name}')
                    )
                else:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ ایجاد شد: {task_name}')
                    )
                
                # Show schedule info
                self.stdout.write(f'   📋 Task: {task_config["task"]}')
                if schedule_type == 'crontab':
                    self.stdout.write(
                        f'   ⏰ Schedule: {schedule}'
                    )
                else:
                    self.stdout.write(
                        f'   ⏰ Schedule: Every {schedule.run_every}'
                    )
                self.stdout.write('')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ خطا در تنظیم {task_name}: {e}')
                )
        
        self.stdout.write('=' * 70)
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ خلاصه: {created_count} ایجاد شد، {updated_count} بروزرسانی شد'
            )
        )
        self.stdout.write('')
        self.stdout.write('💡 برای بررسی task های فعال:')
        self.stdout.write('   https://ingest.arpanet.ir/admin/django_celery_beat/periodictask/')
