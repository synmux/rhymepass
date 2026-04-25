"""Password-strength scoring helpers backed by ``zxcvbn``.

This module wraps :func:`zxcvbn.zxcvbn` (the canonical Python port of
Dropbox's password strength estimator) and renders its 0..4 score as
the user-facing emoji + star indicator that follows each generated
passphrase in both the pipe output and the interactive picker.

The module is deliberately free of any UI-framework imports. Both
:mod:`rhymepass.cli` (the pipe path) and :mod:`rhymepass.ui` (the
TTY path) import these helpers, and pulling Textual in here would
break the lazy-import contract documented in ``AGENTS.md``: the pipe
path must never load Textual.
"""

from __future__ import annotations

from zxcvbn import zxcvbn as _analyse

_QUALITY_EMOJI: tuple[str, ...] = ("🤮", "🙁", "🫤", "🙂", "🥳")
"""Emoji per zxcvbn score, indexed by score (0..4)."""

_STAR: str = "⭐"
"""Star glyph used to render the right-hand half of the indicator."""

_SEPARATOR: str = " | "
"""Visual separator between the emoji and the star run."""


def score_passphrase(text: str) -> int:
    """Return a zxcvbn strength score in ``[0, 4]`` for ``text``.

    Args:
        text: The exact passphrase string to score. Pass it in the
            form the user will actually use it: zxcvbn analyses the
            literal characters, so ``"the cat sat"`` and
            ``"thecatsat"`` may receive different scores.

    Returns:
        An ``int`` in ``[0, 4]`` matching zxcvbn's published scale
        (0 = trivial, 4 = very strong).
    """
    return int(_analyse(text)["score"])


def format_strength(score: int) -> str:
    """Render the user-facing strength indicator.

    The shape is ``"<emoji> | <stars>"`` where the star count grows
    from one (score 0) to five (score 4) - so even the weakest
    password gets a single star, making the visual always present.

    Args:
        score: A zxcvbn score in ``[0, 4]``.

    Returns:
        A string of the form ``"🥳 | ⭐⭐⭐⭐⭐"``.

    Raises:
        ValueError: If ``score`` is outside ``[0, 4]``.
    """
    if not 0 <= score <= 4:
        raise ValueError(f"score must be in [0, 4], got {score!r}")
    stars = _STAR * (score + 1)
    return f"{_QUALITY_EMOJI[score]}{_SEPARATOR}{stars}"
