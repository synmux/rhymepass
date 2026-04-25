"""Batch passphrase generation.

A thin orchestration helper over :func:`rhymepass.generator.generate`
and :func:`rhymepass.randomgen.generate_random`. The module exists so
the CLI pipe path and the picker's regeneration worker share one
dispatch on ``random_mode`` instead of duplicating it.

The function is intentionally tiny - it does not score, it does not
mutate UI state. Callers are responsible for whatever post-processing
they need (the picker scores each phrase off-thread; the CLI scores
each phrase on the way to stderr).
"""

from __future__ import annotations

from rhymepass.generator import generate
from rhymepass.randomgen import (
    _DEFAULT_CLASSES,
    DEFAULT_RANDOM_LEN,
    generate_random,
)


def generate_batch(
    count: int,
    pool: list[str] | None,
    real_words: set[str] | None,
    *,
    random_mode: bool = False,
    limit: int = 0,
    classes: tuple[str, ...] | None = None,
) -> list[str]:
    """Generate ``count`` passphrases for the chosen mode.

    In rhyme mode this calls :func:`rhymepass.generator.generate`
    ``count`` times against the supplied anchor pool. In random mode
    it calls :func:`rhymepass.randomgen.generate_random` ``count``
    times against the supplied character classes.

    The two modes have different limit semantics, mirroring the
    picker:

    * **Rhyme**: ``limit`` is the maximum spaced length (with ``0``
      meaning "no limit"). The generator descends through shorter
      shapes for the same anchor before drawing a new anchor.
    * **Random**: ``limit`` is the *exact* length, with ``0`` meaning
      :data:`rhymepass.randomgen.DEFAULT_RANDOM_LEN` (24).

    Args:
        count: Number of passphrases to return. Must be ``>= 1``;
            callers (the CLI and the worker) already validate this.
        pool: Anchor pool from
            :func:`rhymepass.anchors.build_anchor_pool`. Required in
            rhyme mode; may be ``None`` in random mode (the random
            generator does not touch it).
        real_words: GCIDE word set from
            :func:`rhymepass.anchors.load_real_words`. Required in
            rhyme mode; may be ``None`` in random mode.
        random_mode: ``True`` to draw fully random fixed-length
            passwords, ``False`` (the default) for rhyming couplets.
        limit: Length constraint. See above for the per-mode
            interpretation. Default ``0``.
        classes: Resolved character-class strings (the output of
            :func:`rhymepass.randomgen.resolve_classes`). Used only
            in random mode; defaults to the same four-class default
            :func:`generate_random` itself uses.

    Returns:
        A list of exactly ``count`` passphrases.

    Raises:
        ValueError: If rhyme mode is requested without a ``pool`` or
            ``real_words`` argument; if random mode is requested with
            an invalid length / class combination (re-raised from
            :func:`generate_random`).
        RuntimeError: If rhyme mode cannot fit ``count`` phrases under
            ``limit`` within the generator's retry budget (re-raised
            from :func:`generate`).
    """
    if random_mode:
        target_len = limit if limit > 0 else DEFAULT_RANDOM_LEN
        chosen_classes = classes if classes is not None else _DEFAULT_CLASSES
        return [
            generate_random(length=target_len, classes=chosen_classes)
            for _ in range(count)
        ]

    if pool is None or real_words is None:
        raise ValueError(
            "rhyme mode requires both `pool` and `real_words`; "
            "got pool=%r, real_words=%r" % (pool, real_words)
        )
    return [generate(pool, real_words, limit=limit) for _ in range(count)]
