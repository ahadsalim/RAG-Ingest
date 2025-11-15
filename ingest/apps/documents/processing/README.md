# Document Processing Module

This module handles the processing of documents and legal units into smaller, searchable chunks with vector embeddings.

## Overview

The processing pipeline:
1. Takes a document or legal unit as input
2. Splits the content into overlapping chunks
3. Generates vector embeddings for each chunk
4. Stores the chunks and embeddings in the database

## Components

### ChunkProcessingService

The main service class that handles document processing. Key methods:

- `process_document(document_id, **kwargs)`: Process a document and all its legal units
- `process_legal_unit(unit_id, **kwargs)`: Process a single legal unit
- `_split_text(text, chunk_size, chunk_overlap)`: Split text into overlapping chunks
- `_generate_embeddings(chunks)`: Generate vector embeddings for text chunks

### Configuration

Default settings (can be overridden in Django settings):

```python
# Default chunk size in tokens
DEFAULT_CHUNK_SIZE = 1000

# Default overlap between chunks in tokens
DEFAULT_CHUNK_OVERLAP = 200

# Batch size for bulk operations
PROCESSING_BATCH_SIZE = 10
```

## Usage

### Programmatic Usage

```python
from ingest.apps.documents.processing import get_chunk_processing_service

# Get the processing service
service = get_chunk_processing_service()

# Process a document
result = service.process_document("document-uuid-here")

# Process with custom chunking
result = service.process_document(
    "document-uuid-here",
    chunk_size=800,
    chunk_overlap=100
)
```

### Management Command

```bash
# Process a single document
python manage.py process_chunks --document-id <uuid>

# Process all documents in batches
python manage.py process_chunks --all --batch-size 5

# Process with custom chunking
python manage.py process_chunks --document-id <uuid> --chunk-size 800 --chunk-overlap 100
```

### Signals

Automatic processing on model save:

```python
# In your_app/apps.py
from django.apps import AppConfig

class DocumentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ingest.apps.documents'

    def ready(self):
        # Import signals to connect them
        from . import signals  # noqa
```

## Testing

Run the test suite with:

```bash
pytest ingest/apps/documents/tests/test_processing.py -v
```

## Performance Considerations

- For large documents, consider processing in background tasks
- Monitor memory usage when processing large batches
- Tune chunk size and overlap based on your specific requirements

## Troubleshooting

### Common Issues

1. **Memory Usage High**
   - Reduce batch size
   - Process fewer documents at once
   - Increase server resources if needed

2. **Processing Slow**
   - Check database indexes
   - Consider using a more powerful server
   - Review embedding generation performance

3. **Chunks Too Large/Small**
   - Adjust `DEFAULT_CHUNK_SIZE` and `DEFAULT_CHUNK_OVERLAP`
   - Consider the context window of your embedding model

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for your changes
4. Submit a pull request

## License

[Your License Here]
