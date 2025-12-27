# Change TextEntry title field from CharField to TextField

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0019_add_textentry_type_and_validity'),
    ]

    operations = [
        migrations.AlterField(
            model_name='textentry',
            name='title',
            field=models.TextField(verbose_name='عنوان'),
        ),
    ]
