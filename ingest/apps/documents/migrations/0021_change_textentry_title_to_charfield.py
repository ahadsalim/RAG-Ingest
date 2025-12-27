# Change TextEntry title field from TextField to CharField

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0020_change_textentry_title_to_textfield'),
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
