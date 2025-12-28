# Generated manually on 2025-12-28
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0023_revert_textentry_title_to_500'),
    ]

    operations = [
        migrations.AlterField(
            model_name='instrumentwork',
            name='doc_type',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('law', 'قانون'),
                    ('bylaw', 'آیین‌نامه'),
                    ('decree', 'مصوبه'),
                    ('other', 'سایر')
                ],
                default='law',
                verbose_name='نوع سند'
            ),
        ),
        migrations.AlterField(
            model_name='historicalinstrumentwork',
            name='doc_type',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('law', 'قانون'),
                    ('bylaw', 'آیین‌نامه'),
                    ('decree', 'مصوبه'),
                    ('other', 'سایر')
                ],
                default='law',
                verbose_name='نوع سند'
            ),
        ),
    ]
