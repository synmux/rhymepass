"""Passphrase generator.

:func:`generate` is the library's main workhorse. It draws a random
anchor word from the pool, looks up phonetic rhymes via the CMU
Pronouncing Dictionary, filters those rhymes through the same anchor
quality checks, and assembles a short rhyming couplet from two
fillered phrases plus a two-digit numeric suffix.

An optional character limit forces the generator to prefer shorter
output. When a limit is set, the generator walks through progressively
shorter shapes *for the same anchor* before giving up and drawing a
fresh anchor:

1. **Couplet descent** — try filler budgets from 4 down to 0, and
   every legal ``(fillers_a, fillers_b)`` split within each budget.
2. **Single-statement fallback** — only engaged when ``limit > 0``;
   drops the rhyme partner entirely and emits ``"<phrase> / NN"``.
   Unlimited generation never falls back — it redraws until a
   rhyming couplet is found.

The shape constants at the top of this module describe the minimum
lengths achievable under each shape; they also inform the UI's limit
validator.
"""

from __future__ import annotations

import secrets

import pronouncing

from rhymepass.anchors import _is_good_anchor
from rhymepass.phrases import _build_phrase, _capitalise, _couplet_filler_splits

SUFFIX_LEN: int = len(" / 12")
"""Length of the ``" / NN"`` suffix appended to every passphrase (5)."""

COUPLET_SEP_LEN: int = len(" / ")
"""Length of the ``" / "`` separator between the two couplet halves (3)."""

MIN_ANCHOR_LEN: int = 4
"""Minimum anchor-word length; mirrors the check in :func:`rhymepass.anchors._is_good_anchor`."""

MIN_COUPLET_LEN: int = 2 * MIN_ANCHOR_LEN + COUPLET_SEP_LEN + SUFFIX_LEN
"""Shortest achievable couplet form (16: ``"Abcd / abcd / 12"``)."""

MIN_SINGLE_LEN: int = MIN_ANCHOR_LEN + SUFFIX_LEN
"""Shortest achievable single-statement form (9: ``"Abcd / 12"``)."""


def generate(
    pool: list[str],
    real_words: set[str],
    limit: int = 0,
    max_attempts: int = 300,
) -> str:
    """Generate a single rhyming passphrase.

    Overall format:

    * Couplet: ``"<phrase A> / <phrase B> / <NN>"``.
    * Single-statement fallback (limit only): ``"<phrase> / <NN>"``.

    Each phrase is an anchor wrapped in 0–2 filler words. The first
    character of the first phrase is capitalised. The ``" / NN"``
    suffix is always appended, where ``NN`` is a random two-digit
    number in ``10..99``.

    Generation strategy when ``limit > 0``:

    1. Draw an anchor ``word_a``. If it has good rhymes, draw
       ``word_b`` from those rhymes and try progressively smaller
       filler budgets (4 → 0), iterating every legal
       ``(fillers_a, fillers_b)`` split within each budget. Return
       the first candidate whose length fits the limit.
    2. If no couplet fits, fall back to the single-statement form
       using just ``word_a`` and try filler counts 2 → 1 → 0.
    3. If neither form fits for this anchor, draw another anchor.

    When ``limit == 0`` the single-statement fallback is skipped
    entirely: unlimited generation must produce a rhyming couplet or
    redraw.

    The shortest possible output is ``"Abcd / 12"``
    (:data:`MIN_SINGLE_LEN` = 9); non-zero limits below that value
    are guaranteed to fail within ``max_attempts``.

    Args:
        pool: Anchor pool produced by
            :func:`rhymepass.anchors.build_anchor_pool`.
        real_words: Word-set filter from
            :func:`rhymepass.anchors.load_real_words`, used to
            validate rhyme candidates.
        limit: Maximum total length in characters (spaces included).
            ``0`` disables the check.
        max_attempts: Maximum number of fresh anchors to draw before
            giving up. The default (300) is comfortably above what is
            needed for any realistic limit.

    Returns:
        A passphrase whose spaced length satisfies ``limit``.

    Raises:
        ValueError: If ``pool`` is empty.
        RuntimeError: If no passphrase fitting ``limit`` can be built
            within ``max_attempts``.
    """
    if not pool:
        raise ValueError("Anchor pool is empty; cannot generate passphrases")

    for _ in range(max_attempts):
        word_a = secrets.choice(pool)
        suffix = f" / {secrets.randbelow(90) + 10}"

        # Couplet descent: prefer the rhyming form when rhymes exist.
        rhymes = [
            rhyme
            for rhyme in pronouncing.rhymes(word_a)
            if rhyme != word_a and _is_good_anchor(rhyme, real_words)
        ]
        if rhymes:
            word_b = secrets.choice(rhymes)
            for total in range(4, -1, -1):
                for fillers_a, fillers_b in _couplet_filler_splits(total):
                    left = _capitalise(_build_phrase(word_a, fillers_a))
                    right = _build_phrase(word_b, fillers_b)
                    phrase = f"{left} / {right}{suffix}"
                    if limit == 0 or len(phrase) <= limit:
                        return phrase

        # Single-statement fallback: drop the rhyme partner entirely.
        # Only used under a non-zero limit — unlimited generation must
        # stay rhyming, so we redraw instead of accepting a non-rhyming
        # phrase.
        if limit > 0:
            for fillers in (2, 1, 0):
                left = _capitalise(_build_phrase(word_a, fillers))
                phrase = f"{left}{suffix}"
                if len(phrase) <= limit:
                    return phrase

        # Neither form fit this anchor; draw another and try again.

    raise RuntimeError(
        f"Could not generate a passphrase under {limit} characters"
        f" after {max_attempts} attempts"
    )
