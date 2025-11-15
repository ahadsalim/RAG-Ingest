"""Admin view for user activity report."""

import csv
from datetime import datetime, timedelta, time
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum, Q, F, Case, When, DurationField
from django.db.models.functions import TruncDate, Extract
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from .models import UserActivityLog, UserWorkSession
from ingest.admin import admin_site

@staff_member_required
@require_http_methods(["GET", "POST"])
@csrf_protect
def user_activity_report(request):
    """
    User activity report view integrated with Django admin.
    Supports GET for rendering and POST for CSV export.
    """
    
    # Get filter parameters from request
    from_date = request.GET.get('from', '')
    to_date = request.GET.get('to', '')
    user_id = request.GET.get('user_id', '')
    export_csv = request.GET.get('export') == 'csv' or request.POST.get('export') == 'csv'
    
    # Default date range (last 30 days)
    if not from_date or not to_date:
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        from_date = start_date.strftime('%Y-%m-%d')
        to_date = end_date.strftime('%Y-%m-%d')
    
    # Get users for filter dropdown
    all_users = User.objects.filter(is_active=True).order_by('username')
    selected_user = None
    if user_id:
        try:
            selected_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            pass
    
    # Generate actual report data
    report_data = generate_user_activity_report(from_date, to_date, selected_user)
    
    # Calculate summary stats
    user_count = all_users.count()
    total_activities = sum(row.get('activities', 0) for row in report_data)
    total_work_hours = sum(row.get('work_hours', 0) for row in report_data)
    avg_work_hours = total_work_hours / max(len(report_data), 1)
    
    # Handle CSV export
    if export_csv:
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="user_activity_{from_date}_{to_date}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'کاربر', 'تاریخ', 'ساعات کار', 'فعالیت‌ها', 
            'تعداد ورود', 'اولین ورود', 'آخرین خروج', 'مدت کل'
        ])
        
        for row in report_data:
            writer.writerow([
                row.get('user', ''),
                row.get('date', ''),
                row.get('work_hours', 0),
                row.get('activities', 0),
                row.get('login_count', 0),
                row.get('first_login', '-'),
                row.get('last_logout', '-'),
                row.get('total_duration_str', '00:00:00'),
            ])
        
        return response
    
    # Get admin context (includes sidebar and all admin features)
    context = admin_site.each_context(request)
    
    # Add report specific context
    context.update({
        'title': 'گزارش فعالیت کاربران',
        'from_date': from_date,
        'to_date': to_date,
        'user_id': user_id,
        'all_users': all_users,
        'selected_user': selected_user,
        'report_data': report_data,
        'user_count': user_count,
        'total_activities': total_activities,
        'total_work_hours': round(total_work_hours, 2),
        'avg_work_hours': round(avg_work_hours, 2),
    })
    
    return render(request, 'admin/accounts/user_activity_report_new.html', context)


