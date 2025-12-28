# Increase TextEntry title field max_length from 500 to 1000

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0021_change_textentry_title_to_charfield'),
    ]

    operations = [
        migrations.AlterField(
            model_name='textentry',
            name='title',
            field=models.CharField(max_length=1000, verbose_name='عنوان'),
        ),
        migrations.AlterField(
            model_name='historicaltextentry',
            name='title',
            field=models.CharField(max_length=1000, verbose_name='عنوان'),
        ),
    ]
