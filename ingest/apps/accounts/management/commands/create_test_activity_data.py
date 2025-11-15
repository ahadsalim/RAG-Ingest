"""
Management command to create test activity data for payroll report testing.
"""

from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from ingest.apps.accounts.models import UserWorkSession, UserActivityLog
import random


class Command(BaseCommand):
    help = 'Create test activity data for payroll report testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to create data for (default: 30)'
        )
        parser.add_argument(
            '--users',
            type=str,
            default='',
            help='Comma-separated list of usernames (default: all active users)'
        )

    def handle(self, *args, **options):
        days = options['days']
        user_list = options['users']
        
        # Get users
        if user_list:
            usernames = [u.strip() for u in user_list.split(',')]
            users = User.objects.filter(username__in=usernames, is_active=True)
        else:
            users = User.objects.filter(is_active=True)
        
        if not users.exists():
            self.stdout.write(
                self.style.ERROR('No active users found!')
            )
            return
        
        # Clear existing test data
        self.stdout.write('Clearing existing test data...')
        UserWorkSession.objects.filter(
            login_time__gte=timezone.now() - timedelta(days=days)
        ).delete()
        UserActivityLog.objects.filter(
            timestamp__gte=timezone.now() - timedelta(days=days)
        ).delete()
        
        # Create test data
        self.stdout.write(f'Creating test data for {users.count()} users over {days} days...')
        
        for user in users:
            self.create_user_data(user, days)
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created test data for {users.count()} users')
        )

    def create_user_data(self, user, days):
        """Create realistic work session and activity data for a user."""
        
        for day_offset in range(days):
            # Skip some days (weekends, sick days, etc.)
            if random.random() < 0.2:  # 20% chance to skip a day
                continue
            
            date = timezone.now().date() - timedelta(days=day_offset)
            
            # Create 1-3 work sessions per day
            session_count = random.choices([1, 2, 3], weights=[60, 30, 10])[0]
            
            daily_activities = 0
            
            for session_num in range(session_count):
                # Generate realistic work hours
                if session_num == 0:  # Main work session
                    start_hour = random.randint(7, 10)  # 7 AM to 10 AM
                    work_duration = random.uniform(4, 9)  # 4 to 9 hours
                else:  # Additional sessions (overtime, evening work)
                    start_hour = random.randint(14, 20)  # 2 PM to 8 PM
                    work_duration = random.uniform(1, 4)  # 1 to 4 hours
                
                start_minute = random.randint(0, 59)
                
                login_time = timezone.make_aware(
                    datetime.combine(date, datetime.min.time()) + 
                    timedelta(hours=start_hour, minutes=start_minute)
                )
                
                logout_time = login_time + timedelta(hours=work_duration)
                
                # Add some randomness to logout time
                logout_time += timedelta(minutes=random.randint(-30, 30))
                
                # Create work session
                session = UserWorkSession.objects.create(
                    user=user,
                    login_time=login_time,
                    logout_time=logout_time,
                    ip_address='127.0.0.1',
                    activities_count=0  # Will be updated below
                )
                
                # Calculate session duration
                session.calculate_duration()
                
                # Create activities during this session
                session_activities = random.randint(5, 25)  # 5 to 25 activities per session
                session.activities_count = session_activities
                session.save()
                
                daily_activities += session_activities
                
                # Create individual activity logs
                self.create_activity_logs(user, login_time, logout_time, session_activities)
        
        self.stdout.write(f'  Created data for {user.username}')

    def create_activity_logs(self, user, start_time, end_time, activity_count):
        """Create individual activity logs for a work session."""
        
        actions = ['create', 'update', 'delete', 'view']
        action_weights = [20, 40, 10, 30]  # view is most common
        
        models = [
            'LegalUnit', 'Document', 'Category', 'Tag', 'Comment',
            'Jurisdiction', 'IssuingAuthority', 'Language'
        ]
        
        session_duration = end_time - start_time
        
        for i in range(activity_count):
            # Distribute activities throughout the session
            activity_offset = (session_duration / activity_count) * i
            activity_time = start_time + activity_offset
            
            # Add some randomness
            activity_time += timedelta(minutes=random.randint(-5, 5))
            
            action = random.choices(actions, weights=action_weights)[0]
            model_name = random.choice(models)
            
            UserActivityLog.objects.create(
                user=user,
                action=action,
                model_name=model_name,
                object_id=str(random.randint(1, 1000)),
                description=f'{action} {model_name}',
                ip_address='127.0.0.1',
                timestamp=activity_time
            )
