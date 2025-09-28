"""Main CLI entry point for ingenious-docprep package."""

from __future__ import annotations

import typer
from rich import print as rprint

app = typer.Typer(
    name="docprep",
    help="Document preprocessing tools for RAG pipelines",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Import and register sub-commands
try:
    from ingenious_docprep.chunk.cli import cli as chunk_cli
    app.add_typer(chunk_cli, name="chunk")
except ImportError as e:
    rprint(f"[red]Warning: Could not load chunk module: {e}[/red]")

try:
    from ingenious_docprep.document_processing.cli import doc_app
    app.add_typer(doc_app, name="extract")
except ImportError as e:
    rprint(f"[red]Warning: Could not load document processing module: {e}[/red]")

try:
    from ingenious_docprep.dataprep.cli import dataprep
    app.add_typer(dataprep, name="dataprep")
except ImportError as e:
    rprint(f"[red]Warning: Could not load dataprep module: {e}[/red]")


@app.callback()
def main():
    """
    Document preprocessing tools for RAG pipelines.
    
    This CLI provides utilities for:
    - Document chunking (chunk)
    - Document extraction (extract) 
    - Data preparation (dataprep)
    """
    pass


def cli():
    """Entry point for the CLI."""
    app()


# Make main() callable for the entry point 
main = cli


if __name__ == "__main__":
    cli()