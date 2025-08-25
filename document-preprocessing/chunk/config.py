"""
Defines the configuration model for all document chunking operations.

Purpose & Context
-----------------
This module provides a validated, immutable configuration object, `ChunkConfig`,
that governs how the document processing subsystem (`ingenious.chunk`) splits
large texts into smaller, more manageable pieces. Chunking is a critical
pre-processing step for Retrieval-Augmented Generation (RAG) workflows, enabling
effective embedding and retrieval. This configuration object is consumed by
chunking agents and data ingestion pipelines throughout the Insight Ingenious
architecture to ensure consistent and predictable behavior.

Key Algorithms & Design Choices
-------------------------------
- **Pydantic `BaseModel`**: Configuration is managed via Pydantic to leverage its
  powerful data validation, type enforcement, and serialization capabilities.
  This centralizes all configuration rules in one place.
- **Immutability**: The model is configured with `frozen=True`. Once a `ChunkConfig`
  object is instantiated, it cannot be altered. This prevents runtime modifications
  and ensures that a multi-step chunking process operates on a consistent and
  reproducible configuration, which is vital for deterministic outputs.
- **Strategy-Based Approach**: The model supports multiple distinct chunking
  `strategy` options (`recursive`, `markdown`, `token`, `semantic`) to provide
  flexibility for different document formats and downstream use cases.
- **Cross-Field Validation**: Pydantic's `@model_validator` is used extensively
  to enforce complex invariants between fields (e.g., ensuring
  `chunk_overlap` is less than `chunk_size`).

Usage Example
-------------
.. code-block:: python

    from ingenious.chunk.config import ChunkConfig
    import warnings

    # Example 1: Basic recursive strategy
    try:
        config = ChunkConfig(
            strategy="recursive",
            chunk_size=512,
            chunk_overlap=64,
        )
        print(f"Valid config: {config.strategy} with size {config.chunk_size}")
        # > Valid config: recursive with size 512
    except ValueError as e:
        print(f"Configuration error: {e}")

    # Example 2: Semantic strategy (triggers a fallback warning)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        semantic_config = ChunkConfig(strategy="semantic")
        print(f"Valid semantic config created for strategy: {semantic_config.strategy}")
        # > Valid semantic config created for strategy: semantic
        if w:
            print(f"Caught warning: {w[-1].message}")
            # > Caught warning: Semantic splitter: no `azure_openai_deployment`...

    # Example 3: Invalid configuration (raises ValueError)
    try:
        invalid_config = ChunkConfig(chunk_size=100, chunk_overlap=100)
    except ValueError as e:
        print(f"Caught expected error: {e}")
        # > Caught expected error: 1 validation error for ChunkConfig
        # > chunk_overlap (100) must be smaller than chunk_size (100)
"""

