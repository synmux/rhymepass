"""Shared pytest fixtures.

The ``real_words`` and ``anchor_pool`` fixtures are session-scoped
because building them takes ~1 second (GCIDE is ~7 MB, and
:func:`rhymepass.anchors.build_anchor_pool` walks the entire CMU
dictionary). Reusing the same instances across every test that needs
them keeps the full suite under a couple of seconds.

The ``tiny_pool`` fixture returns a curated five-word list whose
rhymes are known, for tests that need deterministic anchor selection
without loading the full dictionary. It is *function-scoped* since
it is trivially cheap to build.
"""

from __future__ import annotations

import pytest

from rhymepass.anchors import build_anchor_pool, load_real_words


@pytest.fixture(scope="session")
def real_words() -> set[str]:
    """Session-scoped GCIDE word set."""
    return load_real_words()


@pytest.fixture(scope="session")
def anchor_pool(real_words: set[str]) -> list[str]:
    """Session-scoped full anchor pool built from the real-word filter."""
    return build_anchor_pool(real_words)


@pytest.fixture
def tiny_pool() -> list[str]:
    """Five-word anchor list whose rhymes are reliable across CMU builds."""
    return ["parade", "accolade", "rhyme", "crime", "chime"]
