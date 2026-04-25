"""Tests for :mod:`rhymepass.strength`.

These tests exercise both halves of the module:

* :func:`format_strength` - a pure function over a tiny finite
  domain, so we cover every score and the validation path.
* :func:`score_passphrase` - a thin wrapper around real ``zxcvbn``
  calls. We do not mock zxcvbn; per the project rules, real service
  calls beat fake ones.
"""

from __future__ import annotations

import pytest

from rhymepass.strength import format_strength, score_passphrase

# ---------------------------------------------------------------------------
# format_strength
# ---------------------------------------------------------------------------


def test_format_strength_score_0_returns_skull_and_one_star() -> None:
    """Score 0 - the worst rating - shows the disgusted emoji and 1 star."""
    assert format_strength(0) == "🤮 | ⭐"


def test_format_strength_score_4_returns_party_and_five_stars() -> None:
    """Score 4 - the best rating - shows the party emoji and 5 stars."""
    assert format_strength(4) == "🥳 | ⭐⭐⭐⭐⭐"


@pytest.mark.parametrize(
    ("score", "expected_stars"),
    [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)],
)
def test_format_strength_each_score_has_score_plus_one_stars(
    score: int, expected_stars: int
) -> None:
    """The star count is ``score + 1`` so even score 0 shows one star."""
    assert format_strength(score).count("⭐") == expected_stars


@pytest.mark.parametrize(
    ("score", "expected_emoji"),
    [(0, "🤮"), (1, "🙁"), (2, "🫤"), (3, "🙂"), (4, "🥳")],
)
def test_format_strength_each_score_uses_correct_emoji(
    score: int, expected_emoji: str
) -> None:
    """The leading emoji follows the user-defined rubric exactly."""
    assert format_strength(score).startswith(expected_emoji)


def test_format_strength_includes_pipe_separator() -> None:
    """The emoji and stars are joined by ``" | "`` exactly once."""
    assert format_strength(2).count(" | ") == 1


@pytest.mark.parametrize("bad_score", [-1, -100, 5, 99])
def test_format_strength_rejects_out_of_range_scores(bad_score: int) -> None:
    """Anything outside ``[0, 4]`` is rejected with ``ValueError``.

    zxcvbn itself can only return 0..4, so an out-of-range value here
    means a programming error - we want it to fail loudly, not be
    silently clamped.
    """
    with pytest.raises(ValueError, match="score must be in"):
        format_strength(bad_score)


# ---------------------------------------------------------------------------
# score_passphrase
# ---------------------------------------------------------------------------


def test_score_passphrase_returns_int_in_range() -> None:
    """Any string yields an ``int`` in ``[0, 4]``."""
    score = score_passphrase("a sample passphrase to score")
    assert isinstance(score, int)
    assert 0 <= score <= 4


def test_score_passphrase_distinguishes_weak_from_strong() -> None:
    """A real rhymepass-shaped phrase scores higher than ``"password"``.

    This is the only behavioural check that justifies pulling in
    zxcvbn at all: the trivial dictionary word ``"password"`` should
    score 0, while a long rhyming couplet of the kind rhymepass
    actually emits should land near the top.
    """
    weak = score_passphrase("password")
    strong = score_passphrase("The underground parade / an undelivered accolade / 38")
    assert weak < strong
    # Tighten the bound to catch regressions in the zxcvbn pin.
    assert weak == 0
    assert strong == 4


def test_score_passphrase_treats_spaced_and_unspaced_distinctly() -> None:
    """The function accepts both display forms; both must yield valid scores.

    The picker caches scores for ``passphrase`` and
    ``passphrase.replace(" ", "")`` so the indicator can update when
    the user toggles spaces on or off. This test simply documents
    that both calls succeed and return ints in range; whether they
    produce the *same* number is up to zxcvbn.
    """
    spaced = "The short couplet / a brief retort / 42"
    unspaced = spaced.replace(" ", "")
    spaced_score = score_passphrase(spaced)
    unspaced_score = score_passphrase(unspaced)
    assert isinstance(spaced_score, int)
    assert isinstance(unspaced_score, int)
    assert 0 <= spaced_score <= 4
    assert 0 <= unspaced_score <= 4