import warnings
from pathlib import Path
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChunkConfig(BaseModel):
    """User-facing configuration for content chunking.

    This class defines all parameters that control the document chunking process.
    It uses Pydantic for validation and is immutable (`frozen=True`) to guarantee
    that chunking parameters cannot be changed after initialization, ensuring
    consistent and reproducible behavior.

    Attributes:
        strategy: The chunking algorithm to use.
        id_path_mode: Method for generating chunk source identifiers.
        id_base: Base directory for relative path IDs.
        id_hash_bits: The number of bits to retain for SHA-256 hash IDs.
        chunk_size: The target maximum size of a chunk (in tokens or characters).
        chunk_overlap: The amount of overlap between consecutive chunks.
        overlap_unit: The unit for `chunk_size` and `chunk_overlap`.
        separators: Custom separators for 'recursive' or 'markdown' strategies.
        encoding_name: The `tiktoken` encoding for token-based calculations.
        embed_model: The embedding model for the 'semantic' strategy.
        azure_openai_deployment: Azure deployment name for semantic splitting.
        semantic_threshold_percentile: The similarity cutoff for semantic splits.
    """

    # ------------------------------------------------------------------
    # Pydantic model settings
    # ------------------------------------------------------------------
    model_config = ConfigDict(frozen=True)

    # ------------------------------------------------------------------
    # Strategy selector
    # ------------------------------------------------------------------
    strategy: Literal["recursive", "markdown", "token", "semantic"] = "recursive"

    id_path_mode: Literal["abs", "rel", "hash"] = "rel"
    id_base: Path | None = Field(
        default=None, description="Base dir for relative ID paths"
    )

    # ------------------------------------------------------------------
    # Digest truncation – collision domain
    # ------------------------------------------------------------------
    id_hash_bits: int = Field(
        64,
        ge=32,
        le=256,
        description=(
            "Number of **SHA‑256 bits** kept when truncating the hexadecimal "
            "digest that forms a chunk‑ or path‑hash. Must be a multiple of 4 "
            "(1 hex digit = 4 bits)."
        ),
    )

    # ------------------------------------------------------------------
    # Shared knobs
    # ------------------------------------------------------------------
    chunk_size: int = Field(
        1024,
        ge=1,
        description=(
            "Max tokens/characters allowed in a single chunk. NOTE: This is "
            "ignored by the 'semantic' strategy."
        ),
    )
    chunk_overlap: int = Field(
        128,
        ge=0,
        description="Number of tokens/characters shared between consecutive chunks.",
    )

    overlap_unit: Literal["tokens", "characters"] = "tokens"

    # ------------------------------------------------------------------
    # Strategy-specific options
    # ------------------------------------------------------------------
    # recursive / markdown
    separators: List[str] | None = None

    # token splitter
    encoding_name: str = "cl100k_base"

    # semantic splitter
    embed_model: str | None = None
    azure_openai_deployment: str | None = None
    semantic_threshold_percentile: int = Field(
        95,
        ge=0,
        le=100,
        description=(
            "The percentile of similarity scores to use as a threshold for "
            "splitting chunks in the 'semantic' strategy."
        ),
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _validate_hash_bits(self) -> "ChunkConfig":
        """Ensures `id_hash_bits` is a multiple of 4.

        Rationale:
            Chunk and path IDs generated via hashing use a truncated hexadecimal
            `SHA-256` digest. Each hex character represents 4 bits. This validator
            enforces that `id_hash_bits` is a multiple of 4, as truncating to a
            non-multiple would correspond to an incomplete hex character, which is
            invalid and serves no purpose.

        Returns:
            The validated model instance.

        Raises:
            ValueError: If `id_hash_bits` is not a multiple of 4.
        """
        if self.id_hash_bits % 4 != 0:
            raise ValueError("id_hash_bits must be a multiple of 4")
        return self

    @model_validator(mode="after")
    def _warn_small_hash_bits(self) -> "ChunkConfig":
        """Issues a warning if `id_hash_bits` is low (< 48).

        Rationale:
            A small hash size significantly increases the probability of hash
            collisions for chunk IDs, especially in large document sets (per the
            Birthday Problem). While not a fatal error, this condition poses a
            risk to data integrity. A `warning` is used to alert the developer to
            this potential issue without halting execution, promoting robust
            configuration as per DI-101.

        Returns:
            The validated model instance.
        """
        if self.id_hash_bits < 48:
            warnings.warn(
                "id_hash_bits < 48 increases the probability of prefix "
                "collisions in large corpora. Consider using the default 64 "
                "or higher.",
                stacklevel=2,
            )
        return self

    @model_validator(mode="after")
    def _validate_id_mode(self) -> "ChunkConfig":
        """Validates `id_base` based on the chosen `id_path_mode`.

        Rationale:
            The `id_base` field is only meaningful for generating relative path
            IDs (`id_path_mode='rel'`). This validator enforces that dependency. It
            also provides a sensible default (the current working directory) for
            convenience. Since the model is frozen, `object.__setattr__` is used
            to assign the default, a standard Pydantic pattern for immutable models.

        Returns:
            The validated model instance.

        Raises:
            ValueError: If `id_base` is set when `id_path_mode` is not `'rel'`.
        """
        if self.id_path_mode == "rel":
            # Default base to CWD if not supplied
            # Use `object.__setattr__` as the model is frozen.
            object.__setattr__(self, "id_base", self.id_base or Path.cwd())
        else:
            # In abs/hash mode, id_base must not be set
            if self.id_base is not None:
                raise ValueError(
                    "id_base is only applicable when id_path_mode == 'rel'"
                )
        return self

    @model_validator(mode="after")
    def _validate_overlap(self) -> "ChunkConfig":
        """Enforces `chunk_overlap < chunk_size` for applicable strategies.

        Rationale:
            For chunking strategies that use fixed sizes (i.e., not `'semantic'`),
            an overlap equal to or greater than the chunk size is illogical. It
            would produce chunks containing no new information or being identical
            to the previous one. This validator prevents such invalid states. The
            check is skipped for the `'semantic'` strategy, where chunk boundaries
            are determined by content similarity, not fixed lengths.

        Returns:
            The validated model instance.

        Raises:
            ValueError: If `chunk_overlap >= chunk_size` for non-semantic strategies.
        """
        if self.strategy != "semantic" and self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be smaller than "
                f"chunk_size ({self.chunk_size})"
            )
        return self

    @model_validator(mode="after")
    def _validate_semantic_strategy(self) -> "ChunkConfig":
        """Enforces constraints specific to the 'semantic' chunking strategy.

        Rationale:
            The 'semantic' chunking algorithm operates by analyzing sentence
            embeddings, which are inherently token-based. Measuring overlap in
            terms of characters is therefore incompatible with its design and could
            lead to unpredictable behavior. This validator ensures that only the
            supported 'tokens' unit is used with this strategy.

        Returns:
            The validated model instance.

        Raises:
            ValueError: If `overlap_unit` is `'characters'` and strategy is `'semantic'`.
        """
        if self.strategy == "semantic" and self.overlap_unit == "characters":
            raise ValueError(
                "The 'semantic' strategy does not support 'characters' as an "
                "overlap_unit. Please use 'tokens' for semantic chunking."
            )
        return self

    @model_validator(mode="after")
    def _semantic_warn_backend(self) -> "ChunkConfig":
        """Warns user when semantic splitter falls back to public OpenAI API.

        Rationale:
            To simplify local development and testing, the semantic splitter can
            function without explicit Azure or model configuration by using a
            default public OpenAI embedding model. This fallback relies on the
            `OPENAI_API_KEY` environment variable and may incur costs. A warning
            ensures the user is aware of this implicit behavior, preventing silent
            failures or unexpected API usage. It is a warning, not an error, to

            preserve this developer-friendly fallback mechanism.

        Returns:
            The validated model instance.
        """
        if self.strategy == "semantic" and not (
            self.azure_openai_deployment or self.embed_model
        ):
            warnings.warn(
                "Semantic splitter: no `azure_openai_deployment` or "
                "`embed_model` supplied – falling back to the public "
                "OpenAI endpoint with model 'text-embedding-3-small'. "
                "Make sure OPENAI_API_KEY is set.",
                stacklevel=2,
            )
        return self
