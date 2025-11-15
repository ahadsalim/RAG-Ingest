"""Management command to generate user activity reports for payroll calculation."""
import csv
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q
from django.utils import timezone
from ingest.apps.accounts.models import UserActivityLog, UserWorkSession


class Command(BaseCommand):
    help = 'Generate user activity report for payroll calculation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date (YYYY-MM-DD format)',
            required=True
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date (YYYY-MM-DD format)',
            required=True
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Username to filter (optional)',
            required=False
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output CSV file path',
            default='user_activity_report.csv'
        )
        parser.add_argument(
            '--format',
            choices=['csv', 'console'],
            default='console',
            help='Output format'
        )

    def handle(self, *args, **options):
        try:
            start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
        except ValueError:
            raise CommandError('Invalid date format. Use YYYY-MM-DD')

        if start_date > end_date:
            raise CommandError('Start date must be before end date')

        # Filter users
        users = User.objects.all()
        if options['user']:
            users = users.filter(username=options['user'])

        report_data = []
        
        for user in users:
            # Get work sessions in date range
            sessions = UserWorkSession.objects.filter(
                user=user,
                login_time__date__range=[start_date, end_date]
            )
            
            # Calculate total work time
            total_duration = sessions.aggregate(
                total=Sum('total_duration')
            )['total'] or timedelta(0)
            
            # Get activity counts
            activities = UserActivityLog.objects.filter(
                user=user,
                timestamp__date__range=[start_date, end_date]
            )
            
            activity_counts = activities.values('action').annotate(
                count=Count('id')
            )
            
            # Calculate daily averages
            work_days = sessions.values('login_time__date').distinct().count()
            
            user_data = {
                'username': user.username,
                'full_name': user.get_full_name() or user.username,
                'email': user.email,
                'total_work_hours': self.format_duration(total_duration),
                'total_work_minutes': int(total_duration.total_seconds() / 60),
                'work_days': work_days,
                'avg_hours_per_day': self.format_duration(
                    total_duration / work_days if work_days > 0 else timedelta(0)
                ),
                'total_sessions': sessions.count(),
                'total_activities': activities.count(),
                'login_count': activities.filter(action='login').count(),
                'logout_count': activities.filter(action='logout').count(),
                'create_count': activities.filter(action='create').count(),
                'update_count': activities.filter(action='update').count(),
                'delete_count': activities.filter(action='delete').count(),
                'view_count': activities.filter(action='view').count(),
            }
            
            # Add activity breakdown
            for activity in activity_counts:
                user_data[f"{activity['action']}_activities"] = activity['count']
            
            report_data.append(user_data)

        if options['format'] == 'csv':
            self.generate_csv_report(report_data, options['output'])
            self.stdout.write(
                self.style.SUCCESS(f'Report saved to {options["output"]}')
            )
        else:
            self.display_console_report(report_data, start_date, end_date)

    def format_duration(self, duration):
        """Format duration as HH:MM."""
        if not duration:
            return "00:00"
        
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"

    def generate_csv_report(self, data, filename):
        """Generate CSV report."""
        if not data:
            return
        
        fieldnames = data[0].keys()
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

    def display_console_report(self, data, start_date, end_date):
        """Display report in console."""
        self.stdout.write(
            self.style.SUCCESS(
                f'\n📊 گزارش فعالیت کاربران از {start_date} تا {end_date}\n'
            )
        )
        
        if not data:
            self.stdout.write(self.style.WARNING('هیچ داده‌ای یافت نشد.'))
            return
        
        # Summary table
        self.stdout.write('=' * 100)
        self.stdout.write(
            f"{'نام کاربری':<15} {'نام کامل':<20} {'ساعات کار':<10} {'روزهای کار':<10} "
            f"{'میانگین روزانه':<15} {'فعالیت‌ها':<10}"
        )
        self.stdout.write('=' * 100)
        
        total_minutes = 0
        total_activities = 0
        
        for user_data in data:
            total_minutes += user_data['total_work_minutes']
            total_activities += user_data['total_activities']
            
            self.stdout.write(
                f"{user_data['username']:<15} "
                f"{user_data['full_name']:<20} "
                f"{user_data['total_work_hours']:<10} "
                f"{user_data['work_days']:<10} "
                f"{user_data['avg_hours_per_day']:<15} "
                f"{user_data['total_activities']:<10}"
            )
        
        self.stdout.write('=' * 100)
        
        # Summary statistics
        total_hours = total_minutes / 60
        self.stdout.write(
            self.style.SUCCESS(
                f'\n📈 خلاصه آمار:\n'
                f'  • کل ساعات کار: {total_hours:.1f} ساعت\n'
                f'  • کل فعالیت‌ها: {total_activities}\n'
                f'  • تعداد کاربران: {len(data)}\n'
                f'  • میانگین ساعت کار هر کاربر: {total_hours/len(data):.1f} ساعت\n'
            )
        )
        
        # Detailed breakdown for each user
        for user_data in data:
            self.stdout.write(
                f'\n👤 {user_data["full_name"]} ({user_data["username"]}):'
            )
            self.stdout.write(f'  • ورود: {user_data["login_count"]} بار')
            self.stdout.write(f'  • خروج: {user_data["logout_count"]} بار')
            self.stdout.write(f'  • ایجاد: {user_data["create_count"]} مورد')
            self.stdout.write(f'  • ویرایش: {user_data["update_count"]} مورد')
            self.stdout.write(f'  • حذف: {user_data["delete_count"]} مورد')
            self.stdout.write(f'  • مشاهده: {user_data["view_count"]} مورد')
