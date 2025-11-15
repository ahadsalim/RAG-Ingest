from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Initialize pgvector extension in PostgreSQL'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            try:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                self.stdout.write(
                    self.style.SUCCESS('Successfully initialized pgvector extension')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to initialize pgvector: {e}')
                )
