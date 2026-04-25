"""Fully random password generator.

This is the peer of :mod:`rhymepass.generator` for the picker's
*random mode*. Where :func:`rhymepass.generator.generate` builds a
rhyming, memorable couplet, :func:`generate_random` draws a fixed-length
string uniformly at random from a caller-chosen set of character
classes.

The five available classes are:

* :data:`LOWERCASE` - ASCII a..z (26 chars)
* :data:`UPPERCASE` - ASCII A..Z (26 chars)
* :data:`DIGITS` - 0..9 (10 chars)
* :data:`SAFE_SYMBOLS` - punctuation chosen to avoid shell, URL,
  regex and SQL interpretation (7 chars)
* :data:`ALL_SYMBOLS` - the union of :data:`SAFE_SYMBOLS` and
  :data:`UNSAFE_SYMBOLS` (every ASCII punctuation char plus ``§``)

The picker's interactive charset toggles let the user pick any
non-empty subset of the first four; ``ALL_SYMBOLS`` is selected
indirectly by enabling the "all symbols" toggle, which uses
:data:`ALL_SYMBOLS` in place of :data:`SAFE_SYMBOLS`.

For any chosen subset, :func:`generate_random` guarantees at least
one character from each class; the remaining slots are uniform draws
from the union of the chosen classes; the final character order is
shuffled with :class:`secrets.SystemRandom` so the "one-of-each"
guarantee does not leak positional information.

The module deliberately uses :mod:`secrets` (CSPRNG) for every draw -
never :mod:`random` - because the output is a credential.
"""

from __future__ import annotations

import secrets
import string
from collections.abc import Iterable, Sequence

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

UNSAFE_SYMBOLS: str = "".join(c for c in string.punctuation if c not in SAFE_SYMBOLS)
"""ASCII punctuation that has shell, URL, regex or CSV interpretation.

Computed as ``string.punctuation - SAFE_SYMBOLS`` so the two are
mechanically disjoint - editing :data:`SAFE_SYMBOLS` automatically
keeps this set correct. The Unicode section sign (``§``) is in
:data:`SAFE_SYMBOLS` but never in ``string.punctuation``, so it is
not duplicated here either. Used only when the picker's "all symbols"
toggle is enabled, in which case :data:`ALL_SYMBOLS` (the union)
replaces :data:`SAFE_SYMBOLS` in the active class list.
"""

ALL_SYMBOLS: str = SAFE_SYMBOLS + UNSAFE_SYMBOLS
"""Every symbol the random generator will use under "all symbols" mode.

This is the set the picker hands to :func:`generate_random` when the
``[5] All`` charset toggle is on: the safe baseline plus every
ASCII shell-metacharacter that we deliberately omit by default. By
construction, ``set(ALL_SYMBOLS) == set(SAFE_SYMBOLS) | set(UNSAFE_SYMBOLS)``
and there are no duplicates.
"""

DEFAULT_RANDOM_LEN: int = 24
"""Length used when the picker's limit is ``0`` (\"no limit\").

24 characters with a 69-character alphabet carries roughly 146 bits
of entropy - comfortably above the 128-bit "long-term safe"
threshold while still fitting most password fields without
truncation.
"""

MIN_RANDOM_LEN: int = 4
"""Smallest length :func:`generate_random` accepts under the default classes.

The function guarantees at least one character from each requested
class, so the true minimum is ``len(classes)``. With the default
four classes (lowercase, uppercase, digits, safe symbols) that
becomes 4. The picker uses this constant as the modal's minimum
value in random mode and bumps it dynamically when extra classes
are toggled on.
"""

_DEFAULT_CLASSES: tuple[str, ...] = (LOWERCASE, UPPERCASE, DIGITS, SAFE_SYMBOLS)
"""Default character classes used when ``classes`` is omitted."""

CLASS_NAMES: tuple[str, ...] = ("upper", "lower", "digits", "safe", "all")
"""Valid internal names accepted by :func:`resolve_classes`.

Listed in display order: rendering helpers, ``--help`` output, and the
picker's charset bar all iterate this tuple to keep their order in
sync."""

DEFAULT_CHARSET: frozenset[str] = frozenset({"upper", "lower", "digits", "safe"})
"""Default random-mode class set: every default class except ``"all"``.

Shared by the CLI (as the default for ``--classes``) and by the
interactive picker (as the initial value of
:attr:`rhymepass.ui.PassphraseApp.charset`) so the two surfaces never
disagree about what "default" means."""


