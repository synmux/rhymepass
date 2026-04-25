"""Tests for the random-password generator.

These tests cover :func:`rhymepass.randomgen.generate_random` and the
module-level constants. They use real :mod:`secrets` calls (no
monkeypatching); 50 iterations per shape test gives strong
probabilistic coverage of the per-class guarantees without slowing
the suite noticeably.
"""

from __future__ import annotations

import re

import pytest

from rhymepass.randomgen import (
    DEFAULT_RANDOM_LEN,
    DIGITS,
    LOWERCASE,
    MIN_RANDOM_LEN,
    SAFE_SYMBOLS,
    UPPERCASE,
    generate_random,
)

_ALPHABET: str = LOWERCASE + UPPERCASE + DIGITS + SAFE_SYMBOLS

# Characters the user explicitly called out as unsafe (shell or HTTP
# special meaning). The list mirrors the AGENTS.md / plan rationale.
_UNSAFE_CHARS: tuple[str, ...] = (
    "!",
    '"',
    "'",
    "\\",
    "`",
    "$",
    "*",
    "?",
    ";",
    "&",
    "|",
    "<",
    ">",
    "(",
    ")",
    "{",
    "}",
    "[",
    "]",
    "#",
    "%",
    "=",
    "+",
    "/",
    "~",
    " ",
)


class TestRandomShape:
    """Structural invariants for any output of :func:`generate_random`."""

    def test_only_alphabet_chars(self) -> None:
        for _ in range(50):
            password = generate_random()
            for char in password:
                assert char in _ALPHABET, f"unexpected char {char!r} in {password!r}"

    def test_no_whitespace(self) -> None:
        for _ in range(50):
            password = generate_random()
            assert not re.search(r"\s", password), f"whitespace in {password!r}"

    def test_contains_lowercase(self) -> None:
        for _ in range(50):
            password = generate_random()
            assert any(
                c in LOWERCASE for c in password
            ), f"no lowercase in {password!r}"

    def test_contains_uppercase(self) -> None:
        for _ in range(50):
            password = generate_random()
            assert any(
                c in UPPERCASE for c in password
            ), f"no uppercase in {password!r}"

    def test_contains_digit(self) -> None:
        for _ in range(50):
            password = generate_random()
            assert any(c in DIGITS for c in password), f"no digit in {password!r}"

    def test_contains_symbol(self) -> None:
        for _ in range(50):
            password = generate_random()
            assert any(
                c in SAFE_SYMBOLS for c in password
            ), f"no symbol in {password!r}"


class TestRandomLength:
    """Length is exact, not a bound."""

    @pytest.mark.parametrize("length", [MIN_RANDOM_LEN, 8, 16, DEFAULT_RANDOM_LEN, 64])
    def test_exact_length(self, length: int) -> None:
        for _ in range(10):
            assert len(generate_random(length=length)) == length

    def test_default_length(self) -> None:
        assert len(generate_random()) == DEFAULT_RANDOM_LEN

    def test_minimum_length_still_has_one_of_each(self) -> None:
        # At length == MIN_RANDOM_LEN every class appears exactly once.
        for _ in range(50):
            password = generate_random(length=MIN_RANDOM_LEN)
            assert len(password) == MIN_RANDOM_LEN
            assert any(c in LOWERCASE for c in password)
            assert any(c in UPPERCASE for c in password)
            assert any(c in DIGITS for c in password)
            assert any(c in SAFE_SYMBOLS for c in password)


class TestRandomErrors:
    """Boundary conditions raise rather than fail silently."""

    def test_below_minimum_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match=f"at least {MIN_RANDOM_LEN}"):
            generate_random(length=MIN_RANDOM_LEN - 1)

    def test_zero_length_raises(self) -> None:
        with pytest.raises(ValueError):
            generate_random(length=0)

    def test_negative_length_raises(self) -> None:
        with pytest.raises(ValueError):
            generate_random(length=-1)


class TestSafeSymbolsContent:
    """The published :data:`SAFE_SYMBOLS` set matches the design."""

    def test_includes_user_examples(self) -> None:
        # `@` and `§` were called out in the original spec as safe.
        assert "@" in SAFE_SYMBOLS
        assert "§" in SAFE_SYMBOLS

    def test_excludes_all_unsafe_characters(self) -> None:
        for char in _UNSAFE_CHARS:
            assert (
                char not in SAFE_SYMBOLS
            ), f"{char!r} should not be in SAFE_SYMBOLS - it has shell or HTTP meaning"

    def test_no_whitespace_in_symbols(self) -> None:
        assert not re.search(r"\s", SAFE_SYMBOLS)

    def test_no_letters_or_digits_in_symbols(self) -> None:
        # Letters / digits already live in their own class; symbols
        # must be disjoint to keep the alphabet free of duplicates.
        for char in SAFE_SYMBOLS:
            assert char not in LOWERCASE
            assert char not in UPPERCASE
            assert char not in DIGITS

    def test_symbols_are_unique(self) -> None:
        assert len(SAFE_SYMBOLS) == len(set(SAFE_SYMBOLS))


class TestRandomConstants:
    """Sanity for the public module-level constants."""

    def test_min_random_len_is_four(self) -> None:
        assert MIN_RANDOM_LEN == 4

    def test_default_random_len_is_safe(self) -> None:
        # The plan calls 24 the recommended default; keep the test
        # tied to the published constant rather than hard-coding 24
        # so both stay in sync if the policy is revisited.
        assert DEFAULT_RANDOM_LEN >= 16

    def test_alphabet_classes_are_disjoint(self) -> None:
        seen: set[str] = set()
        for cls in (LOWERCASE, UPPERCASE, DIGITS, SAFE_SYMBOLS):
            for char in cls:
                assert char not in seen, f"{char!r} appears in multiple classes"
                seen.add(char)
