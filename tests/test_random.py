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
    ALL_SYMBOLS,
    CLASS_NAMES,
    DEFAULT_CHARSET,
    DEFAULT_RANDOM_LEN,
    DIGITS,
    LOWERCASE,
    MIN_RANDOM_LEN,
    SAFE_SYMBOLS,
    UNSAFE_SYMBOLS,
    UPPERCASE,
    generate_random,
    resolve_classes,
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


class TestSymbolUnion:
    """The :data:`ALL_SYMBOLS` / :data:`UNSAFE_SYMBOLS` relationship."""

    def test_unsafe_excludes_safe(self) -> None:
        for char in SAFE_SYMBOLS:
            assert (
                char not in UNSAFE_SYMBOLS
            ), f"{char!r} is in SAFE_SYMBOLS and must not also be in UNSAFE_SYMBOLS"

    def test_unsafe_contains_user_examples(self) -> None:
        # The user explicitly named these as unsafe in the original spec.
        for char in ("!", '"', "\\"):
            assert char in UNSAFE_SYMBOLS

    def test_all_is_safe_plus_unsafe(self) -> None:
        assert set(ALL_SYMBOLS) == set(SAFE_SYMBOLS) | set(UNSAFE_SYMBOLS)

    def test_all_has_no_duplicates(self) -> None:
        assert len(ALL_SYMBOLS) == len(set(ALL_SYMBOLS))

    def test_all_includes_safe(self) -> None:
        for char in SAFE_SYMBOLS:
            assert char in ALL_SYMBOLS


class TestCustomClasses:
    """`generate_random(classes=...)` honours an arbitrary class subset."""

    def test_default_classes_match_original_behaviour(self) -> None:
        # When `classes` is omitted, the function behaves as before:
        # one of each from (LOWERCASE, UPPERCASE, DIGITS, SAFE_SYMBOLS).
        for _ in range(20):
            password = generate_random()
            assert any(c in LOWERCASE for c in password)
            assert any(c in UPPERCASE for c in password)
            assert any(c in DIGITS for c in password)
            assert any(c in SAFE_SYMBOLS for c in password)

    def test_only_uppercase(self) -> None:
        for _ in range(20):
            password = generate_random(length=12, classes=(UPPERCASE,))
            assert len(password) == 12
            assert all(c in UPPERCASE for c in password)

    def test_two_classes_only_uppercase_and_digits(self) -> None:
        for _ in range(20):
            password = generate_random(length=10, classes=(UPPERCASE, DIGITS))
            assert all(c in UPPERCASE + DIGITS for c in password)
            assert any(c in UPPERCASE for c in password)
            assert any(c in DIGITS for c in password)
            # No characters from the unselected classes.
            assert not any(c in LOWERCASE for c in password)
            assert not any(c in SAFE_SYMBOLS for c in password)

    def test_all_symbols_class(self) -> None:
        # When ALL_SYMBOLS is passed, unsafe punctuation is allowed.
        for _ in range(50):
            password = generate_random(
                length=24,
                classes=(LOWERCASE, UPPERCASE, DIGITS, ALL_SYMBOLS),
            )
            # At least one ALL_SYMBOLS char must appear (one-of-each guarantee).
            assert any(c in ALL_SYMBOLS for c in password)

    def test_empty_classes_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one character class"):
            generate_random(length=10, classes=())

    def test_empty_class_string_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            generate_random(length=10, classes=(UPPERCASE, ""))

    def test_length_below_class_count_raises(self) -> None:
        # 4 classes need length >= 4; 3 need >= 3.
        with pytest.raises(ValueError, match="at least 3"):
            generate_random(length=2, classes=(UPPERCASE, LOWERCASE, DIGITS))

    def test_length_equal_to_class_count_works(self) -> None:
        # Exactly one of each class, no fillers.
        password = generate_random(length=2, classes=(UPPERCASE, LOWERCASE))
        assert len(password) == 2
        assert any(c in UPPERCASE for c in password)
        assert any(c in LOWERCASE for c in password)


class TestResolveClasses:
    """`resolve_classes` maps internal names to character-set strings."""

    def test_each_name_maps_to_expected_constant(self) -> None:
        assert resolve_classes({"upper"}) == (UPPERCASE,)
        assert resolve_classes({"lower"}) == (LOWERCASE,)
        assert resolve_classes({"digits"}) == (DIGITS,)
        assert resolve_classes({"safe"}) == (SAFE_SYMBOLS,)
        assert resolve_classes({"all"}) == (ALL_SYMBOLS,)

    def test_default_charset_resolves_to_default_alphabet(self) -> None:
        # The default charset should produce the same alphabet
        # `generate_random` uses by default (just in display order).
        result = resolve_classes(DEFAULT_CHARSET)
        assert set(result) == {UPPERCASE, LOWERCASE, DIGITS, SAFE_SYMBOLS}

    def test_display_order_is_stable(self) -> None:
        # Order is upper, lower, digits, then safe/all - independent of
        # the order names arrive in.
        for variant in (
            ["upper", "lower", "digits", "safe"],
            ["safe", "digits", "lower", "upper"],
            ["digits", "upper", "safe", "lower"],
        ):
            assert resolve_classes(variant) == (
                UPPERCASE,
                LOWERCASE,
                DIGITS,
                SAFE_SYMBOLS,
            )

    def test_all_replaces_safe_in_output(self) -> None:
        # When `all` is enabled the resolved tuple contains ALL_SYMBOLS
        # in place of SAFE_SYMBOLS - they are not stacked, even if both
        # names are present in the input. This mirrors the picker's
        # `_active_classes` behaviour.
        assert resolve_classes({"all"}) == (ALL_SYMBOLS,)
        assert resolve_classes({"safe", "all"}) == (ALL_SYMBOLS,)
        assert resolve_classes({"upper", "safe", "all"}) == (
            UPPERCASE,
            ALL_SYMBOLS,
        )

    def test_accepts_any_iterable(self) -> None:
        # frozenset, set, list, tuple all work.
        for container in (
            frozenset({"upper", "digits"}),
            {"upper", "digits"},
            ["upper", "digits"],
            ("upper", "digits"),
        ):
            assert resolve_classes(container) == (UPPERCASE, DIGITS)

    def test_empty_input_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one class name"):
            resolve_classes(set())
        with pytest.raises(ValueError, match="at least one class name"):
            resolve_classes([])
        with pytest.raises(ValueError, match="at least one class name"):
            resolve_classes(())

    def test_unknown_name_raises_with_listing(self) -> None:
        with pytest.raises(ValueError, match="unknown class name"):
            resolve_classes({"upper", "wat"})
        # Error must name the offender so the user can fix it.
        with pytest.raises(ValueError, match="wat"):
            resolve_classes({"wat"})
        # Error must mention the valid choices for discoverability.
        with pytest.raises(ValueError, match="upper"):
            resolve_classes({"nope"})

    def test_class_names_constant_matches_resolve(self) -> None:
        # Every valid name in `CLASS_NAMES` resolves without error.
        # Using the singleton form keeps each call producing a single-
        # element tuple so we can compare across the set.
        for name in CLASS_NAMES:
            assert len(resolve_classes({name})) == 1