def generate_random(
    length: int = DEFAULT_RANDOM_LEN,
    classes: Sequence[str] | None = None,
) -> str:
    """Return a random password of exactly ``length`` characters.

    Strategy:

    1. Draw one character from each entry in ``classes`` so every
       output contains at least one character from each requested
       class.
    2. Fill the remaining ``length - len(classes)`` slots with
       uniform draws from the combined alphabet (the concatenation
       of all ``classes``).
    3. Shuffle the resulting list with :class:`secrets.SystemRandom`
       so the mandatory characters are not always in the first
       ``len(classes)`` positions.

    Every random draw uses :mod:`secrets`, which is the cryptographic
    PRNG the standard library exposes for credential generation.

    The per-class guarantee introduces a microscopic bias relative to
    a strict uniform draw from the alphabet (the mandatory class
    samples come from smaller pools). For ``length == len(classes)``
    this is not a bias at all - the output is a uniform sample from
    the cartesian product. For longer lengths the deviation is
    ``O(1/length)`` and is well below the resolution of any
    downstream strength estimator.

    Args:
        length: Total number of characters to emit. Must be at least
            ``len(classes)``.
        classes: Sequence of non-empty character-class strings to
            draw from. ``None`` (the default) uses
            ``(LOWERCASE, UPPERCASE, DIGITS, SAFE_SYMBOLS)``, which
            matches the picker's default charset and preserves the
            original public behaviour of this function.

    Returns:
        A string of exactly ``length`` characters drawn from the
        union of ``classes``.

    Raises:
        ValueError: If ``classes`` is empty, contains an empty
            string, or if ``length < len(classes)``.
    """
    if classes is None:
        classes = _DEFAULT_CLASSES
    if not classes:
        raise ValueError("at least one character class is required")
    for cls in classes:
        if not cls:
            raise ValueError("character classes must be non-empty strings")
    if length < len(classes):
        raise ValueError(
            f"length must be at least {len(classes)} to fit one of each "
            f"of the {len(classes)} requested classes; got {length!r}"
        )

    chars: list[str] = [secrets.choice(cls) for cls in classes]
    alphabet: str = "".join(classes)
    chars.extend(secrets.choice(alphabet) for _ in range(length - len(classes)))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def resolve_classes(names: Iterable[str]) -> tuple[str, ...]:
    """Map internal class names to their character-set strings.

    The mapping mirrors the picker's resolved charset:

    * ``"upper"`` -> :data:`UPPERCASE`
    * ``"lower"`` -> :data:`LOWERCASE`
    * ``"digits"`` -> :data:`DIGITS`
    * ``"safe"`` -> :data:`SAFE_SYMBOLS`
    * ``"all"`` -> :data:`ALL_SYMBOLS` (replaces ``"safe"`` in the
      output because :data:`ALL_SYMBOLS` already contains the safe
      baseline; including both would duplicate every safe symbol).

    The returned tuple is always in display order
    (``UPPERCASE``, ``LOWERCASE``, ``DIGITS``, then either
    ``ALL_SYMBOLS`` or ``SAFE_SYMBOLS``) regardless of the order
    ``names`` arrives in.

    Args:
        names: Iterable of internal class names. Members must come
            from :data:`CLASS_NAMES`.

    Returns:
        Tuple of class strings suitable for passing to
        :func:`generate_random` as the ``classes`` argument.

    Raises:
        ValueError: If ``names`` is empty or contains an unknown name.
    """
    name_set = frozenset(names)
    if not name_set:
        raise ValueError("at least one class name is required")
    invalid = name_set - frozenset(CLASS_NAMES)
    if invalid:
        raise ValueError(
            f"unknown class name(s): {sorted(invalid)}. "
            f"Valid choices: {', '.join(CLASS_NAMES)}."
        )
    parts: list[str] = []
    if "upper" in name_set:
        parts.append(UPPERCASE)
    if "lower" in name_set:
        parts.append(LOWERCASE)
    if "digits" in name_set:
        parts.append(DIGITS)
    if "all" in name_set:
        parts.append(ALL_SYMBOLS)
    elif "safe" in name_set:
        parts.append(SAFE_SYMBOLS)
    return tuple(parts)
