"""Tests for the core passphrase generator.

These tests use the session-scoped ``anchor_pool`` fixture (full real
data) for most behaviour, and a tiny curated pool for edge cases that
need faster draws.
"""

from __future__ import annotations

import re

import pytest

from rhymepass.generator import (
    MIN_COUPLET_LEN,
    MIN_SINGLE_LEN,
    SUFFIX_LEN,
    generate,
)

COUPLET_PATTERN = re.compile(r"^[A-Z][^/]* / [a-z][^/]* / \d{2}$")
SINGLE_PATTERN = re.compile(r"^[A-Z][^/]* / \d{2}$")


def _matches_any_shape(phrase: str) -> bool:
    return bool(COUPLET_PATTERN.match(phrase) or SINGLE_PATTERN.match(phrase))


class TestGeneratorShape:
    """Structural invariants for any generated passphrase."""

    def test_matches_one_of_the_two_shapes(
        self, anchor_pool: list[str], real_words: set[str]
    ) -> None:
        for _ in range(20):
            phrase = generate(anchor_pool, real_words)
            assert _matches_any_shape(phrase), f"unexpected shape: {phrase!r}"

    def test_suffix_is_two_digits(
        self, anchor_pool: list[str], real_words: set[str]
    ) -> None:
        for _ in range(20):
            phrase = generate(anchor_pool, real_words)
            assert re.search(r" / \d{2}$", phrase), f"bad suffix: {phrase!r}"

    def test_unlimited_always_couplet(
        self, anchor_pool: list[str], real_words: set[str]
    ) -> None:
        # With limit=0, the single-statement fallback must never fire —
        # unlimited generation redraws until a rhyme is found.
        for _ in range(20):
            phrase = generate(anchor_pool, real_words)
            assert phrase.count(" / ") == 2, (
                f"unlimited generation produced a single-statement phrase: {phrase!r}"
            )

    def test_first_letter_uppercase(
        self, anchor_pool: list[str], real_words: set[str]
    ) -> None:
        for _ in range(10):
            phrase = generate(anchor_pool, real_words)
            assert phrase[0].isupper()


class TestGeneratorLimits:
    """Character-limit enforcement."""

    def test_respects_tight_limit(
        self, anchor_pool: list[str], real_words: set[str]
    ) -> None:
        # A 24-char budget should always be achievable.
        for _ in range(5):
            phrase = generate(anchor_pool, real_words, limit=24)
            assert len(phrase) <= 24

    def test_minimum_single_limit_succeeds(
        self, anchor_pool: list[str], real_words: set[str]
    ) -> None:
        phrase = generate(anchor_pool, real_words, limit=MIN_SINGLE_LEN)
        assert len(phrase) <= MIN_SINGLE_LEN

    def test_minimum_couplet_limit_succeeds(
        self, anchor_pool: list[str], real_words: set[str]
    ) -> None:
        phrase = generate(anchor_pool, real_words, limit=MIN_COUPLET_LEN)
        assert len(phrase) <= MIN_COUPLET_LEN

    def test_below_single_minimum_raises(
        self, anchor_pool: list[str], real_words: set[str]
    ) -> None:
        # 8 < MIN_SINGLE_LEN (9); no passphrase shorter than "Abcd / 12" exists.
        with pytest.raises(RuntimeError):
            generate(anchor_pool, real_words, limit=8, max_attempts=5)

    def test_suffix_always_included(
        self, anchor_pool: list[str], real_words: set[str]
    ) -> None:
        # Even under the tightest limits, the two-digit suffix stays.
        for limit in (MIN_SINGLE_LEN, MIN_COUPLET_LEN, 20, 50):
            phrase = generate(anchor_pool, real_words, limit=limit)
            assert re.search(r" / \d{2}$", phrase)
            assert len(phrase) >= SUFFIX_LEN + 1  # at minimum "X / NN"


class TestGeneratorErrors:
    """Error-path behaviour."""

    def test_empty_pool_raises_value_error(self, real_words: set[str]) -> None:
        with pytest.raises(ValueError, match="Anchor pool is empty"):
            generate([], real_words)

    def test_tiny_pool_still_works(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        # parade/accolade/rhyme/crime/chime all have good CMU rhymes,
        # so even a five-word pool should be generatable from.
        phrase = generate(tiny_pool, real_words)
        assert _matches_any_shape(phrase)


class TestSuffixConstants:
    """Sanity for the shape constants exposed by the generator module."""

    def test_suffix_len(self) -> None:
        assert SUFFIX_LEN == len(" / 12")

    def test_min_single_len(self) -> None:
        assert MIN_SINGLE_LEN == 9

    def test_min_couplet_len(self) -> None:
        assert MIN_COUPLET_LEN == 16
