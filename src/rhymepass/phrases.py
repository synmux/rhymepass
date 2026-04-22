"""Phrase-construction helpers used by :mod:`rhymepass.generator`.

Each passphrase half is built by wrapping an anchor word in zero, one,
or two filler words drawn from :mod:`rhymepass.wordbanks`. The helpers
here handle the grammatical details:

* picking a determiner that matches the phonetics of the word that
  follows it (``a`` becomes ``an`` before a vowel sound),
* deciding randomly between a determiner and an adjective when only
  one filler is asked for,
* producing every legal ``(fillers_a, fillers_b)`` split for the
  couplet-descent loop inside :func:`rhymepass.generator.generate`.

All randomness routes through :mod:`secrets` rather than
:mod:`random`, because the generated strings are used as passphrases
and must resist prediction.
"""

from __future__ import annotations

import secrets

import pronouncing

from rhymepass.wordbanks import ADJECTIVES, DETERMINERS


def _starts_with_vowel_sound(word: str) -> bool:
    """Return ``True`` if *word* begins with a vowel sound.

    Uses the first phoneme reported by CMU when available, falling
    back to a first-letter vowel check when the word is not in the
    dictionary. The phoneme check correctly handles words like
    ``"hour"`` (starts with a vowel sound despite starting with ``h``)
    and ``"union"`` (starts with a consonant sound despite starting
    with ``u``).

    Args:
        word: The word whose leading sound should be inspected.

    Returns:
        ``True`` if the initial sound is a vowel, ``False`` otherwise.
        Always returns ``False`` for the empty string.
    """
    if not word:
        return False
    phones = pronouncing.phones_for_word(word)
    if phones:
        first_phoneme = phones[0].split()[0]
        return first_phoneme[0] in "AEIOU"
    return word[0].lower() in "aeiou"


def _pick_determiner(next_word: str) -> str:
    """Return a determiner that agrees phonetically with ``next_word``.

    Chooses uniformly from :data:`rhymepass.wordbanks.DETERMINERS` and
    upgrades ``"a"`` to ``"an"`` when ``next_word`` begins with a
    vowel sound. No other determiner is adjusted.

    Args:
        next_word: The word that will immediately follow the
            determiner in the generated phrase.

    Returns:
        A determiner that reads naturally before ``next_word``.
    """
    det = secrets.choice(DETERMINERS)
    if det == "a" and _starts_with_vowel_sound(next_word):
        det = "an"
    return det


def _build_phrase(anchor: str, num_fillers: int) -> str:
    """Assemble a phrase around ``anchor`` with 0, 1, or 2 filler words.

    Filler shapes:

    * ``0``: bare ``anchor`` (``"accolade"``).
    * ``1``: determiner + anchor (``"the accolade"``) or
      adjective + anchor (``"magnificent accolade"``), chosen 50/50.
    * ``2``: determiner + adjective + anchor
      (``"the magnificent accolade"``). The determiner agrees with
      the adjective, not the anchor, because the adjective is the
      word the determiner immediately precedes.

    Args:
        anchor: The content word the phrase is built around.
        num_fillers: How many filler words to prepend (0, 1, or 2).
            Values outside this range are not validated; 3 or more
            fall through to the two-filler branch.

    Returns:
        The assembled phrase, lower-case, words separated by single
        spaces.
    """
    if num_fillers == 0:
        return anchor
    if num_fillers == 1:
        # 50/50 determiner vs adjective.
        if secrets.randbelow(2) == 0:
            return f"{_pick_determiner(anchor)} {anchor}"
        return f"{secrets.choice(ADJECTIVES)} {anchor}"
    # 2 fillers: determiner + adjective + anchor.
    adjective = secrets.choice(ADJECTIVES)
    determiner = _pick_determiner(adjective)
    return f"{determiner} {adjective} {anchor}"


def _capitalise(phrase: str) -> str:
    """Upper-case the first character of ``phrase`` only.

    Unlike :meth:`str.capitalize`, this preserves the case of every
    character after the first, which matters when the rest of the
    phrase already contains an intentionally upper-case letter.

    Args:
        phrase: The phrase whose first character should be upper-cased.

    Returns:
        The phrase with its leading character upper-cased, or the
        input unchanged if it is empty.
    """
    return phrase[0].upper() + phrase[1:] if phrase else phrase


def _couplet_filler_splits(total: int) -> list[tuple[int, int]]:
    """Return every legal ``(fillers_a, fillers_b)`` split for *total*.

    :func:`_build_phrase` only supports 0–2 fillers per half, so each
    component of every returned pair lies in ``0..2``.

    The order is fixed (ascending ``fillers_a``) so the couplet
    descent inside :func:`rhymepass.generator.generate` is
    deterministic for a given total: balanced splits are tried before
    heavily-skewed ones, and the same sequence is retried across
    anchor draws.

    Args:
        total: The combined filler budget to distribute across the
            two halves of the couplet.

    Returns:
        All pairs ``(fillers_a, fillers_b)`` with both components in
        ``0..2`` whose sum equals ``total``. May be empty when
        ``total`` is out of range (``total < 0`` or ``total > 4``).
    """
    return [(a, total - a) for a in range(0, 3) if 0 <= total - a <= 2]
