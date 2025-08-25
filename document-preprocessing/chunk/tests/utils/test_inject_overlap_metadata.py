"""
insight ingenious ▸ chunk ▸ tests ▸ utils ▸ *test_inject_overlap_metadata*
---------------------------------------------------------------------
Regression‑test module ensuring that the *inject_overlap* utility does **not**
introduce metadata aliasing across the chunks it produces.

Purpose & context
=================
`inject_overlap` duplicates or splices neighbouring chunks so that downstream
LLM agents can preserve a specified amount of textual context (*k*) between
adjacent segments.  Prior to **Issue M1**, the function reused the *same*
`metadata` dict when overlapping, meaning an *in‑place* mutation on one chunk
unexpectedly propagated to its siblings.  This module reproduces that edge case
and asserts the bug is fixed.

Key algorithms / design choices
-------------------------------
* Use a **single** `Document` instance (`base`) twice in the input list to make
  aliasing obvious—if `inject_overlap` fails to deep‑copy metadata, the test
  fails.
* Mutate the nested list under the `"tags"` key; lists highlight shallow copy
  issues because `+=` and `.append()` mutate in‑place.
"""

from langchain_core.documents import Document

from ingenious.chunk.utils.overlap import inject_overlap


def test_metadata_isolated() -> None:
    """Verify metadata isolation between overlapped chunks.

    Rationale
    ---------
    Regression guard for **Issue M1** where `inject_overlap` reused the same
    `metadata` mapping across the returned chunks, causing side‑effects when
    callers mutated metadata in‑place.

    Raises
    ------
    AssertionError
        If mutating the `tags` list of the first chunk leaks into the second
        chunk, the assertions will fail and surface the regression.

    Implementation notes
    --------------------
    * Two identical `Document` instances are supplied so that the only variable
      is the behaviour of *inject_overlap* itself.
    * The mutation uses :pymeth:`list.append` because it mutates the nested
      structure in‑place—exactly the scenario that was previously broken.
    """

    base = Document(page_content="AAA BBB", metadata={"id": 1, "tags": ["x"]})

    c0, c1 = inject_overlap([base, base], k=3, unit="characters")

    c0.metadata["tags"].append("mutated")  # mutate in‑place
    assert c1.metadata["tags"] == ["x"]  # isolation verified
