"""Tests for the interactive Textual UI, driven by its pilot harness.

Most of these tests do not actually need the real anchor pool —
regeneration is triggered but the worker can run against a tiny pool
for speed. We still request the session-scoped ``real_words`` fixture
because :func:`rhymepass.generator.generate` needs it to validate
rhyme candidates.
"""

from __future__ import annotations

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
