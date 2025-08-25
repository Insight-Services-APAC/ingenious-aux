"""
Provides a CLI for splitting documents into standardized chunks for RAG.

Purpose & Context
-----------------
This module, `ingenious.chunk.cli`, offers a command-line interface for the core
document chunking functionality within the Insight Ingenious architecture. Its primary
role is to serve as a pre-processing step in Retrieval-Augmented Generation (RAG)
pipelines. It takes large source documents (e.g., from an Azure Document
Intelligence export) and divides them into smaller, textually-coherent chunks.
These chunks are then typically passed to an embedding model and stored in a
vector database for efficient semantic retrieval by Ingenious agents.

Key Algorithms & Design Choices
-------------------------------
- **Strategy Factory**: The CLI uses a factory pattern (`build_splitter`) to
  dynamically select the chunking algorithm (e.g., 'recursive', 'semantic').
  This makes the system extensible, allowing new strategies to be added with
  minimal changes to the CLI itself.
- **Typer for CLI**: `typer` was chosen to build the CLI for its modern,
  type-hint-driven interface. It automatically generates help text, validates
  input types (e.g., `Strategy` enum), and reduces boilerplate code.
- **Robust Loading**: Document loading is abstracted via `loader.load_documents`,
  which handles various file formats (`.txt`, `.json`, `.jsonl`) and glob
  patterns. The `_safe_load` wrapper provides a consistent, user-friendly
  error handling layer for the CLI.
- **Library Version Agnostic**: A compatibility shim, `_resolve_openai_error`,
  ensures the code works seamlessly with both older (`<1.0`) and newer (`>=1.0`)
  versions of the `openai` library, which is a key dependency for token-based
  and semantic chunking strategies.

Usage Example
-------------
.. code-block:: shell

    # Chunk a JSONL file from Azure Document Intelligence using a recursive strategy
    ingen chunk run test_files/pages_azdocint_pdf_scanned.jsonl \\
        --strategy recursive --chunk-size 64 --chunk-overlap 24 \\
        --output azdocint_chunks.jsonl

"""

from __future__ import annotations

import hashlib
import pathlib

# ── std‑lib ────────────────────────────────────────────────────────────────
from collections import defaultdict
from enum import Enum
from typing import Any, Dict, Iterable, List, Type, cast

# ── third‑party ────────────────────────────────────────────────────────────
import jsonlines
import typer
from langchain_core.documents import Document
from pydantic import ValidationError

# ── first‑party (this package) ─────────────────────────────────────────────
from ingenious.chunk.utils.id_path import _norm_source

from .config import ChunkConfig
from .factory import build_splitter
from .loader import load_documents


# --------------------------------------------------------------------------- #
# Resolve OpenAI base error class across client versions                      #
# --------------------------------------------------------------------------- #
def _resolve_openai_error() -> type[BaseException]:
    """Dynamically returns the OpenAIError base exception for different library versions.

    Rationale:
        The `openai` library's exception hierarchy was refactored in its v1.0
        release. The base error class moved from `openai.error.OpenAIError` to
        `openai.OpenAIError`. This function acts as a compatibility shim,
        allowing our `try...except` blocks to work reliably regardless of which
        version of the `openai` library is installed in the environment. This
        prevents runtime errors and improves the module's robustness.

    Returns:
        type[BaseException]: The `OpenAIError` class if the library is found,
        otherwise a local fallback `Exception` subclass to prevent runtime
        crashes and satisfy type checkers.

    Implementation Notes:
        It gracefully handles `ModuleNotFoundError` by returning a dummy
        `_Fallback` class, ensuring that the module can still be imported even
        if `openai` is not installed (e.g., when only using non-OpenAI-dependent
        chunking strategies).
    """
    try:
        import openai

        for attr in ("OpenAIError", "error"):
            candidate: object | None = getattr(openai, attr, None)
            # v1.0+ path: `openai.OpenAIError` is a class
            if isinstance(candidate, type):
                return cast(Type[BaseException], candidate)
            # v0.x path: `openai.error` is a module with `OpenAIError`
            if hasattr(candidate, "OpenAIError"):
                inner = getattr(candidate, "OpenAIError")
                if isinstance(inner, type):
                    return cast(Type[BaseException], inner)
    except ModuleNotFoundError:  # pragma: no cover
        pass

    # Fallback shim keeps type-checking happy if openai is not installed.
    class _Fallback(Exception):
        pass

    return _Fallback


