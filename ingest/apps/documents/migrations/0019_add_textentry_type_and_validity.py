# Add text_type and validity dates to TextEntry model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0018_add_textentry_to_chunk'),
    ]

    operations = [
        migrations.AddField(
            model_name='textentry',
            name='text_type',
            field=models.CharField(
                choices=[
                    ('circular', 'بخشنامه'),
                    ('verdict', 'رای'),
                    ('instruction', 'دستورالعمل'),
                    ('bill', 'لایحه'),
                    ('educational', 'آموزشی'),
                    ('other', 'سایر'),
                ],
                default='other',
                max_length=20,
                verbose_name='نوع متن',
                help_text='نوع محتوای متنی'
            ),
        ),
        migrations.AddField(
            model_name='textentry',
            name='validity_start_date',
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name='تاریخ شروع اعتبار',
                help_text='در صورت خالی بودن، از ابتدا معتبر است'
            ),
        ),
        migrations.AddField(
            model_name='textentry',
            name='validity_end_date',
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name='تاریخ پایان اعتبار',
                help_text='در صورت خالی بودن، همچنان معتبر است'
            ),
        ),
    ]
