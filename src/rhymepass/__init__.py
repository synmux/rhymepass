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
* :func:`score_passphrase` - score a passphrase with ``zxcvbn``.
* :func:`format_strength` - render the ``"<emoji> | <stars>"``
  indicator from a 0..4 score.

A typical library usage pattern is::

    from rhymepass import (
        generate,
        build_anchor_pool,
        load_real_words,
        score_passphrase,
        format_strength,
    )

    real_words = load_real_words()
    pool = build_anchor_pool(real_words)
    phrase = generate(pool, real_words)
    print(phrase, "|", format_strength(score_passphrase(phrase)))

The package also ships the ``rhymepass`` and ``rp`` console scripts,
defined in :mod:`rhymepass.cli`.
"""

from __future__ import annotations

from rhymepass.anchors import build_anchor_pool, load_real_words
from rhymepass.generator import generate
from rhymepass.strength import format_strength, score_passphrase

__version__ = "0.0.0.dev1"

__all__ = [
    "__version__",
    "build_anchor_pool",
    "format_strength",
    "generate",
    "load_real_words",
    "score_passphrase",
]
