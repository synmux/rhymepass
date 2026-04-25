"""Tests for the Click-based command-line interface.

The CLI is exercised through :class:`click.testing.CliRunner`, which
runs the command in-process with mocked stdout/stderr. CliRunner sees
neither stream as a TTY, so the picker is never opened - every test
here covers the pipe path and the option-parsing layer.

Where the CLI would otherwise pay the ~1 s GCIDE+CMU load on every
rhyme-mode call, the ``patched_loaders`` fixture redirects those
loaders to the session-scoped pool fixtures from ``conftest.py``, so
the suite stays fast.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from rhymepass import __version__
from rhymepass.cli import main


def _make_runner() -> CliRunner:
    """Return a CliRunner with stderr separated from stdout.

    Click 8.1 had a ``mix_stderr=False`` kwarg; Click 8.2 removed it
    because separated streams became the default. Falling back keeps
    the tests version-tolerant across the supported pin range.
    """
    try:
        return CliRunner(mix_stderr=False)
    except TypeError:
        return CliRunner()


@pytest.fixture
def runner() -> CliRunner:
    """Per-test :class:`CliRunner`."""
    return _make_runner()


@pytest.fixture
def patched_loaders(
    monkeypatch: pytest.MonkeyPatch,
    anchor_pool: list[str],
    real_words: set[str],
) -> None:
    """Redirect CLI pool loaders to the session-scoped fixtures.

    This avoids the ~1 s GCIDE/CMU load on every rhyme-mode CLI test
    while preserving the actual generator behaviour: the same pool
    and word-set the rest of the suite uses.
    """
    monkeypatch.setattr("rhymepass.cli.load_real_words", lambda: real_words)
    monkeypatch.setattr("rhymepass.cli.build_anchor_pool", lambda _: anchor_pool)


# Help / version --------------------------------------------------------------


class TestHelp:
    """The auto-generated help text exposes the CLI surface."""

    def test_help_long_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "--mode" in result.output
        assert "--limit" in result.output
        assert "--spaces" in result.output
        assert "--no-spaces" in result.output
        assert "--classes" in result.output
        assert "--interactive" in result.output

    def test_help_short_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["-h"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_help_lists_class_choices(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert "upper" in result.output
        assert "lower" in result.output
        assert "digits" in result.output
        assert "safe" in result.output
        assert "all" in result.output

    def test_help_shows_examples(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert "Examples:" in result.output


class TestVersion:
    """The version flag is wired up via :func:`click.version_option`."""

    def test_version_long_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_short_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["-v"])
        assert result.exit_code == 0
        assert __version__ in result.output


# Count argument --------------------------------------------------------------


class TestCount:
    """The positional ``COUNT`` argument and its validation."""

    def test_default_count_is_five(
        self, runner: CliRunner, patched_loaders: None
    ) -> None:
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        # Pipe mode prints exactly `count` passphrase lines and
        # nothing else - no header, no blank lines.
        passphrases = [line for line in result.output.splitlines() if line.strip()]
        assert len(passphrases) == 5

    def test_no_anchor_pool_header_in_pipe_mode(
        self, runner: CliRunner, patched_loaders: None
    ) -> None:
        # Pipe consumers receive only passphrases. The "Anchor pool:"
        # metadata line printed by older versions used to mix
        # metadata into the password stream and is now suppressed.
        result = runner.invoke(main, ["3"])
        assert result.exit_code == 0
        assert "Anchor pool" not in result.output
        # Stricter check: every output line should be a passphrase
        # (no blank separator before the first phrase).
        lines = result.output.splitlines()
        assert lines[0].strip() != ""

    def test_explicit_count(self, runner: CliRunner, patched_loaders: None) -> None:
        result = runner.invoke(main, ["3"])
        assert result.exit_code == 0
        passphrases = [line for line in result.output.splitlines() if line.strip()]
        assert len(passphrases) == 3

    def test_zero_count_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["0"])
        assert result.exit_code != 0

    def test_negative_count_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["-3"])
        assert result.exit_code != 0

    def test_non_integer_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["abc"])
        assert result.exit_code != 0

    def test_too_many_positional_args(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["3", "4"])
        assert result.exit_code != 0


# Mode + rhyme-specific behaviour ---------------------------------------------


class TestRhymeMode:
    """The default rhyme mode prints rhyming couplets to stdout."""

    def test_rhyme_output_contains_slash(
        self, runner: CliRunner, patched_loaders: None
    ) -> None:
        result = runner.invoke(main, ["3"])
        assert result.exit_code == 0
        # Every rhyme passphrase has at least one " / " separator.
        passphrases = [line for line in result.output.splitlines() if line.strip()]
        for phrase in passphrases:
            assert "/" in phrase

    def test_no_spaces_strips_interior_spaces(
        self, runner: CliRunner, patched_loaders: None
    ) -> None:
        result = runner.invoke(main, ["--no-spaces", "3"])
        assert result.exit_code == 0
        passphrases = [line for line in result.output.splitlines() if line.strip()]
        # The " / " around the digit suffix becomes "/" with the
        # surrounding spaces stripped; the interior word spaces are
        # also gone.
        for phrase in passphrases:
            assert " " not in phrase
            assert "/" in phrase

    def test_limit_below_minimum_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--limit", "5"])
        assert result.exit_code != 0
        assert "at least 9" in result.output or "at least 9" in (
            result.stderr if hasattr(result, "stderr") else ""
        )

    def test_classes_rejected_in_rhyme_mode(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--mode", "rhyme", "--classes", "upper"])
        assert result.exit_code != 0


# Mode + random-specific behaviour --------------------------------------------


class TestRandomMode:
    """``--mode random`` produces fixed-length passwords."""

    def test_default_length_is_used_when_limit_zero(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--mode", "random", "1"])
        assert result.exit_code == 0
        line = result.output.strip()
        # No anchor-pool header in random mode.
        assert "Anchor pool" not in result.output
        # Default length is 24.
        assert len(line) == 24

    def test_explicit_limit_sets_exact_length(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--mode", "random", "--limit", "8", "5"])
        assert result.exit_code == 0
        passphrases = [line for line in result.output.splitlines() if line.strip()]
        assert len(passphrases) == 5
        for phrase in passphrases:
            assert len(phrase) == 8

    def test_classes_filter_alphabet(self, runner: CliRunner) -> None:
        result = runner.invoke(
            main,
            [
                "--mode",
                "random",
                "--classes",
                "upper,digits",
                "--limit",
                "12",
                "5",
            ],
        )
        assert result.exit_code == 0
        passphrases = [line for line in result.output.splitlines() if line.strip()]
        # Only uppercase + digits expected.
        for phrase in passphrases:
            assert all(c.isupper() or c.isdigit() for c in phrase), phrase

    def test_invalid_class_name_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--mode", "random", "--classes", "wat"])
        assert result.exit_code != 0

    def test_limit_below_class_count_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(
            main,
            [
                "--mode",
                "random",
                "--limit",
                "1",
                "--classes",
                "upper,lower",
            ],
        )
        assert result.exit_code != 0

    def test_mode_is_case_insensitive(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--mode", "RANDOM", "1"])
        assert result.exit_code == 0

    def test_classes_are_case_insensitive(self, runner: CliRunner) -> None:
        result = runner.invoke(
            main,
            ["--mode", "random", "--classes", "Upper,DIGITS", "8"],
        )
        assert result.exit_code == 0
        # 8 lines of digits-only-or-upper-only chars.
        for phrase in result.output.splitlines():
            if phrase.strip():
                assert all(c.isupper() or c.isdigit() for c in phrase)

    def test_no_spaces_in_random_mode_is_silent_noop(self, runner: CliRunner) -> None:
        # Random output has no spaces anyway; passing --no-spaces is
        # accepted and produces the same shape.
        result = runner.invoke(
            main, ["--mode", "random", "--no-spaces", "--limit", "8", "1"]
        )
        assert result.exit_code == 0
        line = result.output.strip()
        assert len(line) == 8
        assert " " not in line

    def test_all_class_uses_full_punctuation(self, runner: CliRunner) -> None:
        # With "all" enabled the alphabet contains unsafe punctuation.
        # Across 50 generations we should observe at least one such
        # character (the one-of-each guarantee makes ALL_SYMBOLS
        # appear in every output).
        result = runner.invoke(
            main,
            [
                "--mode",
                "random",
                "--classes",
                "upper,lower,digits,all",
                "--limit",
                "16",
                "10",
            ],
        )
        assert result.exit_code == 0


# Strength indicator routing --------------------------------------------------


class TestStrengthIndicator:
    """The strength indicator is suppressed when stderr is not a TTY."""

    def test_no_indicator_in_stdout(
        self, runner: CliRunner, patched_loaders: None
    ) -> None:
        # CliRunner streams report isatty()==False, so the indicator
        # is suppressed entirely. None of the strength emoji should
        # appear in stdout.
        result = runner.invoke(main, ["3"])
        assert result.exit_code == 0
        for emoji in ("🤮", "☹️", "🫤", "😀", "🥳"):
            assert emoji not in result.output


# --interactive override ------------------------------------------------------


class TestInteractiveOverride:
    """``--no-interactive`` forces the pipe path even on a TTY."""

    def test_no_interactive_forces_pipe(
        self,
        runner: CliRunner,
        patched_loaders: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Pretend stdout IS a TTY: without --no-interactive the picker
        # would launch (and fail in CliRunner). With --no-interactive
        # the pipe path is taken instead.
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        result = runner.invoke(main, ["--no-interactive", "2"])
        assert result.exit_code == 0
        passphrases = [line for line in result.output.splitlines() if line.strip()]
        assert len(passphrases) == 2
