from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from ingest.apps.masterdata.models import Jurisdiction, IssuingAuthority, Vocabulary, VocabularyTerm
from ingest.apps.documents.models import LegalUnit
from ingest.apps.documents.enums import DocumentType, DocumentStatus, UnitType, QAStatus


class Command(BaseCommand):
    help = 'Create sample data for testing and demonstration'

    def handle(self, *args, **options):
        self.stdout.write('Creating sample data...')
        
        # Create sample jurisdiction
        iran, created = Jurisdiction.objects.get_or_create(
            code='IR',
            defaults={
                'name': 'جمهوری اسلامی ایران',
                'description': 'حوزه قضایی کشور ایران'
            }
        )
        if created:
            self.stdout.write(f'Created jurisdiction: {iran.name}')
        
        # Create sample issuing authority
        majles, created = IssuingAuthority.objects.get_or_create(
            code='MAJLES',
            defaults={
                'name': 'مجلس شورای اسلامی',
                'jurisdiction': iran,
                'description': 'مجلس شورای اسلامی ایران'
            }
        )
        if created:
            self.stdout.write(f'Created authority: {majles.name}')
        
        # Create sample vocabulary
        legal_vocab, created = Vocabulary.objects.get_or_create(
            code='LEGAL',
            defaults={
                'name': 'موضوعات حقوقی',
                'description': 'دسته‌بندی موضوعات حقوقی'
            }
        )
        if created:
            self.stdout.write(f'Created vocabulary: {legal_vocab.name}')
        
        # Create sample vocabulary terms
        terms_data = [
            ('CIVIL', 'حقوق مدنی'),
            ('CRIMINAL', 'حقوق جزا'),
            ('COMMERCIAL', 'حقوق تجارت'),
            ('ADMINISTRATIVE', 'حقوق اداری'),
        ]
        
        for code, term in terms_data:
            vocab_term, created = VocabularyTerm.objects.get_or_create(
                vocabulary=legal_vocab,
                code=code,
                defaults={'term': term}
            )
            if created:
                self.stdout.write(f'Created term: {vocab_term.term}')
        
        # Create sample user if needed
        user, created = User.objects.get_or_create(
            username='demo_operator',
            defaults={
                'email': 'demo@example.com',
                'first_name': 'Demo',
                'last_name': 'Operator'
            }
        )
        if created:
            user.set_password('demo123')
            user.save()
            self.stdout.write(f'Created user: {user.username}')
        
        # Create sample document
        sample_doc, created = LegalDocument.objects.get_or_create(
            reference_no='SAMPLE-001',
            defaults={
                'title': 'قانون نمونه برای آزمایش سیستم',
                'doc_type': DocumentType.LAW,
                'jurisdiction': iran,
                'authority': majles,
                'status': DocumentStatus.DRAFT,
                'created_by': user
            }
        )
        if created:
            self.stdout.write(f'Created document: {sample_doc.title}')
            
            # Add subject terms
            civil_term = VocabularyTerm.objects.get(vocabulary=legal_vocab, code='CIVIL')
            sample_doc.subject_terms.add(civil_term)
            
            # Create sample units
            unit1 = LegalUnit.objects.create(
                document=sample_doc,
                unit_type=UnitType.ARTICLE,
                label='ماده ۱',
                number='1',
                order_index=1,
                content='این ماده اول قانون نمونه است که برای آزمایش سیستم ایجاد شده است.'
            )
            self.stdout.write(f'Created unit: {unit1.label}')
            
            unit2 = LegalUnit.objects.create(
                document=sample_doc,
                unit_type=UnitType.ARTICLE,
                label='ماده ۲',
                number='2',
                order_index=2,
                content='این ماده دوم قانون نمونه است که شامل مقررات تکمیلی می‌باشد.'
            )
            self.stdout.write(f'Created unit: {unit2.label}')
        
        # QA entry creation removed - QAEntry model no longer exists in simplified version
        
        self.stdout.write(
            self.style.SUCCESS('Successfully created sample data')
        )
