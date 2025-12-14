# Generated manually for M2M to through model conversion

from django.db import migrations, models
import django.db.models.deletion


def migrate_qaentry_tags_forward(apps, schema_editor):
    """Migrate QAEntry tags from auto M2M to through model."""
    QAEntry = apps.get_model('documents', 'QAEntry')
    QAEntryVocabularyTerm = apps.get_model('documents', 'QAEntryVocabularyTerm')
    
    for qa in QAEntry.objects.all():
        for term in qa.tags.all():
            QAEntryVocabularyTerm.objects.get_or_create(
                qa_entry=qa,
                vocabulary_term=term,
                defaults={'weight': 1.0}
            )


def migrate_qaentry_units_forward(apps, schema_editor):
    """Migrate QAEntry related_units from auto M2M to through model."""
    QAEntry = apps.get_model('documents', 'QAEntry')
    QAEntryRelatedUnit = apps.get_model('documents', 'QAEntryRelatedUnit')
    
    for qa in QAEntry.objects.all():
        for unit in qa.related_units.all():
            QAEntryRelatedUnit.objects.get_or_create(
                qa_entry=qa,
                legal_unit=unit
            )


def migrate_textentry_units_forward(apps, schema_editor):
    """Migrate TextEntry related_units from auto M2M to through model."""
    TextEntry = apps.get_model('documents', 'TextEntry')
    TextEntryRelatedUnit = apps.get_model('documents', 'TextEntryRelatedUnit')
    
    for te in TextEntry.objects.all():
        for unit in te.related_units.all():
            TextEntryRelatedUnit.objects.get_or_create(
                text_entry=te,
                legal_unit=unit
            )


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0016_update_qaentry_remove_status'),
        ('masterdata', '0001_initial'),
    ]

    operations = [
        # Step 1: Create through models
        migrations.CreateModel(
            name='QAEntryVocabularyTerm',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weight', models.FloatField(default=1.0, help_text='وزن برچسب (1.0 = عادی)', verbose_name='وزن')),
                ('qa_entry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='documents.qaentry', verbose_name='پرسش و پاسخ')),
                ('vocabulary_term', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='masterdata.vocabularyterm', verbose_name='برچسب')),
            ],
            options={
                'verbose_name': 'برچسب پرسش و پاسخ',
                'verbose_name_plural': 'برچسب‌های پرسش و پاسخ',
                'unique_together': {('qa_entry', 'vocabulary_term')},
            },
        ),
        migrations.CreateModel(
            name='QAEntryRelatedUnit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('qa_entry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='documents.qaentry', verbose_name='پرسش و پاسخ')),
                ('legal_unit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='documents.legalunit', verbose_name='بند مرتبط')),
            ],
            options={
                'verbose_name': 'بند مرتبط پرسش و پاسخ',
                'verbose_name_plural': 'بندهای مرتبط پرسش و پاسخ',
                'unique_together': {('qa_entry', 'legal_unit')},
            },
        ),
        migrations.CreateModel(
            name='TextEntryRelatedUnit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text_entry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='documents.textentry', verbose_name='متن')),
                ('legal_unit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='documents.legalunit', verbose_name='بند مرتبط')),
            ],
            options={
                'verbose_name': 'بند مرتبط متن',
                'verbose_name_plural': 'بندهای مرتبط متن',
                'unique_together': {('text_entry', 'legal_unit')},
            },
        ),
        
        # Step 2: Migrate data from old M2M tables to new through models
        migrations.RunPython(migrate_qaentry_tags_forward, migrations.RunPython.noop),
        migrations.RunPython(migrate_qaentry_units_forward, migrations.RunPython.noop),
        migrations.RunPython(migrate_textentry_units_forward, migrations.RunPython.noop),
        
        # Step 3: Remove old M2M fields
        migrations.RemoveField(
            model_name='qaentry',
            name='tags',
        ),
        migrations.RemoveField(
            model_name='qaentry',
            name='related_units',
        ),
        migrations.RemoveField(
            model_name='textentry',
            name='related_units',
        ),
        
        # Step 4: Add new M2M fields with through models
        migrations.AddField(
            model_name='qaentry',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='qa_entries', through='documents.QAEntryVocabularyTerm', to='masterdata.vocabularyterm', verbose_name='برچسب‌ها'),
        ),
        migrations.AddField(
            model_name='qaentry',
            name='related_units',
            field=models.ManyToManyField(blank=True, related_name='related_qa_entries', through='documents.QAEntryRelatedUnit', to='documents.legalunit', verbose_name='بندهای مرتبط'),
        ),
        migrations.AddField(
            model_name='textentry',
            name='related_units',
            field=models.ManyToManyField(blank=True, related_name='related_text_entries', through='documents.TextEntryRelatedUnit', to='documents.legalunit', verbose_name='بندهای مرتبط'),
        ),
    ]
