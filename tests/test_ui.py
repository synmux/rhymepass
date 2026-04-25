"""Tests for the interactive Textual UI, driven by its pilot harness.

Most of these tests do not actually need the real anchor pool.
Regeneration is triggered but the worker can run against a tiny pool
for speed. We still request the session-scoped ``real_words`` fixture
because :func:`rhymepass.generator.generate` needs it to validate
rhyme candidates.
"""

from __future__ import annotations

from rhymepass.randomgen import (
    ALL_SYMBOLS,
    DIGITS,
    LOWERCASE,
    SAFE_SYMBOLS,
    UPPERCASE,
)
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


class TestPassphraseAppMode:
    """Mode-toggle (``m``) behaviour: state, CSS, regeneration, modal min.

    Each test waits for the regeneration worker via
    ``app.workers.wait_for_complete()`` after pressing ``m`` because the
    mode flip dispatches a thread worker that runs asynchronously - a
    bare ``pilot.pause()`` would race against worker completion.
    """

    async def test_m_toggles_random_mode_reactive(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """Pressing ``m`` flips ``app.random_mode`` and pressing again restores it."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.random_mode is False
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert app.random_mode is True
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert app.random_mode is False

    async def test_m_adds_and_removes_css_class(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """The ``random-mode`` CSS class is what drives the purple accent."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert not app.has_class("random-mode")
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert app.has_class("random-mode")
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert not app.has_class("random-mode")

    async def test_m_replaces_batch_with_random_passwords(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """After ``m`` the visible batch contains random passwords, not couplets."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            # Random passwords have no rhyming separator and no whitespace.
            for password in app._passphrases:
                assert " / " not in password
                assert " " not in password
                # Sanity: at least one safe symbol must be present.
                assert any(c in SAFE_SYMBOLS for c in password)

    async def test_random_mode_modal_accepts_short_limit(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """Limit modal accepts 8 in random mode; the same value would be rejected in rhyme mode."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            await pilot.press("l")
            await pilot.pause()
            assert isinstance(app.screen, LimitModal)
            # Replace the default 0 with 8. In rhyme mode this would
            # be rejected (MIN_SINGLE_LEN=9); in random mode the
            # minimum is 4 so 8 must be accepted.
            await pilot.press("8")
            await pilot.pause()
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert not isinstance(app.screen, LimitModal)
            assert app.limit == 8

    async def test_status_bar_shows_mode(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """Status bar shows ``Mode: rhyme`` / ``Mode: random`` and hides Spaces in random mode."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            status = app.query_one("#status-bar")
            assert "Mode: rhyme" in str(status.render())
            assert "Spaces:" in str(status.render())
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert "Mode: random" in str(status.render())
            assert "Spaces:" not in str(status.render())

    async def test_key_hints_drop_x_in_random_mode(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """Footer hint omits the ``x: toggle spaces`` hint when in random mode."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            hints = app.query_one("#key-hints")
            assert "x: toggle spaces" in str(hints.render())
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert "x: toggle spaces" not in str(hints.render())
            assert "m: mode" in str(hints.render())
            # Random mode advertises the charset toggles instead.
            assert "1-5: charset" in str(hints.render())


class TestPassphraseAppCharset:
    """Random-mode character-class toggles (keys ``1`` through ``5``).

    Each test that triggers regeneration awaits
    ``app.workers.wait_for_complete()`` because the toggle dispatches
    a thread worker and the assertions need the post-regeneration
    state.
    """

    async def test_default_charset(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """The five-class charset starts with ``all`` off, the rest on."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.charset == frozenset({"upper", "lower", "digits", "safe"})

    async def test_charset_bar_hidden_in_rhyme_mode(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """Charset bar is ``display: none`` when not in random mode."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            bar = app.query_one("#charset-bar")
            # Textual exposes the resolved CSS display value here.
            assert str(bar.styles.display) == "none"

    async def test_charset_bar_visible_in_random_mode(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """Charset bar becomes visible after pressing ``m``."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            bar = app.query_one("#charset-bar")
            assert str(bar.styles.display) == "block"
            # Bar text shows all five chips with their keys.
            text = str(bar.render())
            for key in ("[1]", "[2]", "[3]", "[4]", "[5]"):
                assert key in text

    async def test_card_min_width_fits_all_chips_on_narrow_screen(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """All five chips remain visible when the screen is barely wide enough.

        Regression guard for the truncation bug: if the OptionList
        rows are narrower than the charset bar, the card's ``width:
        auto`` would otherwise size to the rows and clip the bar's
        right edge. The random-mode ``min-width`` rule prevents that.

        The assertion compares the card's resolved *outer* width (the
        rendered widget including border and padding) against the
        chip-text width plus chrome. If the min-width rule is
        removed, the card shrinks to the OptionList width and this
        test fails.
        """
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        # 70 cells is wide enough for the random-mode card's
        # 64-cell min-width but narrower than the rhyme-mode key
        # hints, simulating the screenshotted case.
        async with app.run_test(size=(70, 30)) as pilot:
            await pilot.pause()
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            card = app.query_one("#card")
            # The card's outer rendered width (border + padding +
            # content) must respect the min-width rule of 64 cells.
            # Textual's ``size`` property reports the content area
            # only, so we use ``outer_size`` for the rule check.
            assert card.outer_size.width >= 64
            # The charset bar's rendered text must contain every
            # chip's full label; if the card were too narrow, the
            # right-hand chips would be clipped from the rendered
            # output.
            bar = app.query_one("#charset-bar")
            text = str(bar.render())
            for label in ("Upper", "Lower", "Digits", "Safe", "All"):
                assert label in text, f"missing chip label {label!r} in {text!r}"

    async def test_keys_are_noop_in_rhyme_mode(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """Pressing 1-5 in rhyme mode must not mutate the charset."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            before = app.charset
            for key in ("1", "2", "3", "4", "5"):
                await pilot.press(key)
                await pilot.pause()
            assert app.charset == before

    async def test_1_toggles_uppercase(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """Pressing 1 in random mode flips the ``upper`` class."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert "upper" in app.charset
            await pilot.press("1")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert "upper" not in app.charset

    async def test_5_forces_safe_on(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """Enabling ``all`` (key 5) implicitly enables ``safe`` (key 4)."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            # Disable safe first, then enable all - safe must come back on.
            await pilot.press("4")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert "safe" not in app.charset
            await pilot.press("5")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert "all" in app.charset
            assert "safe" in app.charset

    async def test_disabling_safe_disables_all(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """Disabling ``safe`` while ``all`` is on must also disable ``all``."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            await pilot.press("5")  # all on (also forces safe on)
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert "all" in app.charset
            assert "safe" in app.charset
            await pilot.press("4")  # safe off -> all off too
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert "safe" not in app.charset
            assert "all" not in app.charset

    async def test_cannot_disable_last_class(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """The last enabled class refuses to be disabled (toast, no change)."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            # Disable lower, digits, safe. Upper remains the last class.
            for key in ("2", "3", "4"):
                await pilot.press(key)
                await app.workers.wait_for_complete()
                await pilot.pause()
            assert app.charset == frozenset({"upper"})
            # Now try to disable upper too. Charset must stay at {upper}.
            await pilot.press("1")
            await pilot.pause()
            assert app.charset == frozenset({"upper"})

    async def test_toggle_triggers_regeneration_with_charset_filter(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """After narrowing to uppercase only, every output is uppercase only."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            # Disable lower, digits, safe -> uppercase-only charset.
            for key in ("2", "3", "4"):
                await pilot.press(key)
                await app.workers.wait_for_complete()
                await pilot.pause()
            for password in app._passphrases:
                assert all(c in UPPERCASE for c in password), password
                # Sanity: no other-class chars sneak in.
                assert not any(c in LOWERCASE for c in password)
                assert not any(c in DIGITS for c in password)
                assert not any(c in SAFE_SYMBOLS for c in password)

    async def test_all_symbols_class_can_appear(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """With ``all`` enabled, the unsafe punctuation set is reachable."""
        app = PassphraseApp(
            count=3, pool=tiny_pool, real_words=real_words, seeded=_seed_batch()
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("m")
            await app.workers.wait_for_complete()
            await pilot.pause()
            await pilot.press("5")  # enable "all"
            await app.workers.wait_for_complete()
            await pilot.pause()
            # Every output is guaranteed to contain a char from
            # ALL_SYMBOLS (the per-class one-of-each rule).
            for password in app._passphrases:
                assert any(c in ALL_SYMBOLS for c in password), password


class TestPassphraseAppInitialState:
    """The keyword-only constructor args seed the picker's opening state.

    These tests cover the surface the CLI uses to forward parsed flags
    into the picker. They do not exercise key bindings - those live in
    :class:`TestPassphraseAppKeys`, :class:`TestPassphraseAppMode`, and
    :class:`TestPassphraseAppCharset`.
    """

    async def test_random_mode_initial_state_applies_css_class(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """Opening with ``random_mode=True`` paints the violet accent immediately."""
        app = PassphraseApp(
            count=3,
            pool=tiny_pool,
            real_words=real_words,
            seeded=_seed_batch(),
            random_mode=True,
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.random_mode is True
            assert app.has_class("random-mode")
            # The charset bar must be visible from first paint, not
            # only after the user presses ``m``.
            bar = app.query_one("#charset-bar")
            assert str(bar.styles.display) == "block"

    async def test_rhyme_mode_initial_state_no_css_class(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """The default rhyme mode opens without the violet accent."""
        app = PassphraseApp(
            count=3,
            pool=tiny_pool,
            real_words=real_words,
            seeded=_seed_batch(),
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.random_mode is False
            assert not app.has_class("random-mode")
            bar = app.query_one("#charset-bar")
            assert str(bar.styles.display) == "none"

    async def test_spaces_off_initial_state_strips_rows(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """``spaces_on=False`` shows space-stripped rows on first paint."""
        app = PassphraseApp(
            count=3,
            pool=tiny_pool,
            real_words=real_words,
            seeded=_seed_batch(),
            spaces_on=False,
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.spaces_on is False
            option_list = app.query_one("#passphrase-list")
            for index, phrase in enumerate(_seed_batch()):
                row_text = str(option_list.get_option_at_index(index).prompt)
                # The displayed slug is the seeded phrase with all
                # interior spaces removed.
                stripped = phrase.replace(" ", "")
                assert stripped in row_text
                # Sanity: the *spaced* form of a phrase with spaces
                # must NOT appear (otherwise the toggle had no effect).
                if " " in phrase:
                    assert phrase not in row_text

    async def test_initial_limit_appears_in_status_bar(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """A non-zero opening ``limit`` is reflected in the status text."""
        app = PassphraseApp(
            count=3,
            pool=tiny_pool,
            real_words=real_words,
            seeded=_seed_batch(),
            limit=42,
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.limit == 42
            status = app.query_one("#status-bar")
            assert "Limit: 42" in str(status.render())

    async def test_initial_charset_constrains_active_classes(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """A custom opening ``charset`` flows into ``_active_classes``."""
        app = PassphraseApp(
            count=3,
            pool=tiny_pool,
            real_words=real_words,
            seeded=_seed_batch(),
            random_mode=True,
            charset=frozenset({"upper", "digits"}),
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.charset == frozenset({"upper", "digits"})
            # ``_active_classes`` is what the worker passes into
            # ``generate_random``; it must reflect the constructor's
            # charset, in display order (upper, digits).
            assert app._active_classes() == (UPPERCASE, DIGITS)

    async def test_initial_charset_constrains_regenerated_output(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """Regenerating with an opening custom charset uses only those classes."""
        app = PassphraseApp(
            count=3,
            pool=tiny_pool,
            real_words=real_words,
            seeded=_seed_batch(),
            random_mode=True,
            charset=frozenset({"upper", "digits"}),
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("r")
            await app.workers.wait_for_complete()
            await pilot.pause()
            for password in app._passphrases:
                assert all(c in UPPERCASE + DIGITS for c in password), password
                # Sanity: nothing from the unselected classes leaked in.
                assert not any(c in LOWERCASE for c in password)
                assert not any(c in SAFE_SYMBOLS for c in password)

    async def test_status_bar_hides_spaces_when_random_initial(
        self, tiny_pool: list[str], real_words: set[str]
    ) -> None:
        """Random-mode initial state hides ``Spaces:`` from the status bar."""
        app = PassphraseApp(
            count=3,
            pool=tiny_pool,
            real_words=real_words,
            seeded=_seed_batch(),
            random_mode=True,
        )
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            status = app.query_one("#status-bar")
            text = str(status.render())
            assert "Mode: random" in text
            assert "Spaces:" not in text
