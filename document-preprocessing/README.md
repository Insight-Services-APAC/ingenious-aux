# Ingenious Document Preprocessing Tools

A standalone CLI package for document preprocessing including chunking, extraction, and data preparation utilities specifically designed for RAG (Retrieval-Augmented Generation) pipelines.

## Features

- **Document Chunking**: Split large documents into smaller, semantically meaningful chunks
- **Document Extraction**: Extract structured content from PDFs, DOCX, and other document formats  
- **Data Preparation**: Web scraping and data collection utilities

## Installation

```bash
pip install ingenious-docprep
```

Or install from source:

```bash
git clone <repository-url>
cd document-preprocessing
pip install -e .
```

## Usage

The package provides a unified CLI with three main command groups:

### Document Chunking

Split documents into chunks for RAG pipelines:

```bash
# Basic chunking with default settings
docprep chunk run input.txt --output chunks.jsonl

# Recursive chunking with custom parameters
docprep chunk run document.txt --strategy recursive --chunk-size 512 --chunk-overlap 50

# Token-based chunking
docprep chunk run document.txt --strategy token --chunk-size 256 --overlap-unit tokens

# Semantic chunking (requires OpenAI API key)
docprep chunk run document.txt --strategy semantic --embed-model text-embedding-ada-002

# Markdown-aware chunking
docprep chunk run document.md --strategy markdown
```

Supported input formats:
- `.txt`, `.md`, `.markdown` - Plain text files
- `.json` - JSON objects with `text`, `page_content`, or `body` fields
- `.jsonl`, `.ndjson` - Newline-delimited JSON (one object per line)

### Document Extraction

Extract structured content from various document formats:

```bash
# Extract from PDF
docprep extract document.pdf --out extracted.jsonl

# Extract from DOCX
docprep extract document.docx --engine pymupdf

# Extract from directory of files
docprep extract documents/ --out all_extracted.jsonl

# Extract from URL
docprep extract https://example.com/document.pdf
```

### Data Preparation

Web scraping and data collection utilities:

```bash
# Single page scraping
docprep dataprep crawl https://example.com

# Batch scraping
docprep dataprep batch https://example.com/page1 https://example.com/page2 --out scraped.jsonl
```

## Configuration

### Chunking Strategies

1. **Recursive**: Default character-based splitting with sensible separators
2. **Token**: Token-aware splitting using tiktoken encodings
3. **Semantic**: Embedding-based splitting for semantic coherence
4. **Markdown**: Markdown-structure-aware splitting

### Parameters

- `--chunk-size`: Maximum size per chunk (tokens or characters)
- `--chunk-overlap`: Overlap between chunks for context preservation
- `--overlap-unit`: Unit for overlap (`tokens` or `characters`)
- `--strategy`: Chunking algorithm to use
- `--output`: Output file path (defaults to `chunks.jsonl`)

## Dependencies

Core dependencies:
- `typer` - CLI framework
- `rich` - Rich text formatting
- `pydantic` - Data validation
- `langchain-core` - Document abstractions
- `langchain-text-splitters` - Text splitting algorithms
- `tiktoken` - Tokenization
- `jsonlines` - JSONL file handling

Optional dependencies:
- `langchain-openai` - For semantic chunking
- `langchain-experimental` - Advanced splitting features

## Development

```bash
# Install development dependencies
pip install -e .[dev]

# Run tests
pytest

# Format code
black .

# Lint code
ruff check .
```

## API Usage

The package can also be used programmatically:

```python
from ingenious_docprep.chunk import ChunkConfig, build_splitter

# Create configuration
config = ChunkConfig(
    strategy="recursive",
    chunk_size=512,
    chunk_overlap=50,
    overlap_unit="characters"
)

# Build splitter
splitter = build_splitter(config)

# Split text
chunks = splitter.split_text("Your document text here...")
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.