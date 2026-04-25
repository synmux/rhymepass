"""Tests for the shared batch-generation helper.

`generate_batch` is the small dispatch on `random_mode` shared between
the CLI's pipe path and the picker's regeneration worker. The tests
here cover both branches plus the input-validation guard the rhyme
branch needs (since `pool`/`real_words` are optional in the random
branch).
"""

from __future__ import annotations

import pytest

from rhymepass.batch import generate_batch
from rhymepass.randomgen import (
    ALL_SYMBOLS,
    DEFAULT_RANDOM_LEN,
    DIGITS,
    LOWERCASE,
    SAFE_SYMBOLS,
    UPPERCASE,
    resolve_classes,
)


class TestRandomMode:
    """Random-mode dispatch produces fixed-length passwords."""

    def test_count_is_respected(self) -> None:
        result = generate_batch(
            7,
            None,
            None,
            random_mode=True,
            limit=12,
            classes=(UPPERCASE, LOWERCASE, DIGITS, SAFE_SYMBOLS),
        )
        assert len(result) == 7

    def test_each_passphrase_matches_limit(self) -> None:
        for _ in range(5):
            result = generate_batch(
                3,
                None,
                None,
                random_mode=True,
                limit=16,
                classes=(UPPERCASE, LOWERCASE, DIGITS, SAFE_SYMBOLS),
            )
            assert all(len(phrase) == 16 for phrase in result)

    def test_zero_limit_uses_default_length(self) -> None:
        result = generate_batch(
            2,
            None,
            None,
            random_mode=True,
            limit=0,
            classes=(UPPERCASE, LOWERCASE, DIGITS, SAFE_SYMBOLS),
        )
        assert all(len(phrase) == DEFAULT_RANDOM_LEN for phrase in result)

    def test_pool_can_be_none_in_random_mode(self) -> None:
        # Random mode must not need the anchor pool. Calling with
        # explicit `None` arguments confirms the function does not
        # touch them.
        result = generate_batch(
            3,
            None,
            None,
            random_mode=True,
            limit=8,
            classes=(UPPERCASE, DIGITS),
        )
        assert len(result) == 3
        for phrase in result:
            assert len(phrase) == 8
            assert all(c in UPPERCASE + DIGITS for c in phrase)

    def test_default_classes_when_none_supplied(self) -> None:
        # When `classes=None` the default four-class alphabet is used,
        # mirroring `generate_random`'s default.
        result = generate_batch(
            5,
            None,
            None,
            random_mode=True,
            limit=24,
            classes=None,
        )
        for phrase in result:
            assert any(c in LOWERCASE for c in phrase)
            assert any(c in UPPERCASE for c in phrase)
            assert any(c in DIGITS for c in phrase)
            assert any(c in SAFE_SYMBOLS for c in phrase)

    def test_resolved_charset_with_all_symbols(self) -> None:
        # The `all` class enables the unsafe punctuation set. Verify
        # the dispatch passes through `resolve_classes` correctly.
        classes = resolve_classes({"upper", "lower", "digits", "all"})
        for _ in range(5):
            result = generate_batch(
                2,
                None,
                None,
                random_mode=True,
                limit=24,
                classes=classes,
            )
            for phrase in result:
                # At least one ALL_SYMBOLS char must appear (the
                # one-of-each guarantee surfaces here).
                assert any(c in ALL_SYMBOLS for c in phrase)

    def test_invalid_length_raises_value_error(self) -> None:
        # Limit below the per-class minimum is the random generator's
        # ValueError path; `generate_batch` re-raises it unchanged.
        with pytest.raises(ValueError, match="at least"):
            generate_batch(
                1,
                None,
                None,
                random_mode=True,
                limit=2,
                classes=(UPPERCASE, LOWERCASE, DIGITS),
            )


class TestRhymeMode:
    """Rhyme-mode dispatch needs the anchor pool."""

    def test_count_and_shape(
        self, anchor_pool: list[str], real_words: set[str]
    ) -> None:
        result = generate_batch(
            4,
            anchor_pool,
            real_words,
            random_mode=False,
            limit=0,
        )
        assert len(result) == 4
        # Each entry must contain the suffix and at least one slash.
        for phrase in result:
            assert "/" in phrase
            assert phrase[-2:].isdigit() or phrase.endswith(("0", "1"))

    def test_limit_is_respected(
        self, anchor_pool: list[str], real_words: set[str]
    ) -> None:
        result = generate_batch(
            5,
            anchor_pool,
            real_words,
            random_mode=False,
            limit=24,
        )
        for phrase in result:
            assert len(phrase) <= 24

    def test_pool_required_for_rhyme(self) -> None:
        with pytest.raises(ValueError, match="pool.*real_words"):
            generate_batch(
                1,
                None,
                None,
                random_mode=False,
                limit=0,
            )

    def test_real_words_required_for_rhyme(self, anchor_pool: list[str]) -> None:
        with pytest.raises(ValueError, match="pool.*real_words"):
            generate_batch(
                1,
                anchor_pool,
                None,
                random_mode=False,
                limit=0,
            )

    def test_classes_argument_is_ignored_in_rhyme_mode(
        self, anchor_pool: list[str], real_words: set[str]
    ) -> None:
        # Passing classes in rhyme mode should not error - it is
        # silently ignored. The picker's worker always passes the
        # resolved tuple regardless of mode for shape stability.
        result = generate_batch(
            2,
            anchor_pool,
            real_words,
            random_mode=False,
            limit=0,
            classes=(UPPERCASE, DIGITS),
        )
        assert len(result) == 2
        # Confirm rhyming output, not random: contains a slash.
        for phrase in result:
            assert "/" in phrase
