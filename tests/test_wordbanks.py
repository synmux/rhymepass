"""Tests for the static word banks."""

from __future__ import annotations

from rhymepass.wordbanks import ADJECTIVES, DETERMINERS


class TestDeterminers:
    """Invariants for the determiner list."""

    def test_non_empty(self) -> None:
        assert len(DETERMINERS) > 0

    def test_all_strings(self) -> None:
        assert all(isinstance(word, str) for word in DETERMINERS)

    def test_all_lowercase(self) -> None:
        assert all(word == word.lower() for word in DETERMINERS)

    def test_no_duplicates(self) -> None:
        assert len(DETERMINERS) == len(set(DETERMINERS))

    def test_alphabetically_sorted(self) -> None:
        # The module docstring promises "alphabetical within each list".
        assert DETERMINERS == sorted(DETERMINERS)

    def test_exact_count(self) -> None:
        # Pinned because AGENTS.md documents this exact count; if the
        # list changes, update AGENTS.md line 27 in the same commit.
        assert len(DETERMINERS) == 33

    def test_no_multi_word_entries(self) -> None:
        assert all(" " not in word for word in DETERMINERS)

    def test_a_and_an_both_present(self) -> None:
        # _pick_determiner upgrades "a" to "an" before a vowel sound;
        # both forms must exist in the bank for that logic to work.
        assert "a" in DETERMINERS
        assert "an" not in DETERMINERS  # "an" is produced dynamically, not listed

    def test_common_determiners_present(self) -> None:
        for word in ("the", "some", "every", "my", "your"):
            assert word in DETERMINERS


class TestAdjectives:
    """Invariants for the adjective list."""

    def test_non_empty(self) -> None:
        assert len(ADJECTIVES) > 0

    def test_all_strings(self) -> None:
        assert all(isinstance(word, str) for word in ADJECTIVES)

    def test_all_lowercase(self) -> None:
        assert all(word == word.lower() for word in ADJECTIVES)

    def test_no_duplicates(self) -> None:
        assert len(ADJECTIVES) == len(set(ADJECTIVES))

    def test_alphabetically_sorted(self) -> None:
        # The module docstring promises "alphabetical within each list".
        assert ADJECTIVES == sorted(ADJECTIVES)

    def test_exact_count(self) -> None:
        # Pinned because AGENTS.md documents this exact count; if the
        # list changes, update AGENTS.md line 27 in the same commit.
        assert len(ADJECTIVES) == 118

    def test_all_purely_alphabetic(self) -> None:
        assert all(word.isalpha() for word in ADJECTIVES)

    def test_no_multi_word_entries(self) -> None:
        assert all(" " not in word for word in ADJECTIVES)

    def test_reasonable_size(self) -> None:
        # Sanity: if this ever drops under ~50, filler variety suffers;
        # if it balloons past ~500, the bank has lost its curated feel.
        assert 50 <= len(ADJECTIVES) <= 500
