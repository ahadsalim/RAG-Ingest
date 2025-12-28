# Generated manually on 2025-12-28
# Fix missing fields in HistoricalTextEntry

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0025_update_instrumentwork_doc_type_choices'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicaltextentry',
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
                verbose_name='نوع متن'
            ),
        ),
        migrations.AddField(
            model_name='historicaltextentry',
            name='validity_start_date',
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name='تاریخ شروع اعتبار',
                help_text='در صورت خالی بودن، از ابتدا معتبر است'
            ),
        ),
        migrations.AddField(
            model_name='historicaltextentry',
            name='validity_end_date',
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name='تاریخ پایان اعتبار',
                help_text='در صورت خالی بودن، همچنان معتبر است'
            ),
        ),
    ]
