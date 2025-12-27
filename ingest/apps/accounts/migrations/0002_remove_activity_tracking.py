# Remove UserActivityLog and UserWorkSession models
# These models are no longer needed as the activity tracking feature was removed

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.DeleteModel(
            name='UserActivityLog',
        ),
        migrations.DeleteModel(
            name='UserWorkSession',
        ),
        migrations.DeleteModel(
            name='ClockedScheduleProxy',
        ),
        migrations.DeleteModel(
            name='IntervalScheduleProxy',
        ),
    ]
