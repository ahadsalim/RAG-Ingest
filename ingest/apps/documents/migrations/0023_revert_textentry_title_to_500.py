# Revert TextEntry title field max_length from 1000 to 500

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0022_increase_textentry_title_length'),
    ]

    operations = [
        migrations.AlterField(
            model_name='textentry',
            name='title',
            field=models.CharField(max_length=500, verbose_name='عنوان'),
        ),
        migrations.AlterField(
            model_name='historicaltextentry',
            name='title',
            field=models.CharField(max_length=500, verbose_name='عنوان'),
        ),
    ]