_OpenAIError = _resolve_openai_error()

try:
    from azure.core.exceptions import HttpResponseError
except ModuleNotFoundError:  # package not installed

    class HttpResponseError(Exception):  # type: ignore
        pass


# Centralized list of exceptions that chunking strategies are expected to raise.
_EXPECTED_SPLITTER_ERRORS: tuple[type[BaseException], ...] = (
    ValueError,
    RuntimeError,
    _OpenAIError,  # Covers public + Azure OpenAI
    HttpResponseError,  # Covers direct Azure SDK calls (optional dependency)
)


# --------------------------------------------------------------------------- #
# Enum with the allowed strategies                                            #
# --------------------------------------------------------------------------- #
class Strategy(str, Enum):
    """Defines the set of permissible chunking strategies for the CLI.

    Rationale:
        Using a `str`-based `Enum` provides strong typing and self-documentation
        for the available strategies. `typer` leverages this enum to
        automatically generate CLI choices (`--strategy [recursive|markdown|...]`)
        and perform input validation, ensuring users can only select valid options.
    """

    recursive = "recursive"
    markdown = "markdown"
    token = "token"
    semantic = "semantic"


# --------------------------------------------------------------------------- #
# Shared “input‑file contract” text                                           #
# --------------------------------------------------------------------------- #
_CONTRACT = (
    "[bold]Input-file contract[/bold]\n"
    "• .txt / .md / .markdown – entire file becomes one document\n"
    "• .json              – an OBJECT or ARRAY of objects; each object must have a\n"
    "                       'text' | 'page_content' | 'body' key\n"
    "• .jsonl / .ndjson   – **one object per line** with the same keys above"
)


