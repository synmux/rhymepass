"""Tests for CLI argument parsing and flag handling."""

from __future__ import annotations

import pytest

from rhymepass import cli


class TestParseCount:
    """The positional count argument."""

    def test_no_args_defaults_to_five(self) -> None:
        assert cli._parse_count(["rhymepass"]) == 5

    def test_explicit_count(self) -> None:
        assert cli._parse_count(["rhymepass", "7"]) == 7

    def test_count_one(self) -> None:
        assert cli._parse_count(["rhymepass", "1"]) == 1

    def test_zero_raises(self) -> None:
        with pytest.raises(SystemExit, match="at least 1"):
            cli._parse_count(["rhymepass", "0"])

    def test_negative_raises(self) -> None:
        with pytest.raises(SystemExit, match="at least 1"):
            cli._parse_count(["rhymepass", "-3"])

    def test_non_integer_raises(self) -> None:
        with pytest.raises(SystemExit, match="integer"):
            cli._parse_count(["rhymepass", "abc"])

    def test_too_many_args_raises(self) -> None:
        with pytest.raises(SystemExit, match="Too many arguments"):
            cli._parse_count(["rhymepass", "3", "4"])

    def test_float_raises(self) -> None:
        with pytest.raises(SystemExit, match="integer"):
            cli._parse_count(["rhymepass", "3.5"])


class TestHandleFlags:
    """The --help / --version short-circuit."""

    def test_no_flags_returns_false(self) -> None:
        assert cli._handle_flags(["rhymepass"]) is False
        assert cli._handle_flags(["rhymepass", "5"]) is False

    def test_version_flag_prints_and_signals(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from rhymepass import __version__

        assert cli._handle_flags(["rhymepass", "--version"]) is True
        out = capsys.readouterr().out
        assert __version__ in out

    def test_short_version_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        from rhymepass import __version__

        assert cli._handle_flags(["rhymepass", "-v"]) is True
        out = capsys.readouterr().out
        assert __version__ in out

    def test_help_flag_prints_usage(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert cli._handle_flags(["rhymepass", "--help"]) is True
        out = capsys.readouterr().out
        assert "Usage:" in out
        assert "rhymepass" in out

    def test_short_help_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert cli._handle_flags(["rhymepass", "-h"]) is True
        out = capsys.readouterr().out
        assert "Usage:" in out

    def test_unrecognised_flag_returns_false(self) -> None:
        # Anything other than -h/--help/-v/--version is left to _parse_count.
        assert cli._handle_flags(["rhymepass", "--unknown"]) is False
