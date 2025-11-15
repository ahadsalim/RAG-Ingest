"""Views for user activity reporting in admin panel."""
import csv
from datetime import datetime, timedelta
from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Sum, Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
# Safe import for JalaliDateField
try:
    from .fields import JalaliDateField
except ImportError:
    from django.forms import DateField as JalaliDateField
from .models import UserActivityLog, UserWorkSession


class UserActivityReportForm(forms.Form):
    """Form for user activity report with Jalali date inputs."""
    
    start_date = JalaliDateField(
        label='از تاریخ (شمسی)',
        required=True
    )
    
    end_date = JalaliDateField(
        label='تا تاریخ (شمسی)',
        required=True
    )
    
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label='کاربر',
        required=False,
        empty_label='همه کاربران',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default dates (current month in Jalali)
        import jdatetime
        today = jdatetime.date.today()
        first_day = jdatetime.date(today.year, today.month, 1)
        
        if not self.is_bound:
            self.fields['start_date'].initial = first_day.togregorian()
            self.fields['end_date'].initial = today.togregorian()


@method_decorator(staff_member_required, name='dispatch')
class UserActivityReportView(TemplateView):
    """Admin view for generating user activity reports."""
    template_name = 'admin/accounts/user_activity_report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        user_id = self.request.GET.get('user')
        
        # Default to last 30 days if no dates provided
        if not start_date or not end_date:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
        else:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                messages.error(self.request, 'فرمت تاریخ نامعتبر است. از فرمت YYYY-MM-DD استفاده کنید.')
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=30)
        
        # Get users
        users = User.objects.all()
        if user_id:
            users = users.filter(id=user_id)
        
        # Generate report data
        report_data = []
        total_work_minutes = 0
        total_activities = 0
        
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
            
            # Calculate daily averages
            work_days = sessions.values('login_time__date').distinct().count()
            
            work_minutes = int(total_duration.total_seconds() / 60)
            total_work_minutes += work_minutes
            activity_count = activities.count()
            total_activities += activity_count
            
            user_data = {
                'user': user,
                'total_work_hours': self.format_duration(total_duration),
                'total_work_minutes': work_minutes,
                'work_days': work_days,
                'avg_hours_per_day': self.format_duration(
                    total_duration / work_days if work_days > 0 else timedelta(0)
                ),
                'total_sessions': sessions.count(),
                'total_activities': activity_count,
                'login_count': activities.filter(action='login').count(),
                'logout_count': activities.filter(action='logout').count(),
                'create_count': activities.filter(action='create').count(),
                'update_count': activities.filter(action='update').count(),
                'delete_count': activities.filter(action='delete').count(),
                'view_count': activities.filter(action='view').count(),
            }
            
            report_data.append(user_data)
        
        context.update({
            'report_data': report_data,
            'start_date': start_date,
            'end_date': end_date,
            'selected_user': user_id,
            'all_users': User.objects.all(),
            'total_work_hours': self.format_duration(timedelta(minutes=total_work_minutes)),
            'total_activities': total_activities,
            'user_count': len(report_data),
            'avg_work_hours': self.format_duration(
                timedelta(minutes=total_work_minutes / len(report_data)) if report_data else timedelta(0)
            ),
        })
        
        return context
    
    def format_duration(self, duration):
        """Format duration as HH:MM."""
        if not duration:
            return "00:00"
        
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"


@staff_member_required
def export_user_activity_csv(request):
    """Export user activity report as CSV."""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    user_id = request.GET.get('user')
    
    # Default to last 30 days if no dates provided
    if not start_date or not end_date:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
    else:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return HttpResponse('فرمت تاریخ نامعتبر است.', status=400)
    
    # Get users
    users = User.objects.all()
    if user_id:
        users = users.filter(id=user_id)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="user_activity_report_{start_date}_to_{end_date}.csv"'
    
    # Add BOM for proper UTF-8 encoding in Excel
    response.write('\ufeff')
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'نام کاربری', 'نام کامل', 'ایمیل', 'ساعات کار', 'دقایق کار', 'روزهای کار',
        'میانگین ساعت روزانه', 'تعداد جلسات', 'کل فعالیت‌ها', 'ورود', 'خروج',
        'ایجاد', 'ویرایش', 'حذف', 'مشاهده'
    ])
    
    # Write data
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
        
        # Calculate daily averages
        work_days = sessions.values('login_time__date').distinct().count()
        work_minutes = int(total_duration.total_seconds() / 60)
        
        def format_duration(duration):
            if not duration:
                return "00:00"
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours:02d}:{minutes:02d}"
        
        writer.writerow([
            user.username,
            user.get_full_name() or user.username,
            user.email,
            format_duration(total_duration),
            work_minutes,
            work_days,
            format_duration(total_duration / work_days if work_days > 0 else timedelta(0)),
            sessions.count(),
            activities.count(),
            activities.filter(action='login').count(),
            activities.filter(action='logout').count(),
            activities.filter(action='create').count(),
            activities.filter(action='update').count(),
            activities.filter(action='delete').count(),
            activities.filter(action='view').count(),
        ])
    
    return response


@staff_member_required
def user_activity_summary_json(request):
    """Get user activity summary as JSON for AJAX requests."""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    user_id = request.GET.get('user')
    
    # Default to last 30 days if no dates provided
    if not start_date or not end_date:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
    else:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'فرمت تاریخ نامعتبر است.'}, status=400)
    
    # Get users
    users = User.objects.all()
    if user_id:
        users = users.filter(id=user_id)
    
    summary_data = {
        'total_users': users.count(),
        'total_work_minutes': 0,
        'total_activities': 0,
        'date_range': f'{start_date} تا {end_date}',
        'users': []
    }
    
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
        
        work_minutes = int(total_duration.total_seconds() / 60)
        activity_count = activities.count()
        
        summary_data['total_work_minutes'] += work_minutes
        summary_data['total_activities'] += activity_count
        
        summary_data['users'].append({
            'username': user.username,
            'full_name': user.get_full_name() or user.username,
            'work_minutes': work_minutes,
            'activities': activity_count
        })
    
    return JsonResponse(summary_data)
