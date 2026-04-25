"""Tests for the interactive Textual UI, driven by its pilot harness.

Most of these tests do not actually need the real anchor pool.
Regeneration is triggered but the worker can run against a tiny pool
for speed. We still request the session-scoped ``real_words`` fixture
because :func:`rhymepass.generator.generate` needs it to validate
rhyme candidates.
"""

from __future__ import annotations

from rhymepass.strength import format_strength
from rhymepass.ui import LimitModal, PassphraseApp


def _seed_batch() -> list[str]:
    """Three pre-baked passphrases that exercise both shapes."""
    return [
        "The underground parade / an undelivered accolade / 38",
        "Cubed / 12",
        "Wild chime / any mime / 77",
    ]


class TestPassphraseAppDefaults:
    """Initial reactive state of the picker."""

    async def test_spaces_on_by_default(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.spaces_on is True

    async def test_limit_zero_by_default(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.limit == 0

    async def test_list_populated_with_seeded_batch(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            option_list = app.query_one("#passphrase-list")
            assert option_list.option_count == 3


class TestPassphraseAppKeys:
    """Key-binding behaviour."""

    async def test_x_toggles_spaces(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.spaces_on is True
            await pilot.press("x")
            await pilot.pause()
            assert app.spaces_on is False
            await pilot.press("x")
            await pilot.pause()
            assert app.spaces_on is True

    async def test_l_opens_limit_modal(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("l")
            await pilot.pause()
            # The modal should now be the topmost screen.
            assert isinstance(app.screen, LimitModal)

    async def test_escape_exits_without_result(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert app.return_value is None

    async def test_q_exits_without_result(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
        assert app.return_value is None


class TestLimitModalValidation:
    """The limit modal's integer-range validation."""

    async def test_zero_accepted(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("l")
            await pilot.pause()
            assert isinstance(app.screen, LimitModal)
            # The input is pre-filled with "0" and selected; submitting
            # should close the modal.
            await pilot.press("enter")
            await pilot.pause()
            assert not isinstance(app.screen, LimitModal)

    async def test_below_minimum_rejected(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("l")
            await pilot.pause()
            # Replace the default 0 with 5 (below MIN_SINGLE_LEN=9).
            await pilot.press("5")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            # Modal should remain open because 5 was rejected.
            assert isinstance(app.screen, LimitModal)

    async def test_escape_cancels_modal(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("l")
            await pilot.pause()
            assert isinstance(app.screen, LimitModal)
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, LimitModal)


class TestStrengthIndicator:
    """The zxcvbn-backed strength indicator that follows each row.

    These tests focus on three guarantees:

    1. Each seeded passphrase gets a ``(spaced, unspaced)`` score
       cached up front so the toggle does not call zxcvbn on the UI
       thread.
    2. Every rendered row contains the ``format_strength`` output for
       the score that matches the current display form.
    3. Pressing ``x`` flips the lookup index so the indicator updates
       to reflect the form the user would actually copy.
    """

    async def test_seed_scores_have_two_in_range_ints_per_row(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """Each seeded passphrase yields a (spaced, unspaced) score pair."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert len(app._scores) == 3
            for spaced, unspaced in app._scores:
                assert isinstance(spaced, int)
                assert isinstance(unspaced, int)
                assert 0 <= spaced <= 4
                assert 0 <= unspaced <= 4

    async def test_rows_contain_indicator_for_current_display_form(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """Each rendered row ends with the strength indicator."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            option_list = app.query_one("#passphrase-list")
            for index, (spaced_score, _) in enumerate(app._scores):
                row_text = str(option_list.get_option_at_index(index).prompt)
                assert format_strength(spaced_score) in row_text

    async def test_toggle_swaps_indicator_lookup(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """Pressing ``x`` flips the score-pair index used for rendering.

        The test plants a deterministic divergence between spaced and
        unspaced scores so we can assert the row text changes when
        ``self.spaces_on`` flips, even if zxcvbn happens to score the
        two display forms identically for a given passphrase.
        """
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # Force distinguishable scores per form so we can spot the
            # toggle from outside without depending on zxcvbn's exact
            # behaviour for these particular phrases.
            app._scores = [(0, 4), (1, 3), (2, 2)]
            app._refresh_list()
            await pilot.pause()
            option_list = app.query_one("#passphrase-list")

            # spaces_on=True -> lookup index 0 (the spaced score).
            assert format_strength(0) in str(option_list.get_option_at_index(0).prompt)
            assert format_strength(1) in str(option_list.get_option_at_index(1).prompt)

            await pilot.press("x")
            await pilot.pause()

            # spaces_on=False -> lookup index 1 (the unspaced score).
            assert format_strength(4) in str(option_list.get_option_at_index(0).prompt)
            assert format_strength(3) in str(option_list.get_option_at_index(1).prompt)
