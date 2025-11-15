from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date
from ingest.apps.documents.models import (
    InstrumentWork, InstrumentExpression, InstrumentManifestation,
    LegalUnit, InstrumentRelation
)


class Command(BaseCommand):
    help = 'Create sample FRBR data for testing the new schema'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creating sample FRBR data...'))
        
        # Create or get admin user
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(f'Created admin user with password: admin123')
        
        # Create sample tags
        tag_civil, _ = Tag.objects.get_or_create(
            name='حقوق مدنی',
            defaults={
                'slug': 'civil-law',
                'description': 'قوانین مربوط به حقوق مدنی',
                'category': 'subject',
                'color': '#3B82F6'
            }
        )
        
        tag_commercial, _ = Tag.objects.get_or_create(
            name='حقوق تجاری',
            defaults={
                'slug': 'commercial-law',
                'description': 'قوانین مربوط به حقوق تجاری',
                'category': 'subject',
                'color': '#10B981'
            }
        )
        
        # Create sample InstrumentWork
        work1, created = InstrumentWork.objects.get_or_create(
            local_slug='civil-code-1928',
            defaults={
                'title_official': 'قانون مدنی جمهوری اسلامی ایران',
                'doc_type': 'law',
                'jurisdiction': 'IR',
                'authority': 'parliament',
                'eli_uri_work': 'https://eli.example.ir/akn/ir/act/1928/civil-code',
                'subject_summary': 'قانون اساسی حقوق مدنی شامل اشخاص، اموال، تعهدات و قراردادها',
                'enactment_date': date(1928, 5, 20),
                'created_by': admin_user
            }
        )
        
        work2, created = InstrumentWork.objects.get_or_create(
            local_slug='commercial-code-1932',
            defaults={
                'title_official': 'قانون تجارت جمهوری اسلامی ایران',
                'doc_type': 'law',
                'jurisdiction': 'IR',
                'authority': 'parliament',
                'eli_uri_work': 'https://eli.example.ir/akn/ir/act/1932/commercial-code',
                'subject_summary': 'قانون تجارت شامل شرکت‌ها، اوراق تجاری و ورشکستگی',
                'enactment_date': date(1932, 6, 15),
                'created_by': admin_user
            }
        )
        
        # Create sample InstrumentExpression
        expr1, created = InstrumentExpression.objects.get_or_create(
            work=work1,
            language='fa',
            defaults={
                'eli_uri_expr': 'https://eli.example.ir/akn/ir/act/1928/civil-code/fa',
                'expression_date': date(1928, 5, 20),
                'consolidation_level': 'original',
                'created_by': admin_user
            }
        )
        
        expr2, created = InstrumentExpression.objects.get_or_create(
            work=work2,
            language='fa',
            defaults={
                'eli_uri_expr': 'https://eli.example.ir/akn/ir/act/1932/commercial-code/fa',
                'expression_date': date(1932, 6, 15),
                'consolidation_level': 'original',
                'created_by': admin_user
            }
        )
        
        # Create sample InstrumentManifestation
        manifest1, created = InstrumentManifestation.objects.get_or_create(
            expr=expr1,
            defaults={
                'eli_uri_manifest': 'https://eli.example.ir/akn/ir/act/1928/civil-code/fa/1928-05-20',
                'publication_date': date(1928, 5, 25),
                'official_gazette_name': 'روزنامه رسمی کشور',
                'gazette_issue_no': '1234',
                'in_force_from': date(1928, 6, 1),
                'repeal_status': 'in_force',
                'created_by': admin_user
            }
        )
        
        manifest2, created = InstrumentManifestation.objects.get_or_create(
            expr=expr2,
            defaults={
                'eli_uri_manifest': 'https://eli.example.ir/akn/ir/act/1932/commercial-code/fa/1932-06-15',
                'publication_date': date(1932, 6, 20),
                'official_gazette_name': 'روزنامه رسمی کشور',
                'gazette_issue_no': '1567',
                'in_force_from': date(1932, 7, 1),
                'repeal_status': 'in_force',
                'created_by': admin_user
            }
        )
        
        # Create sample LegalUnits with new FRBR references
        unit1, created = LegalUnit.objects.get_or_create(
            work=work1,
            expr=expr1,
            manifestation=manifest1,
            label='ماده ۱',
            defaults={
                'unit_type': 'article',
                'number': '1',
                'order_index': 1,
                'content': 'هر شخص از بدو تولد تا هنگام مرگ دارای شخصیت حقوقی است.',
                'eli_fragment': '#art_1',
                'xml_id': 'art_1',
                'text_plain': 'هر شخص از بدو تولد تا هنگام مرگ دارای شخصیت حقوقی است.',
                'created_by': admin_user
            }
        )
        
        unit2, created = LegalUnit.objects.get_or_create(
            work=work2,
            expr=expr2,
            manifestation=manifest2,
            label='ماده ۱',
            defaults={
                'unit_type': 'article',
                'number': '1',
                'order_index': 1,
                'content': 'تاجر کسی است که حرفه او تجارت باشد.',
                'eli_fragment': '#art_1',
                'xml_id': 'art_1',
                'text_plain': 'تاجر کسی است که حرفه او تجارت باشد.',
                'created_by': admin_user
            }
        )
        
        # Create sample WorkTags
        WorkTag.objects.get_or_create(
            work=work1,
            tag=tag_civil,
            defaults={
                'relevance_score': 1.0,
                'notes': 'قانون اصلی حقوق مدنی',
                'tagged_by': admin_user
            }
        )
        
        WorkTag.objects.get_or_create(
            work=work2,
            tag=tag_commercial,
            defaults={
                'relevance_score': 1.0,
                'notes': 'قانون اصلی حقوق تجاری',
                'tagged_by': admin_user
            }
        )
        
        # Create sample UnitTags
        UnitTag.objects.get_or_create(
            unit=unit1,
            tag=tag_civil,
            defaults={
                'relevance_score': 1.0,
                'notes': 'ماده مربوط به شخصیت حقوقی',
                'tagged_by': admin_user
            }
        )
        
        # Create sample InstrumentRelation
        InstrumentRelation.objects.get_or_create(
            from_work=work2,
            to_work=work1,
            relation_type='references',
            defaults={
                'effective_date': date(1932, 6, 15),
                'notes': 'قانون تجارت به قانون مدنی ارجاع می‌دهد',
                'created_by': admin_user
            }
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created sample FRBR data:\n'
                f'- 2 Works: {work1.title_official}, {work2.title_official}\n'
                f'- 2 Expressions (Persian language)\n'
                f'- 2 Manifestations (official publications)\n'
                f'- 2 Legal Units (articles)\n'
                f'- 2 Tags: {tag_civil.name}, {tag_commercial.name}\n'
                f'- Work and Unit tagging relationships\n'
                f'- 1 Instrument relation (reference)\n'
                f'\nAdmin login: admin / admin123\n'
                f'Visit: http://localhost:8001/admin/'
            )
        )
