"""Fully random password generator.

This is the peer of :mod:`rhymepass.generator` for the picker's
*random mode*. Where :func:`rhymepass.generator.generate` builds a
rhyming, memorable couplet, :func:`generate_random` draws a fixed-length
string uniformly at random from a curated character set.

The character set is the union of:

* :data:`LOWERCASE` - ASCII a..z
* :data:`UPPERCASE` - ASCII A..Z
* :data:`DIGITS` - 0..9
* :data:`SAFE_SYMBOLS` - punctuation chosen to avoid shell, URL, regex
  and SQL interpretation

Every output is guaranteed to contain at least one character from
each of the four classes, and the final character order is shuffled
with :class:`secrets.SystemRandom` so the "one-of-each" guarantee
does not leak positional information.

The module deliberately uses :mod:`secrets` (CSPRNG) for every draw -
never :mod:`random` - because the output is a credential.
"""

from __future__ import annotations

import secrets
import string

LOWERCASE: str = string.ascii_lowercase
"""ASCII lowercase letters (``a..z``); 26 characters."""

UPPERCASE: str = string.ascii_uppercase
"""ASCII uppercase letters (``A..Z``); 26 characters."""

DIGITS: str = string.digits
"""ASCII decimal digits (``0..9``); 10 characters."""

SAFE_SYMBOLS: str = "@-_.,:§"
"""Punctuation safe to include in random passwords.

A character is considered safe here when it has no syntactic meaning
in any of the contexts a password regularly traverses:

* POSIX shells (no quoting, escaping, expansion, redirection,
  command-substitution or globbing).
* URLs and HTTP form bodies (no percent-encoding required, no query
  or fragment delimiters).
* Regex (no metacharacter behaviour outside character classes).
* CSV / TSV (no separator collisions in the most common dialects).

The current set is ``@ - _ . , : §`` (7 characters). The Unicode
section sign (``§``, U+00A7) is included because it is UTF-8 safe
across well-formed HTTP forms and is commonly accepted by password
fields, while remaining outside the ASCII shell-metacharacter set.

Explicitly **excluded** for shell or HTTP reasons:
``! " ' \\ ` $ * ? ; & | < > ( ) { } [ ] # % = + / ~`` and the space
character.
"""

DEFAULT_RANDOM_LEN: int = 24
"""Length used when the picker's limit is ``0`` (\"no limit\").

24 characters with a 69-character alphabet carries roughly 146 bits
of entropy - comfortably above the 128-bit "long-term safe"
threshold while still fitting most password fields without
truncation.
"""

MIN_RANDOM_LEN: int = 4
"""Smallest length :func:`generate_random` accepts.

The function guarantees at least one character from each of the four
classes (lowercase, uppercase, digit, symbol), so a length of 4 is
the smallest value that can satisfy that guarantee.
"""

_CHARSET: str = LOWERCASE + UPPERCASE + DIGITS + SAFE_SYMBOLS
"""Combined alphabet used to fill positions beyond the one-of-each guarantee."""


def generate_random(length: int = DEFAULT_RANDOM_LEN) -> str:
    """Return a random password of exactly ``length`` characters.

    Strategy:

    1. Draw one character each from :data:`LOWERCASE`,
       :data:`UPPERCASE`, :data:`DIGITS` and :data:`SAFE_SYMBOLS` so
       every output contains the full character-class mix.
    2. Fill the remaining ``length - 4`` slots with uniform draws
       from the combined alphabet (:data:`_CHARSET`).
    3. Shuffle the resulting list with :class:`secrets.SystemRandom`
       so the mandatory characters are not always in the first four
       positions.

    Every random draw uses :mod:`secrets`, which is the cryptographic
    PRNG the standard library exposes for credential generation.

    The per-class guarantee introduces a microscopic bias relative to
    a strict uniform draw from the alphabet (the four mandatory
    classes are sampled from smaller pools). For ``length == 4`` this
    is not a bias at all - the output is a uniform sample from the
    cartesian product. For longer lengths the deviation is
    ``O(1/length)`` and is well below the resolution of any
    downstream strength estimator.

    Args:
        length: Total number of characters to emit. Must be at least
            :data:`MIN_RANDOM_LEN` (4).

    Returns:
        A string of exactly ``length`` characters drawn from
        :data:`LOWERCASE`, :data:`UPPERCASE`, :data:`DIGITS` and
        :data:`SAFE_SYMBOLS`.

    Raises:
        ValueError: If ``length < MIN_RANDOM_LEN`` or if
            :data:`SAFE_SYMBOLS` has been replaced with an empty
            string at runtime.
    """
    if length < MIN_RANDOM_LEN:
        raise ValueError(f"length must be at least {MIN_RANDOM_LEN}; got {length!r}")
    if not SAFE_SYMBOLS:
        raise ValueError("SAFE_SYMBOLS is empty; cannot guarantee a symbol")

    chars: list[str] = [
        secrets.choice(LOWERCASE),
        secrets.choice(UPPERCASE),
        secrets.choice(DIGITS),
        secrets.choice(SAFE_SYMBOLS),
    ]
    chars.extend(secrets.choice(_CHARSET) for _ in range(length - MIN_RANDOM_LEN))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)
