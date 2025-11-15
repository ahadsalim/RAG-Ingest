"""Test utilities for the documents app."""
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from django.core.files.uploadedfile import SimpleUploadedFile


def create_test_file(
    filename: str = "test_file.txt",
    content: bytes = b"Test file content",
    content_type: str = "text/plain"
) -> SimpleUploadedFile:
    """
    Create a test file for upload testing.

    Args:
        filename: The name of the test file.
        content: The content of the test file.
        content_type: The content type of the test file.

    Returns:
        A SimpleUploadedFile instance.
    """
    return SimpleUploadedFile(filename, content, content_type)


def create_temp_file(
    content: str = "Test content",
    suffix: str = "",
    prefix: str = "test_file_"
) -> str:
    """
    Create a temporary file for testing.

    Args:
        content: The content to write to the file.
        suffix: The suffix for the temporary file.
        prefix: The prefix for the temporary file.

    Returns:
        The path to the created temporary file.
    """
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=suffix,
        prefix=prefix,
        delete=False,
        encoding="utf-8"
    ) as f:
        f.write(content)
    return f.name


def get_fixture_path(filename: str) -> str:
    """
    Get the absolute path to a test fixture file.

    Args:
        filename: The name of the fixture file.

    Returns:
        The absolute path to the fixture file.
    """
    base_dir = Path(__file__).parent.parent.parent
    return str(base_dir / "fixtures" / filename)


def assert_dict_contains_subset(subset: Dict[Any, Any], dictionary: Dict[Any, Any]) -> None:
    """
    Assert that a dictionary contains all items in a subset.

    Args:
        subset: The subset of items to check for.
        dictionary: The dictionary to check in.

    Raises:
        AssertionError: If the subset is not found in the dictionary.
    """
    for key, value in subset.items():
        assert key in dictionary, f"Key '{key}' not found in dictionary"
        assert dictionary[key] == value, f"Value for key '{key}' does not match. " \
                                       f"Expected: {value}, Got: {dictionary[key]}"


def create_test_image(
    filename: str = "test_image.jpg",
    size: tuple[int, int] = (100, 100),
    color: str = "red",
    format: str = "JPEG"
) -> SimpleUploadedFile:
    """
    Create a test image for upload testing.

    Args:
        filename: The name of the test image file.
        size: The size of the image as (width, height).
        color: The color of the image.
        format: The image format (JPEG, PNG, etc.).

    Returns:
        A SimpleUploadedFile instance containing the test image.
    """
    from PIL import Image, ImageDraw
    
    # Create a new image with the specified size and color
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    
    # Add some content to the image
    draw.rectangle([10, 10, 90, 90], outline="black")
    
    # Save the image to a bytes buffer
    from io import BytesIO
    buffer = BytesIO()
    image.save(buffer, format=format)
    
    # Create and return the SimpleUploadedFile
    return SimpleUploadedFile(
        name=filename,
        content=buffer.getvalue(),
        content_type=f"image/{format.lower()}"
    )


def create_test_pdf(
    filename: str = "test_document.pdf",
    text: str = "Test PDF Content"
) -> SimpleUploadedFile:
    """
    Create a simple test PDF file.

    Args:
        filename: The name of the test PDF file.
        text: The text content to include in the PDF.

    Returns:
        A SimpleUploadedFile instance containing the test PDF.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.drawString(100, 750, text)
        c.save()
        
        return SimpleUploadedFile(
            name=filename,
            content=buffer.getvalue(),
            content_type="application/pdf"
        )
    except ImportError:
        # Fallback to a simple text file if reportlab is not available
        return SimpleUploadedFile(
            name=filename,
            content=text.encode(),
            content_type="application/pdf"
        )
