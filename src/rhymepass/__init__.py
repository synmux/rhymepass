"""rhymepass - generate memorable, rhyming passphrases.

Overview
--------

``rhymepass`` draws anchor words from the CMU Pronouncing Dictionary
(filtered against the GCIDE English word list), finds phonetic
rhymes, wraps each side in short filler words, and appends two random
digits. The result is a passphrase that is easy to read, easy to
type, and hard to guess.

Public API
----------

* :func:`generate` - build a single passphrase.
* :func:`build_anchor_pool` - construct the anchor pool used by
  :func:`generate`. Can be called once per process and reused for
  many generations.
* :func:`load_real_words` - load the GCIDE word set used to filter
  the anchor pool.

A typical library usage pattern is::

    from rhymepass import generate, build_anchor_pool, load_real_words

    real_words = load_real_words()
    pool = build_anchor_pool(real_words)
    print(generate(pool, real_words))
    print(generate(pool, real_words, limit=24))

The package also ships the ``rhymepass`` and ``rp`` console scripts,
defined in :mod:`rhymepass.cli`.
"""

from __future__ import annotations

from rhymepass.anchors import build_anchor_pool, load_real_words
from rhymepass.generator import generate

__version__ = "0.0.0.dev1"

__all__ = [
    "__version__",
    "build_anchor_pool",
    "generate",
    "load_real_words",
]