def _safe_load(pattern: str) -> Iterable[Document]:
    """Loads documents from a path, handling errors gracefully for the CLI.

    Rationale:
        This function centralizes error handling for the document loading
        process. It abstracts the caller (the Typer command) from the specific
        exceptions raised by the underlying loader and its dependencies (e.g.,
        `ijson`, Azure SDK). By catching known errors and re-raising a
        `typer.Exit`, it ensures a consistent and user-friendly failure mode
        for the CLI, printing a clear message and exiting with a standard error
        code (1).

    Args:
        pattern (str): A file path or glob pattern pointing to source documents.

    Returns:
        Iterable[dict]: An iterable of document dictionaries loaded from the source.

    Raises:
        typer.Exit: Exits the CLI with status code 1 if any of the following
                    exceptions occur during loading: `ValueError` (e.g.,
                    unsupported file type), `FileNotFoundError`, `RuntimeError`,
                    or `HttpResponseError` (from Azure SDK).
    """
    try:
        return load_documents(pattern)
    except (ValueError, FileNotFoundError, RuntimeError, HttpResponseError) as exc:
        typer.secho(f"❌  {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


# --------------------------------------------------------------------------- #
# Typer app                                                                   #
# --------------------------------------------------------------------------- #
# This object defines the `ingen chunk` command group. Specific subcommands like
# `run` are attached to this `Typer` application instance.
cli = typer.Typer(
    add_completion=False,
    rich_markup_mode="rich",
    help=f"Split files into chunked JSONL for RAG pipelines.\n\n{_CONTRACT}",
)


# --------------------------------------------------------------------------- #
# Root callback – nothing to do, but keeps Typer happy                        #
# --------------------------------------------------------------------------- #
@cli.callback(invoke_without_command=True, no_args_is_help=True)
def main() -> None:  # pragma: no cover
    """A Typer callback to show help text when no subcommand is given.

    Rationale:
        This is a standard Typer pattern that improves the CLI's usability. By
        setting `invoke_without_command=True` and `no_args_is_help=True`, a
        user who runs `ingen chunk` without a command (like `run`) will be
        shown the help message instead of an error. This guides them on how to
        use the tool correctly.

    Implementation Notes:
        The function body is intentionally empty as its only purpose is to
        configure the CLI's behavior through its decorator. The `pragma: no
        cover` is used because this is framework wiring, not testable business
        logic.
    """


# --------------------------------------------------------------------------- #
# `run` sub-command                                                           #
# --------------------------------------------------------------------------- #
@cli.command(
    "run",
    help=f"Chunk files and write a JSONL output file.\n\n{_CONTRACT}",
)
def run(  # noqa: PLR0913 – many CLI knobs by design
    # -------------- positional input ------------------------------------
    path: str = typer.Argument(
        ...,
        metavar="PATH",
        help="File, directory, or glob pattern",
        rich_help_panel="Input-file contract",
    ),
    # -------------- core knobs ------------------------------------------
    strategy: Strategy = typer.Option(
        Strategy.recursive,
        "--strategy",
        "-s",
        help="Chunking strategy to use.",
    ),
    chunk_size: int = typer.Option(
        1024, "--chunk-size", help="Max tokens/characters per chunk"
    ),
    chunk_overlap: int = typer.Option(
        128, "--chunk-overlap", help="Overlap between chunks (< size)"
    ),
    overlap_unit: str = typer.Option(
        "tokens",
        "--overlap-unit",
        help="Unit for overlap window: tokens | characters",
        rich_help_panel="Advanced",
    ),
    # -------------- advanced knobs --------------------------------------
    separators: str = typer.Option(
        "", help="Custom separators (join with '|') for recursive splitter"
    ),
    encoding_name: str = typer.Option(
        "cl100k_base", help="Tokenizer encoding for token splitter"
    ),
    embed_model: str = typer.Option("", help="Embedding model for semantic splitter"),
    azure_deployment: str = typer.Option(
        "", help="Azure OpenAI deployment for semantic splitter"
    ),
    semantic_threshold_percentile: int = typer.Option(
        95, help="Similarity percentile threshold for semantic splitter (0-100)"
    ),
    # -------------- ID-path handling ------------------------------------
    id_path_mode: str = typer.Option(
        "rel",
        "--id-path-mode",
        help=(
            "Encode source paths inside chunk IDs: rel | hash | abs.\n\n"
            "⚠️  Using 'abs' will embed your *full* filesystem path into every "
            "chunk ID.  You must supply --force-abs-path to acknowledge this "
            "risk."
        ),
        rich_help_panel="Output",
    ),
    id_base: str = typer.Option(
        "",
        "--id-base",
        help="Base directory for --id-path-mode=rel (defaults to CWD)",
        rich_help_panel="Output",
    ),
    # NOTE: default bumped to 64 bits → 16 hex chars
    id_hash_bits: int = typer.Option(
        64,
        "--id-hash-bits",
        help="Bits to keep from the SHA-256 hash used in chunk IDs "
        "(multiple of 4; ≥ 32, ≤ 256).  Default: 64 bits → 16 hex.",
        rich_help_panel="Output",
    ),
    # -------------- safety acknowledgement --------------------------------
    force_abs_path: bool = typer.Option(
        False,
        "--force-abs-path",
        help=(
            "⚠️  REQUIRED when --id-path-mode=abs. Confirms you understand "
            "absolute source paths will be embedded in every chunk ID and "
            "may leak sensitive information when the file is shared."
        ),
        rich_help_panel="Output",
    ),
    # -------------- output ----------------------------------------------
    output: str = typer.Option(
        "chunks.jsonl", "--output", "-o", help="Output JSONL filepath"
    ),
    # -------------- diagnostics ------------------------------------------
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show full Python traceback on internal errors.",
        rich_help_panel="Debugging",
    ),
) -> None:
    """Executes the end-to-end document chunking process via the CLI.

    This function reads documents from a source path, splits them into chunks
    according to the specified strategy and parameters, and writes the resulting
    chunks to a JSONL output file.

    Rationale:
        This function serves as the primary user entry point for the chunking
        service. It integrates all necessary components: configuration, loading,
        splitting, and writing. The large number of CLI options is a deliberate
        design choice to provide fine-grained control for various use cases,
        from simple recursive splitting to complex semantic chunking. Sensible
        defaults ensure ease of use for common tasks. Robust error handling is
        built in to provide clear feedback for configuration errors, loading
        failures, and chunking exceptions.

    Args:
        path (str): The source file, directory, or glob pattern to load documents
            from.
        strategy (Strategy): The chunking algorithm to use (e.g., 'recursive').
        chunk_size (int): The maximum size of each chunk in characters or tokens.
        chunk_overlap (int): The number of characters or tokens to overlap
            between adjacent chunks.
        overlap_unit (str): The unit for `chunk_overlap`: 'tokens' or 'characters'.
        separators (str): A '|'-delimited string of custom separators for the
            recursive text splitter.
        encoding_name (str): The `tiktoken` encoding model to use for token-based
            counting or splitting.
        embed_model (str): The embedding model name for the semantic splitter.
        azure_deployment (str): The Azure OpenAI deployment name for semantic
            splitting.
        semantic_threshold_percentile (int): The percentile (0-100) for the
            similarity threshold used in semantic splitting.
        id_path_mode (str): Method to encode the source path in chunk IDs:
            'rel' (relative), 'hash' (hashed), or 'abs' (absolute).
        id_base (str): The base path to use for making relative paths when
            `id_path_mode` is 'rel'. Defaults to the current working directory.
        id_hash_bits (int): The number of bits (32-256) of the SHA-256 hash
            to use in chunk IDs.
        force_abs_path (bool): A safety flag that must be enabled to use
            `id_path_mode='abs'`, acknowledging the risk of leaking file paths.
        output (str): The path to the output JSONL file.
        verbose (bool): If True, prints full exception tracebacks for debugging.

    Raises:
        typer.Exit: The function catches all internal exceptions and exits
            gracefully with a non-zero status code and a user-friendly error
            message.
    """

    # ------------------------------------------------------------------ #
    # Guard against accidental PII leakage                                 #
    # ------------------------------------------------------------------ #
    if id_path_mode == "abs" and not force_abs_path:
        typer.secho(
            "❌  --id-path-mode=abs embeds *absolute* filesystem paths in "
            "chunk IDs which can reveal sensitive information.\n"
            "   Re-run with --force-abs-path if you really want this.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    # ------------------------------------------------------------------ #
    # Build config & splitter                                              #
    # ------------------------------------------------------------------ #
    try:
        cfg = ChunkConfig(
            strategy=strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            overlap_unit=overlap_unit,
            separators=separators.split("|") if separators else None,
            encoding_name=encoding_name,
            embed_model=embed_model or None,
            azure_openai_deployment=azure_deployment or None,
            semantic_threshold_percentile=semantic_threshold_percentile,
            id_path_mode=id_path_mode,
            id_base=pathlib.Path(id_base) if id_base else None,
            id_hash_bits=id_hash_bits,
        )
    except ValidationError as exc:
        # Uniform UX: red ❌ prefix + graceful exit on user-config errors
        typer.secho(f"❌  Configuration error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    splitter = build_splitter(cfg)

    # ------------------------------------------------------------------ #
    # Load documents                                                       #
    # ------------------------------------------------------------------ #
    docs = _safe_load(path)

    # ------------------------------------------------------------------ #
    # Prepare output path                                                  #
    # ------------------------------------------------------------------ #
    out_path = pathlib.Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Chunk                                                                #
    # ------------------------------------------------------------------ #
    try:
        chunks = splitter.split_documents(docs)
    except _EXPECTED_SPLITTER_ERRORS as exc:
        # --- Expected, user-visible failure --------------------------- #
        typer.secho(f"❌  Chunking failed: {exc}", fg=typer.colors.RED, err=True)

        # `--verbose / -v` ⇒ surface the full traceback for diagnostics.
        if verbose:
            import sys
            import traceback

            traceback.print_exc(file=sys.stderr)

        # Graceful termination with exit-code 1 (same UX as loader errors)
        raise typer.Exit(code=1) from exc

    # ------------------------------------------------------------------ #
    # Unexpected internal error – present a friendly banner and exit 1   #
    # unless the user asked for a full traceback via --verbose.          #
    # ------------------------------------------------------------------ #
    except Exception as exc:  # pragma: no cover
        typer.secho(
            f"❌  An unexpected error occurred: {exc}", fg=typer.colors.RED, err=True
        )

        if verbose:
            import sys
            import traceback

            traceback.print_exc(file=sys.stderr)

        # Graceful termination, mirroring _safe_load behaviour
        raise typer.Exit(code=1) from exc

    # ------------------------------------------------------------------ #
    # Write                                                                #
    # ------------------------------------------------------------------ #
    try:
        # NOTE: _write_chunks_jsonl is assumed to be defined elsewhere in the module
        _write_chunks_jsonl(chunks, out_path, cfg)
        typer.secho(
            f"✅ Wrote {len(chunks)} chunks → {out_path}",
            fg=typer.colors.GREEN,
        )
    except (OSError, jsonlines.Error) as exc:  # pragma: no cover
        typer.secho(
            f"❌  Failed to write output file: {exc}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from exc


# --------------------------------------------------------------------------- #
# Helper – primitives & serialization                                         #
# --------------------------------------------------------------------------- #
_PRIMITIVE = (str, int, float, bool, type(None))


def _json_safe(val: Any, *, max_depth: int = 50) -> Any:
    """Iteratively converts a Python object into a JSON-serializable structure.

    This function safely traverses complex object graphs, including those with
    circular references or excessive nesting, and converts them into a structure
    composed of dicts, lists, and JSON primitives.

    Rationale:
        An iterative, stack-based approach was chosen over a recursive one to
        prevent `RecursionError` on deeply nested data from external sources.
        This ensures robustness in the data ingestion pipeline. The cycle
        detection mechanism (`on_path`) is precise, correctly ignoring legitimate
        shared sub-objects while catching true circular references. This is a
        common failure point in simpler `visited` set implementations.

    Args:
        val (Any): The Python object to convert.
        max_depth (int): The maximum traversal depth. Branches exceeding this
            depth will be converted to their string representation `str(obj)`
            instead of being explored further. Defaults to 50.

    Returns:
        Any: A JSON-serializable representation of the input value, composed of
        dicts, lists, and primitive types. Unsupported objects are stringified.

    Implementation Notes:
        - Complexity: The algorithm runs in O(N) time, where N is the total
          number of elements (values in lists/tuples/sets and key-value pairs
          in dicts) in the object graph.
        - Cycle Detection: A cycle is detected if an object's ID is found in the
          `on_path` set, which tracks objects in the current traversal path.
        - Determinism: Sets are converted to lists and sorted to ensure
          deterministic output, which is important for stable hashing.
    """
    if isinstance(val, _PRIMITIVE):
        return val

    # Stack frame: (object, depth, parent_container, key_in_parent, visited_flag)
    stack: list[tuple[Any, int, Any | None, Any | None, bool]] = [
        (val, 0, None, None, False)
    ]
    root_out: Any = None
    on_path: set[int] = set()  # IDs of objects in the current traversal branch

    while stack:
        cur, depth, parent, key, entered = stack.pop()
        obj_id = id(cur)

        # Finished exploring children of `cur`, so remove from path and continue.
        if entered:
            on_path.discard(obj_id)
            continue

        # Convert primitives or objects beyond max_depth and assign to parent.
        if depth >= max_depth or isinstance(cur, _PRIMITIVE):
            converted = cur if isinstance(cur, _PRIMITIVE) else str(cur)
            if parent is None:
                root_out = converted
            elif isinstance(parent, dict):
                parent[key] = converted
            else:  # Parent is a list surrogate being built in reverse.
                parent.insert(0, converted)
            continue

        # A true circular reference is detected. Mark it and assign to parent.
        if obj_id in on_path:
            converted = "[Circular Reference]"
            if parent is None:
                root_out = converted
            elif isinstance(parent, dict):
                parent[key] = converted
            else:
                parent.insert(0, converted)
            continue

        # First visit to a composite object: mark it and process its children.
        on_path.add(obj_id)
        container: List[Any] | Dict[str, Any] | str

        if isinstance(cur, dict):
            container = {}
            # Re-visit this node after its children are processed.
            stack.append((cur, depth, parent, key, True))
            # Push children in reverse to process them in original order.
            for k, v in reversed(list(cur.items())):
                stack.append((v, depth + 1, container, str(k), False))
        elif isinstance(cur, (list, tuple, set)):
            container = []
            stack.append((cur, depth, parent, key, True))
            # Sort sets for deterministic output; keep list/tuple order.
            items = sorted(cur, key=str) if isinstance(cur, set) else list(cur)
            for item in reversed(items):
                stack.append((item, depth + 1, container, None, False))
        else:
            # Fallback: stringify any other unsupported type.
            container = str(cur)
            on_path.discard(obj_id)  # No children to explore.

        # Attach the newly created container (or stringified value) to its parent.
        if parent is None:
            root_out = container
        elif isinstance(parent, dict):
            parent[key] = container
        else:
            parent.insert(0, container)

    # `root_out` is guaranteed to be assigned unless the initial `val` is empty.
    # The assert provides a mypy guard and a runtime sanity check.
    assert root_out is not None, "root_out should have been initialised"
    return root_out


def _write_chunks_jsonl(
    chunks: Iterable[Any],
    out_path: pathlib.Path,
    cfg: ChunkConfig,
) -> None:
    """Serializes an iterable of data chunks to a file in JSON Lines format.

    This function writes each chunk as a separate JSON object on a new line,
    assigning a deterministic, globally-unique ID to each one.

    Rationale:
        The JSONL format is used for its stream-ability and ease of use with
        big data tools. The deterministic ID generation is crucial for idempotent
        data ingestion pipelines, allowing for reliable updates, content
        verification, and stable references in downstream vector stores without
        duplication.

    Args:
        chunks (Iterable[Any]): An iterable of chunk objects. Each chunk must
            have `page_content` (str) and `metadata` (dict) attributes.
        out_path (pathlib.Path): The file path to write the JSONL output to.
        cfg (ChunkConfig): Configuration object containing parameters for ID
            generation like `id_hash_bits` and `id_path_mode`.

    Raises:
        IOError: If the file at `out_path` cannot be opened or written to.
        AttributeError: If a chunk object is missing `page_content` or
            `metadata` attributes.

    Implementation Notes:
        The unique chunk ID has the format `<path>#p<page>.<pos>-<hash>`:
        - `path`: Source path encoded according to `cfg.id_path_mode`.
        - `page`: The 0-indexed page number from chunk metadata.
        - `pos`: The 0-indexed position of the chunk within its page.
        - `hash`: A truncated SHA-256 hash of `chunk.page_content` for uniqueness.
    """
    # Counter keyed by (source_path, page) to track chunk position.
    position_ctr: defaultdict[tuple[str, int], int] = defaultdict(int)

    with jsonlines.open(out_path, mode="w") as writer:
        for chunk in chunks:
            # 1. Normalize the source path using the configured strategy.
            src_path = _norm_source(chunk.metadata.get("source", ""), cfg)

            # 2. Extract page number from metadata.
            page = int(chunk.metadata.get("page", 0))

            # 3. Determine the chunk's sequential position on its page.
            pos = position_ctr[(src_path, page)]
            position_ctr[(src_path, page)] += 1

            # 4. Generate content hash.
            hex_len = cfg.id_hash_bits // 4
            digest = hashlib.sha256(
                chunk.page_content.encode("utf-8", "surrogatepass")
            ).hexdigest()[:hex_len]

            # 5. Assemble the stable, globally-unique ID.
            chunk_id = f"{src_path}#p{page}.{pos}-{digest}"

            writer.write(
                {
                    "id": chunk_id,
                    "text": chunk.page_content,
                    "meta": _json_safe(chunk.metadata),
                }
            )
