"""Tests for phrase-construction helpers."""

from __future__ import annotations

import pytest

from rhymepass import phrases
from rhymepass.wordbanks import ADJECTIVES, DETERMINERS


class TestStartsWithVowelSound:
    """Phoneme-based initial-sound detection."""

    def test_empty_string(self) -> None:
        assert phrases._starts_with_vowel_sound("") is False

    def test_obvious_vowel(self) -> None:
        assert phrases._starts_with_vowel_sound("apple") is True

    def test_obvious_consonant(self) -> None:
        assert phrases._starts_with_vowel_sound("tree") is False

    def test_silent_h_counts_as_vowel(self) -> None:
        # "hour" begins with a vowel sound despite starting with h.
        assert phrases._starts_with_vowel_sound("hour") is True

    def test_union_not_a_vowel_sound(self) -> None:
        # "union" starts with a y-glide, which CMU marks as a consonant.
        assert phrases._starts_with_vowel_sound("union") is False

    def test_unknown_word_falls_back_to_letter(self) -> None:
        assert phrases._starts_with_vowel_sound("xxnotawordxx") is False
        assert phrases._starts_with_vowel_sound("uuunottaworduu") is True


class TestPickDeterminer:
    """Determiner selection with the a/an upgrade."""

    def test_returns_value_from_bank(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(phrases.secrets, "choice", lambda seq: seq[0])
        assert phrases._pick_determiner("zebra") in set(DETERMINERS) | {"an"}

    def test_upgrades_a_to_an_before_vowel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(phrases.secrets, "choice", lambda _seq: "a")
        assert phrases._pick_determiner("apple") == "an"

    def test_leaves_a_alone_before_consonant(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(phrases.secrets, "choice", lambda _seq: "a")
        assert phrases._pick_determiner("tree") == "a"

    def test_never_upgrades_other_determiners(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(phrases.secrets, "choice", lambda _seq: "the")
        assert phrases._pick_determiner("apple") == "the"


class TestBuildPhrase:
    """Phrase assembly with 0, 1, or 2 fillers."""

    def test_zero_fillers_returns_bare_anchor(self) -> None:
        assert phrases._build_phrase("accolade", 0) == "accolade"

    def test_one_filler_determiner_branch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(phrases.secrets, "randbelow", lambda _n: 0)
        monkeypatch.setattr(phrases.secrets, "choice", lambda _seq: "the")
        result = phrases._build_phrase("parade", 1)
        assert result == "the parade"

    def test_one_filler_adjective_branch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(phrases.secrets, "randbelow", lambda _n: 1)
        monkeypatch.setattr(phrases.secrets, "choice", lambda _seq: "zesty")
        result = phrases._build_phrase("parade", 1)
        assert result == "zesty parade"

    def test_two_fillers_produces_three_words(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # First call picks an adjective, second call picks a determiner.
        calls: list[list[str]] = []

        def fake_choice(seq: list[str]) -> str:
            calls.append(seq)
            return seq[0]

        monkeypatch.setattr(phrases.secrets, "choice", fake_choice)
        result = phrases._build_phrase("parade", 2)
        words = result.split()
        assert len(words) == 3
        # The determiner is DETERMINERS[0] ("a") upgraded to "an" because
        # ADJECTIVES[0] ("abundant") starts with a vowel sound. This
        # confirms the determiner agrees with the adjective that follows
        # it, not with the anchor.
        assert words[0] == "an"
        assert words[1] == ADJECTIVES[0]
        assert words[2] == "parade"
        # First choice should be from ADJECTIVES, second from DETERMINERS.
        assert calls[0] is ADJECTIVES
        assert calls[1] is DETERMINERS


class TestCapitalise:
    """First-character capitalisation preserving the rest."""

    def test_empty_returns_empty(self) -> None:
        assert phrases._capitalise("") == ""

    def test_lowercases_unchanged(self) -> None:
        assert phrases._capitalise("hello world") == "Hello world"

    def test_preserves_inner_case(self) -> None:
        assert phrases._capitalise("hELLO") == "HELLO"

    def test_already_capital_unchanged(self) -> None:
        assert phrases._capitalise("Hello") == "Hello"

    def test_single_character(self) -> None:
        assert phrases._capitalise("a") == "A"


class TestCoupletFillerSplits:
    """Legal filler-budget splits for the couplet descent."""

    def test_total_zero(self) -> None:
        assert phrases._couplet_filler_splits(0) == [(0, 0)]

    def test_total_one(self) -> None:
        assert phrases._couplet_filler_splits(1) == [(0, 1), (1, 0)]

    def test_total_two(self) -> None:
        assert phrases._couplet_filler_splits(2) == [(0, 2), (1, 1), (2, 0)]

    def test_total_three(self) -> None:
        assert phrases._couplet_filler_splits(3) == [(1, 2), (2, 1)]

    def test_total_four(self) -> None:
        assert phrases._couplet_filler_splits(4) == [(2, 2)]

    def test_total_five_returns_empty(self) -> None:
        # No split with both components in 0..2 can sum to 5.
        assert phrases._couplet_filler_splits(5) == []

    def test_components_always_in_range(self) -> None:
        for total in range(-2, 7):
            for left, right in phrases._couplet_filler_splits(total):
                assert 0 <= left <= 2
                assert 0 <= right <= 2
                assert left + right == total
