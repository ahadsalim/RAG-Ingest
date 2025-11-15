# Generated migration for documents app
# This migration creates the initial database schema for the documents app

from django.db import migrations, models
import django.db.models.deletion
import mptt.fields
import simple_history.models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('masterdata', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        # This is a placeholder migration
        # Actual models will be created when makemigrations is run in development
        migrations.RunSQL(
            sql="-- Initial migration placeholder for documents app",
            reverse_sql="-- Reverse migration placeholder",
        ),
    ]
