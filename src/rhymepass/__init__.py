"""rhymepass - generate memorable, rhyming passphrases.

Overview
--------

``rhymepass`` draws anchor words from the CMU Pronouncing Dictionary
(filtered against the GCIDE English word list), finds phonetic
rhymes, wraps each side in short filler words, and appends two random
digits. The result is a passphrase that is easy to read, easy to
type, and hard to guess.

For situations where a memorable phrase is the wrong tool - very
short fields, PIN-style snippets, or anywhere maximum entropy per
character matters - the package also exposes :func:`generate_random`,
which produces a fixed-length string drawn uniformly from a curated
character set (lowercase + uppercase + digits + a small set of
shell-/HTTP-safe symbols).

Public API
----------

* :func:`generate` - build a single rhyming passphrase.
* :func:`generate_random` - build a fully random fixed-length password.
* :func:`build_anchor_pool` - construct the anchor pool used by
  :func:`generate`. Can be called once per process and reused for
  many generations.
* :func:`load_real_words` - load the GCIDE word set used to filter
  the anchor pool.
* :func:`score_passphrase` - score a passphrase with ``zxcvbn``.
* :func:`format_strength` - render the ``"<emoji> | <stars>"``
  indicator from a 0..4 score.
* :data:`SAFE_SYMBOLS`, :data:`DEFAULT_RANDOM_LEN`,
  :data:`MIN_RANDOM_LEN` - random-generator configuration exposed
  for callers that need to mirror the picker's behaviour.

A typical library usage pattern is::

    from rhymepass import (
        generate,
        generate_random,
        build_anchor_pool,
        load_real_words,
        score_passphrase,
        format_strength,
    )

    # Rhyming flavour
    real_words = load_real_words()
    pool = build_anchor_pool(real_words)
    phrase = generate(pool, real_words)
    print(phrase, "|", format_strength(score_passphrase(phrase)))

    # Random flavour
    password = generate_random(length=24)
    print(password, "|", format_strength(score_passphrase(password)))

The package also ships the ``rhymepass`` and ``rp`` console scripts,
defined in :mod:`rhymepass.cli`.
"""

from __future__ import annotations

from rhymepass.anchors import build_anchor_pool, load_real_words
from rhymepass.batch import generate_batch
from rhymepass.generator import generate
from rhymepass.randomgen import (
    ALL_SYMBOLS,
    CLASS_NAMES,
    DEFAULT_CHARSET,
    DEFAULT_RANDOM_LEN,
    DIGITS,
    LOWERCASE,
    MIN_RANDOM_LEN,
    SAFE_SYMBOLS,
    UNSAFE_SYMBOLS,
    UPPERCASE,
    generate_random,
    resolve_classes,
)
from rhymepass.strength import format_strength, score_passphrase

__version__ = "0.0.0.dev1"

__all__ = [
    "ALL_SYMBOLS",
    "CLASS_NAMES",
    "DEFAULT_CHARSET",
    "DEFAULT_RANDOM_LEN",
    "DIGITS",
    "LOWERCASE",
    "MIN_RANDOM_LEN",
    "SAFE_SYMBOLS",
    "UNSAFE_SYMBOLS",
    "UPPERCASE",
    "__version__",
    "build_anchor_pool",
    "format_strength",
    "generate",
    "generate_batch",
    "generate_random",
    "load_real_words",
    "resolve_classes",
    "score_passphrase",
]