def generate_user_activity_report(from_date, to_date, selected_user=None):
    """
    Generate detailed user activity report with accurate work hours calculation.
    """
    try:
        start_date = datetime.strptime(from_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(to_date, '%Y-%m-%d').date()
    except ValueError:
        return []
    
    # Base queryset for users
    users_query = User.objects.filter(is_active=True)
    if selected_user:
        users_query = users_query.filter(id=selected_user.id)
    
    report_data = []
    
    for user in users_query:
        # Get work sessions for the date range
        sessions = UserWorkSession.objects.filter(
            user=user,
            login_time__date__gte=start_date,
            login_time__date__lte=end_date
        ).order_by('login_time')
        
        # Group sessions by date
        daily_data = {}
        
        for session in sessions:
            session_date = session.login_time.date()
            
            if session_date not in daily_data:
                daily_data[session_date] = {
                    'user': user.username,
                    'user_id': user.id,
                    'date': session_date,
                    'date_str': session_date.strftime('%Y-%m-%d'),
                    'sessions': [],
                    'total_duration': timedelta(0),
                    'activities': 0,
                    'login_count': 0,
                    'first_login': None,
                    'last_logout': None,
                }
            
            # Calculate session duration
            if session.logout_time:
                duration = session.logout_time - session.login_time
                # Remove breaks longer than 1 hour (likely lunch or long breaks)
                if duration <= timedelta(hours=12):  # Max 12 hours per session
                    daily_data[session_date]['total_duration'] += duration
            else:
                # If no logout time, assume session ended at end of day or current time
                end_time = min(
                    timezone.now(),
                    session.login_time.replace(hour=18, minute=0, second=0, microsecond=0)
                )
                if end_time > session.login_time:
                    duration = end_time - session.login_time
                    if duration <= timedelta(hours=12):
                        daily_data[session_date]['total_duration'] += duration
            
            # Track session details
            daily_data[session_date]['sessions'].append({
                'login': session.login_time,
                'logout': session.logout_time,
                'duration': session.total_duration,
                'activities': session.activities_count,
            })
            
            daily_data[session_date]['activities'] += session.activities_count
            daily_data[session_date]['login_count'] += 1
            
            # Track first login and last logout
            if not daily_data[session_date]['first_login'] or session.login_time < daily_data[session_date]['first_login']:
                daily_data[session_date]['first_login'] = session.login_time
            
            if session.logout_time:
                if not daily_data[session_date]['last_logout'] or session.logout_time > daily_data[session_date]['last_logout']:
                    daily_data[session_date]['last_logout'] = session.logout_time
        
        # If no work sessions, check activity logs for basic activity
        if not daily_data:
            activity_logs = UserActivityLog.objects.filter(
                user=user,
                timestamp__date__gte=start_date,
                timestamp__date__lte=end_date
            ).exclude(action='view')  # Exclude view actions as they're too frequent
            
            if activity_logs.exists():
                # Group activities by date
                for log in activity_logs:
                    log_date = log.timestamp.date()
                    
                    if log_date not in daily_data:
                        daily_data[log_date] = {
                            'user': user.username,
                            'user_id': user.id,
                            'date': log_date,
                            'date_str': log_date.strftime('%Y-%m-%d'),
                            'sessions': [],
                            'total_duration': timedelta(0),
                            'activities': 0,
                            'login_count': 0,
                            'first_login': None,
                            'last_logout': None,
                        }
                    
                    daily_data[log_date]['activities'] += 1
        
        # Convert daily data to report format
        for date_str, data in daily_data.items():
            # Calculate work hours (convert timedelta to hours)
            total_seconds = data['total_duration'].total_seconds()
            work_hours = round(total_seconds / 3600, 2) if total_seconds > 0 else 0
            
            # If no sessions but activities exist, estimate minimum work time
            if work_hours == 0 and data['activities'] > 0:
                # Estimate 15 minutes per significant activity
                estimated_minutes = min(data['activities'] * 15, 480)  # Max 8 hours
                work_hours = round(estimated_minutes / 60, 2)
            
            report_data.append({
                'user': data['user'],
                'user_id': data['user_id'],
                'date': data['date'],
                'date_str': data['date_str'],
                'work_hours': work_hours,
                'activities': data['activities'],
                'login_count': data['login_count'],
                'first_login': data['first_login'].strftime('%H:%M') if data['first_login'] else '-',
                'last_logout': data['last_logout'].strftime('%H:%M') if data['last_logout'] else '-',
                'sessions_detail': data['sessions'],
                'total_duration_str': str(data['total_duration']).split('.')[0] if data['total_duration'] else '00:00:00',
            })
    
    # Sort by date and user
    report_data.sort(key=lambda x: (x['date_str'], x['user']))
    
    return report_data


def calculate_payroll_hours(user, start_date, end_date):
    """
    Calculate accurate payroll hours for a user in a date range.
    """
    sessions = UserWorkSession.objects.filter(
        user=user,
        login_time__date__gte=start_date,
        login_time__date__lte=end_date
    )
    
    total_hours = 0
    daily_hours = {}
    
    for session in sessions:
        date = session.login_time.date()
        
        if session.logout_time:
            # Calculate actual session duration
            duration = session.logout_time - session.login_time
            
            # Apply business rules
            session_hours = duration.total_seconds() / 3600
            
            # Cap daily hours at 12 (remove unrealistic long sessions)
            if session_hours > 12:
                session_hours = 8  # Default to standard work day
            
            # Minimum session time (ignore very short sessions < 15 minutes)
            if session_hours < 0.25:
                session_hours = 0
            
            if date not in daily_hours:
                daily_hours[date] = 0
            
            daily_hours[date] += session_hours
    
    # Cap daily hours at 10 hours maximum
    for date, hours in daily_hours.items():
        if hours > 10:
            daily_hours[date] = 10
        total_hours += daily_hours[date]
    
    return round(total_hours, 2), daily_hours


@staff_member_required
@require_http_methods(["GET", "POST"])
@csrf_protect
def payroll_summary_report(request):
    """
    Monthly payroll summary report for salary calculation.
    """
    # Get filter parameters
    month = request.GET.get('month', timezone.now().strftime('%Y-%m'))
    user_id = request.GET.get('user_id', '')
    export_csv = request.GET.get('export') == 'csv'
    
    try:
        year, month_num = map(int, month.split('-'))
        start_date = timezone.datetime(year, month_num, 1).date()
        if month_num == 12:
            end_date = timezone.datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = timezone.datetime(year, month_num + 1, 1).date() - timedelta(days=1)
    except ValueError:
        # Default to current month
        now = timezone.now()
        start_date = now.replace(day=1).date()
        end_date = (start_date.replace(month=start_date.month + 1) - timedelta(days=1)) if start_date.month < 12 else start_date.replace(year=start_date.year + 1, month=1) - timedelta(days=1)
        month = start_date.strftime('%Y-%m')
    
    # Get users
    all_users = User.objects.filter(is_active=True).order_by('username')
    selected_user = None
    if user_id:
        try:
            selected_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            pass
    
    # Generate payroll data
    payroll_data = []
    users_query = all_users if not selected_user else [selected_user]
    
    for user in users_query:
        total_hours, daily_breakdown = calculate_payroll_hours(user, start_date, end_date)
        
        # Calculate working days (exclude weekends)
        working_days = 0
        worked_days = len(daily_breakdown)
        
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() < 5:  # Monday = 0, Sunday = 6
                working_days += 1
            current_date += timedelta(days=1)
        
        # Calculate attendance percentage
        attendance_rate = (worked_days / working_days * 100) if working_days > 0 else 0
        
        # Calculate average daily hours
        avg_daily_hours = total_hours / worked_days if worked_days > 0 else 0
        
        # Estimate monthly salary (you can adjust these rates)
        hourly_rate = 50000  # 50,000 Toman per hour (adjust as needed)
        gross_salary = total_hours * hourly_rate
        
        # Apply attendance bonus/penalty
        if attendance_rate >= 95:
            attendance_bonus = gross_salary * 0.1  # 10% bonus
        elif attendance_rate < 80:
            attendance_bonus = -gross_salary * 0.05  # 5% penalty
        else:
            attendance_bonus = 0
        
        final_salary = gross_salary + attendance_bonus
        
        payroll_data.append({
            'user': user.username,
            'user_id': user.id,
            'full_name': user.get_full_name() or user.username,
            'total_hours': round(total_hours, 2),
            'worked_days': worked_days,
            'working_days': working_days,
            'attendance_rate': round(attendance_rate, 1),
            'avg_daily_hours': round(avg_daily_hours, 2),
            'hourly_rate': hourly_rate,
            'gross_salary': int(gross_salary),
            'attendance_bonus': int(attendance_bonus),
            'final_salary': int(final_salary),
            'daily_breakdown': daily_breakdown,
        })
    
    # Handle CSV export
    if export_csv:
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="payroll_summary_{month}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'کاربر', 'نام کامل', 'کل ساعات', 'روزهای کاری', 'نرخ حضور (%)',
            'میانگین ساعات روزانه', 'نرخ ساعتی', 'حقوق پایه', 'پاداش/جریمه حضور', 'حقوق نهایی'
        ])
        
        for row in payroll_data:
            writer.writerow([
                row['user'],
                row['full_name'],
                row['total_hours'],
                f"{row['worked_days']}/{row['working_days']}",
                f"{row['attendance_rate']}%",
                row['avg_daily_hours'],
                f"{row['hourly_rate']:,}",
                f"{row['gross_salary']:,}",
                f"{row['attendance_bonus']:,}",
                f"{row['final_salary']:,}",
            ])
        
        return response
    
    # Calculate summary statistics
    total_employees = len(payroll_data)
    total_salary_budget = sum(row['final_salary'] for row in payroll_data)
    avg_hours_per_employee = sum(row['total_hours'] for row in payroll_data) / max(total_employees, 1)
    avg_attendance = sum(row['attendance_rate'] for row in payroll_data) / max(total_employees, 1)
    
    # Get admin context (includes sidebar and all admin features)
    context = admin_site.each_context(request)
    
    # Add report specific context
    context.update({
        'title': f'گزارش حقوق و دستمزد - {month}',
        'month': month,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'user_id': user_id,
        'all_users': all_users,
        'selected_user': selected_user,
        'payroll_data': payroll_data,
        
        # Summary stats
        'total_employees': total_employees,
        'total_salary_budget': int(total_salary_budget),
        'avg_hours_per_employee': round(avg_hours_per_employee, 2),
        'avg_attendance': round(avg_attendance, 1),
    })
    
    return render(request, 'admin/accounts/payroll_summary_report.html', context)
