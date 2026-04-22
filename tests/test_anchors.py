"""Tests for anchor-word loading and filtering.

These tests exercise real CMU / GCIDE data through the session-scoped
``real_words`` and ``anchor_pool`` fixtures in ``conftest.py``.
"""

from __future__ import annotations

from rhymepass.anchors import _is_good_anchor, _syllable_count


class TestSyllableCount:
    """Integration tests against the real CMU Pronouncing Dictionary."""

    def test_monosyllable(self) -> None:
        assert _syllable_count("tree") == 1

    def test_disyllable(self) -> None:
        assert _syllable_count("hello") == 2

    def test_trisyllable(self) -> None:
        assert _syllable_count("computer") == 3

    def test_unknown_word_returns_zero(self) -> None:
        assert _syllable_count("xxnotaword") == 0

    def test_case_insensitive(self) -> None:
        # pronouncing's CMU lookup normalises case internally.
        assert _syllable_count("Hello") == _syllable_count("hello")


class TestIsGoodAnchor:
    """Composite anchor-quality check."""

    def test_short_word_rejected(self, real_words: set[str]) -> None:
        assert _is_good_anchor("the", real_words) is False

    def test_non_word_rejected(self, real_words: set[str]) -> None:
        assert _is_good_anchor("xxnotawordxx", real_words) is False

    def test_typical_disyllable_accepted(self, real_words: set[str]) -> None:
        assert _is_good_anchor("parade", real_words) is True

    def test_typical_trisyllable_accepted(self, real_words: set[str]) -> None:
        assert _is_good_anchor("accolade", real_words) is True

    def test_six_syllable_word_rejected(self, real_words: set[str]) -> None:
        # "incomprehensibility" has far more than 5 syllables.
        assert _is_good_anchor("incomprehensibility", real_words) is False

    def test_monosyllable_rejected(self, real_words: set[str]) -> None:
        # "tree" is a real word but only 1 syllable.
        assert _is_good_anchor("tree", real_words) is False


class TestBuildAnchorPool:
    """The full anchor pool built from the real CMU / GCIDE data."""

    def test_non_empty(self, anchor_pool: list[str]) -> None:
        assert len(anchor_pool) > 100

    def test_no_duplicates(self, anchor_pool: list[str]) -> None:
        assert len(anchor_pool) == len(set(anchor_pool))

    def test_all_lowercase(self, anchor_pool: list[str]) -> None:
        assert all(word == word.lower() for word in anchor_pool)

    def test_all_in_real_words(
        self, anchor_pool: list[str], real_words: set[str]
    ) -> None:
        assert all(word in real_words for word in anchor_pool)

    def test_all_meet_length_minimum(self, anchor_pool: list[str]) -> None:
        assert all(len(word) >= 4 for word in anchor_pool)

    def test_expected_ballpark_size(self, anchor_pool: list[str]) -> None:
        # With GCIDE + CMU and the 4-char / 2-5-syllable filter the pool
        # settles around 20k-25k words on current data.
        assert 10_000 <= len(anchor_pool) <= 40_000
