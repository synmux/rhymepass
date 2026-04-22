"""Tests for the cross-platform clipboard helper.

Each backend is exercised by faking the three external signals
``copy_to_clipboard`` depends on:

* ``platform.system()`` - chooses the top-level branch.
* ``shutil.which(name)`` - reports which helper binaries are on
  ``PATH``.
* ``os.environ`` - ``WAYLAND_DISPLAY`` is the canonical flag that
  tells us a Wayland session is live.

All invocations of ``subprocess.run`` are captured into a list so each
test can assert on argv, stdin payload, and encoding without touching
the real system clipboard.
"""

from __future__ import annotations

from typing import Any

import pytest

from rhymepass import clipboard


class _RunRecorder:
    """Captures ``subprocess.run`` calls for later inspection."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        argv: list[str],
        *,
        input: bytes,  # noqa: A002 - mirror subprocess.run signature
        check: bool,
    ) -> None:
        self.calls.append({"argv": argv, "input": input, "check": check})


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _RunRecorder:
    """Replace ``clipboard.subprocess.run`` with a recorder."""
    rec = _RunRecorder()
    monkeypatch.setattr(clipboard.subprocess, "run", rec)
    return rec


def _patch_platform(monkeypatch: pytest.MonkeyPatch, system: str) -> None:
    monkeypatch.setattr(clipboard.platform, "system", lambda: system)


def _patch_which(monkeypatch: pytest.MonkeyPatch, available: set[str]) -> None:
    monkeypatch.setattr(
        clipboard.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in available else None,
    )


class TestMacOS:
    """Darwin still uses pbcopy - existing behaviour must be preserved."""

    def test_uses_pbcopy_with_utf8_payload(
        self,
        monkeypatch: pytest.MonkeyPatch,
        recorder: _RunRecorder,
    ) -> None:
        _patch_platform(monkeypatch, "Darwin")
        _patch_which(monkeypatch, {"pbcopy"})

        clipboard.copy_to_clipboard("hello")

        assert len(recorder.calls) == 1
        call = recorder.calls[0]
        assert call["argv"] == ["pbcopy"]
        assert call["input"] == b"hello"
        assert call["check"] is True

    def test_missing_pbcopy_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        recorder: _RunRecorder,
    ) -> None:
        _patch_platform(monkeypatch, "Darwin")
        _patch_which(monkeypatch, set())

        with pytest.raises(RuntimeError, match="pbcopy"):
            clipboard.copy_to_clipboard("hello")
        assert recorder.calls == []


class TestLinuxWayland:
    """Wayland sessions: prefer wl-copy, fall back to X11 tools."""

    def test_wayland_display_set_uses_wl_copy(
        self,
        monkeypatch: pytest.MonkeyPatch,
        recorder: _RunRecorder,
    ) -> None:
        _patch_platform(monkeypatch, "Linux")
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        _patch_which(monkeypatch, {"wl-copy", "xclip"})

        clipboard.copy_to_clipboard("hello")

        assert len(recorder.calls) == 1
        assert recorder.calls[0]["argv"] == ["wl-copy"]
        assert recorder.calls[0]["input"] == b"hello"

    def test_wayland_without_wl_copy_falls_back_to_xclip(
        self,
        monkeypatch: pytest.MonkeyPatch,
        recorder: _RunRecorder,
    ) -> None:
        """XWayland is common; xclip still works under many Wayland sessions."""
        _patch_platform(monkeypatch, "Linux")
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        _patch_which(monkeypatch, {"xclip"})

        clipboard.copy_to_clipboard("hello")

        assert len(recorder.calls) == 1
        assert recorder.calls[0]["argv"][0] == "xclip"


class TestLinuxX11:
    """Classic X11: xclip preferred, xsel as fallback."""

    def test_x11_uses_xclip_with_clipboard_selection(
        self,
        monkeypatch: pytest.MonkeyPatch,
        recorder: _RunRecorder,
    ) -> None:
        _patch_platform(monkeypatch, "Linux")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        _patch_which(monkeypatch, {"xclip"})

        clipboard.copy_to_clipboard("hello")

        # Default xclip target is PRIMARY; we want the real CLIPBOARD.
        assert recorder.calls[0]["argv"] == ["xclip", "-selection", "clipboard"]
        assert recorder.calls[0]["input"] == b"hello"

    def test_x11_falls_back_to_xsel_when_xclip_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        recorder: _RunRecorder,
    ) -> None:
        _patch_platform(monkeypatch, "Linux")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        _patch_which(monkeypatch, {"xsel"})

        clipboard.copy_to_clipboard("hello")

        assert recorder.calls[0]["argv"] == ["xsel", "--clipboard", "--input"]
        assert recorder.calls[0]["input"] == b"hello"

    def test_linux_no_backend_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        recorder: _RunRecorder,
    ) -> None:
        _patch_platform(monkeypatch, "Linux")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        _patch_which(monkeypatch, set())

        with pytest.raises(RuntimeError) as excinfo:
            clipboard.copy_to_clipboard("hello")

        # Error should name the tools the user can install.
        message = str(excinfo.value)
        assert "xclip" in message
        assert "wl-copy" in message or "wl-clipboard" in message
        assert recorder.calls == []


class TestWindows:
    """Windows ships clip.exe; non-ASCII text must be UTF-16LE encoded."""

    def test_windows_uses_clip_with_utf16le(
        self,
        monkeypatch: pytest.MonkeyPatch,
        recorder: _RunRecorder,
    ) -> None:
        _patch_platform(monkeypatch, "Windows")
        _patch_which(monkeypatch, {"clip"})

        clipboard.copy_to_clipboard("hello")

        assert len(recorder.calls) == 1
        call = recorder.calls[0]
        assert call["argv"] == ["clip"]
        # clip.exe on Windows treats stdin as UTF-16LE when the BOM is present.
        # For ASCII passphrases UTF-16LE without BOM suffices, but BOM-prefixed
        # UTF-16LE is safest; accept either the raw UTF-16LE encoding or one
        # prefixed with the byte-order mark.
        expected_bare = "hello".encode("utf-16-le")
        expected_bom = b"\xff\xfe" + expected_bare
        assert call["input"] in {expected_bare, expected_bom}

    def test_windows_missing_clip_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        recorder: _RunRecorder,
    ) -> None:
        _patch_platform(monkeypatch, "Windows")
        _patch_which(monkeypatch, set())

        with pytest.raises(RuntimeError, match="clip"):
            clipboard.copy_to_clipboard("hello")
        assert recorder.calls == []


class TestUnknownPlatform:
    """Exotic systems (FreeBSD, AIX...) should fail with a clear message."""

    def test_unknown_platform_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        recorder: _RunRecorder,
    ) -> None:
        _patch_platform(monkeypatch, "Haiku")
        _patch_which(monkeypatch, set())

        with pytest.raises(RuntimeError, match="Haiku"):
            clipboard.copy_to_clipboard("hello")
        assert recorder.calls == []
