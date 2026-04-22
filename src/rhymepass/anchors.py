"""Anchor-word selection.

An *anchor* is the content word at the heart of one half of a
passphrase. Good anchors are real English words with moderate
syllable counts, long enough to be readable but short enough that a
rhyming couplet still fits common character budgets.

This module provides:

* :func:`load_real_words` — loads a filtered view of the GCIDE word
  list (GNU Collaborative International Dictionary of English) used
  to reject proper nouns, abbreviations, and obscurities;
* :func:`build_anchor_pool` — walks the CMU Pronouncing Dictionary
  and returns every word that survives the anchor-quality checks.

The private helpers :func:`_syllable_count` and
:func:`_is_good_anchor` are also exported for testing.
"""

from __future__ import annotations

import pronouncing
from english_words import get_english_words_set


def load_real_words() -> set[str]:
    """Return the set of lower-case GCIDE English words.

    Non-alphabetic entries (numbers, punctuation, hyphenated forms)
    are discarded. The result is intended as a membership filter for
    candidate anchor words drawn from the CMU Pronouncing Dictionary,
    which also contains proper nouns, abbreviations, and other
    non-word entries that are unsuitable for human-readable
    passphrases.

    Returns:
        A set of real English words, all lower-case, all purely
        alphabetic.
    """
    return {
        word.lower()
        for word in get_english_words_set(["gcide_alpha_lower"])
        if word.isalpha()
    }


def _syllable_count(word: str) -> int:
    """Return the estimated syllable count of ``word``.

    Consults the CMU Pronouncing Dictionary via
    :func:`pronouncing.phones_for_word`, returning the syllable
    count of the first listed pronunciation. Words absent from the
    dictionary return ``0``, which
    :func:`_is_good_anchor` treats as disqualifying.

    Args:
        word: The word to inspect, in any case.

    Returns:
        The syllable count of the first pronunciation, or ``0`` if
        the word is not in the dictionary.
    """
    phones = pronouncing.phones_for_word(word)
    return pronouncing.syllable_count(phones[0]) if phones else 0


def _is_good_anchor(word: str, real_words: set[str]) -> bool:
    """Return ``True`` if ``word`` meets every anchor-quality rule.

    Rules:

    1. It appears in ``real_words`` (rejects proper nouns,
       abbreviations, and CMU oddities).
    2. It is at least four characters long (mirrors ``MIN_ANCHOR_LEN``
       in :mod:`rhymepass.generator`; shorter words produce
       awkward phrases and rhyme poorly).
    3. Its syllable count is between 2 and 5 inclusive. One-syllable
       words crowd the output; six-plus-syllable words dominate it.

    Args:
        word: The candidate word.
        real_words: The filter produced by :func:`load_real_words`.

    Returns:
        ``True`` if every rule passes, ``False`` if any rule fails.
    """
    if word not in real_words:
        return False
    if len(word) < 4:
        return False
    syllables = _syllable_count(word)
    return 2 <= syllables <= 5


def build_anchor_pool(real_words: set[str]) -> list[str]:
    """Return every CMU word that passes :func:`_is_good_anchor`.

    The returned list is de-duplicated and stable across calls for
    the same ``real_words`` input, so downstream randomness (via
    :mod:`secrets`) is the only source of variation between
    generator runs.

    Args:
        real_words: The word-set filter from :func:`load_real_words`.

    Returns:
        A list of unique lower-case anchor candidates. Typically in
        the 20k–25k range with the shipped ``gcide_alpha_lower``
        word set.
    """
    seen: set[str] = set()
    pool: list[str] = []
    for word in pronouncing.search("."):
        lower = word.lower()
        if lower not in seen and _is_good_anchor(lower, real_words):
            seen.add(lower)
            pool.append(lower)
    return pool
