"""Tests for document models."""
import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase

from ingest.apps.documents.models import Document, LegalUnit


class DocumentModelTest(TestCase):
    """Test the Document model."""

    def test_create_document(self):
        ""Test creating a document."""
        document = Document.objects.create(
            title="Test Document",
            description="Test Description",
        )
        self.assertEqual(str(document), "Test Document")
        self.assertEqual(document.status, Document.Status.DRAFT)
        self.assertIsNotNone(document.created_at)
        self.assertIsNotNone(document.updated_at)

    def test_document_status_choices(self):
        ""Test document status choices."""
        document = Document(
            title="Test Document",
            description="Test Description",
            status=Document.Status.PUBLISHED
        )
        document.full_clean()
        document.save()
        self.assertEqual(document.status, Document.Status.PUBLISHED)

    def test_invalid_status(self):
        ""Test that an invalid status raises a validation error."""
        document = Document(
            title="Test Document",
            description="Test Description",
            status="INVALID_STATUS"
        )
        with self.assertRaises(ValidationError):
            document.full_clean()

    def test_document_ordering(self):
        ""Test that documents are ordered by title by default."""
        Document.objects.create(title="B Document", description="B")
        Document.objects.create(title="A Document", description="A")
        documents = Document.objects.all()
        self.assertEqual(documents[0].title, "A Document")
        self.assertEqual(documents[1].title, "B Document")


class LegalUnitModelTest(TestCase):
    ""Test the LegalUnit model."""

    def setUp(self):
        ""Set up test data."""
        self.document = Document.objects.create(
            title="Test Document",
            description="Test Description",
        )

    def test_create_legal_unit(self):
        ""Test creating a legal unit."""
        legal_unit = LegalUnit.objects.create(
            title="Test Legal Unit",
            document=self.document,
            content="Test Content",
            order=1,
        )
        self.assertEqual(str(legal_unit), "Test Legal Unit")
        self.assertEqual(legal_unit.document, self.document)
        self.assertEqual(legal_unit.order, 1)
        self.assertIsNotNone(legal_unit.created_at)
        self.assertIsNotNone(legal_unit.updated_at)

    def test_legal_unit_ordering(self):
        ""Test that legal units are ordered by order field."""
        unit1 = LegalUnit.objects.create(
            title="Unit 2",
            document=self.document,
            content="Content 2",
            order=2,
        )
        unit2 = LegalUnit.objects.create(
            title="Unit 1",
            document=self.document,
            content="Content 1",
            order=1,
        )
        units = list(self.document.legal_units.all())
        self.assertEqual(units, [unit2, unit1])

    def test_legal_unit_tree_structure(self):
        ""Test the MPTT tree structure of legal units."""
        parent = LegalUnit.objects.create(
            title="Parent Unit",
            document=self.document,
            content="Parent Content",
            order=1,
        )
        child = LegalUnit.objects.create(
            title="Child Unit",
            document=self.document,
            content="Child Content",
            parent=parent,
            order=1,
        )
        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.get_children())
        self.assertEqual(child.get_ancestors().count(), 1)
        self.assertEqual(child.get_ancestors()[0], parent)

    def test_legal_unit_str_representation(self):
        ""Test the string representation of a legal unit."""
        legal_unit = LegalUnit.objects.create(
            title="Test Legal Unit",
            document=self.document,
            content="Test Content",
            order=1,
        )
        self.assertEqual(str(legal_unit), "Test Legal Unit")

    @pytest.mark.django_db
def test_legal_unit_without_document(self):
    ""Test that a legal unit cannot be created without a document."""
    with pytest.raises(ValidationError):
        legal_unit = LegalUnit(
            title="Test Legal Unit",
            content="Test Content",
            order=1,
        )
        legal_unit.full_clean()  # This should raise ValidationError
        legal_unit.save()  # This line won't be reached if the test passes

    # Verify no legal unit was created
    assert LegalUnit.objects.count() == 0
