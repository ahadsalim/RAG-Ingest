# Generated migration - Add node_id to Chunk & qaentry FK to Chunk

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0003_alter_instrumentwork_unique_together'),
    ]

    operations = [
        # Make unit nullable in Chunk (برای QAEntry chunks)
        migrations.AlterField(
            model_name='chunk',
            name='unit',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='chunks',
                to='documents.legalunit',
                verbose_name='واحد حقوقی'
            ),
        ),
        
        # Add qaentry FK to Chunk
        migrations.AddField(
            model_name='chunk',
            name='qaentry',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='chunks',
                to='documents.qaentry',
                verbose_name='ورودی QA'
            ),
        ),
        
        # Add node_id to Chunk
        migrations.AddField(
            model_name='chunk',
            name='node_id',
            field=models.UUIDField(
                null=True,
                blank=True,
                unique=True,
                db_index=True,
                verbose_name='Node ID در Core'
            ),
        ),
        
        # Historical tables
        migrations.AlterField(
            model_name='historicalchunk',
            name='unit',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='+',
                to='documents.legalunit',
                verbose_name='واحد حقوقی',
                db_constraint=False
            ),
        ),
        
        migrations.AddField(
            model_name='historicalchunk',
            name='qaentry',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='+',
                to='documents.qaentry',
                verbose_name='ورودی QA',
                db_constraint=False
            ),
        ),
        
        migrations.AddField(
            model_name='historicalchunk',
            name='node_id',
            field=models.UUIDField(
                null=True,
                blank=True,
                db_index=True,
                verbose_name='Node ID در Core'
            ),
        ),
    ]
