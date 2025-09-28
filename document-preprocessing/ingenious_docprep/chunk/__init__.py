"""
A stable, public-facing API for the document chunking subsystem.

Purpose & Context
-----------------
This module provides the core components for splitting large documents into
smaller, semantically meaningful chunks. In the Insight Ingenious architecture,
chunking is a critical preprocessing step for Retrieval-Augmented Generation
(RAG). Chunks, rather than full documents, are vectorized and stored in a
vector database, enabling agents to retrieve the most relevant, concise
information to answer user queries.

This `__init__.py` file acts as a facade, exporting the essential public symbols
from its submodules (`.config`, `.factory`). This simplifies usage for other
parts of the system and decouples them from the internal file structure of the
chunking feature, which can be refactored without breaking client code.

Key Algorithms & Design Choices
-------------------------------
The primary design choice here is the **Facade Pattern**. By exposing
`ChunkConfig` and `build_splitter` at the package level, we create a single,
stable entry point. Consumers do not need to know whether the configuration
and factory logic live in the same or different files.

The underlying splitting strategies (e.g., recursive character splitting,
semantic chunking) are implemented via a factory function (`build_splitter`)
that is configured by a dedicated data class (`ChunkConfig`). This promotes
flexibility and extensibility, allowing new chunking strategies to be added
without altering the public API.
"""

from .config import ChunkConfig
from .factory import build_splitter

__all__ = ["ChunkConfig", "build_splitter"]
