"""System clipboard helper.

Cross-platform clipboard support with platform detection confined to
this module. Callers invoke :func:`copy_to_clipboard` and get either a
successful copy or a :class:`RuntimeError` explaining what is missing.

Backends by platform:

* **macOS** (``Darwin``): ``pbcopy`` - ships with every modern macOS.
* **Linux on Wayland** (``$WAYLAND_DISPLAY`` set): ``wl-copy`` from the
  ``wl-clipboard`` package, with a fall-through to ``xclip`` / ``xsel``
  for sessions running XWayland where only the X11 tools are present.
* **Linux on X11**: ``xclip`` preferred, ``xsel`` as fallback.
* **Windows**: ``clip.exe`` - shipped since Windows Vista. Text is
  encoded as UTF-16LE with a byte-order mark so non-ASCII characters
  round-trip correctly.

Adding a new backend is a matter of appending to the relevant list in
:func:`_linux_backends` / :func:`_backends_for`, not sprinkling
platform checks across the codebase.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess  # nosec B404
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class _Backend:
    """A concrete clipboard helper.

    Attributes:
        binary: Executable name looked up on ``PATH`` via
            :func:`shutil.which`. If it is not present the backend is
            skipped.
        argv: Full argv to hand to :func:`subprocess.run`. The first
            element must match ``binary``.
        encode: Function that converts the text payload to the byte
            stream the binary expects on stdin.
    """

    binary: str
    argv: tuple[str, ...]
    encode: Callable[[str], bytes]


def _utf8(text: str) -> bytes:
    return text.encode("utf-8")


def _utf16_le_bom(text: str) -> bytes:
    """Encode ``text`` as UTF-16LE prefixed with a byte-order mark.

    Windows' ``clip.exe`` inspects the BOM to decide how to interpret
    stdin. ASCII-only input also works as plain UTF-8, but emitting a
    BOM-prefixed UTF-16LE stream is the safest choice and matches the
    convention used by PowerShell's ``Set-Clipboard``.
    """
    return b"\xff\xfe" + text.encode("utf-16-le")


_MAC_BACKENDS: tuple[_Backend, ...] = (
    _Backend(binary="pbcopy", argv=("pbcopy",), encode=_utf8),
)

_WINDOWS_BACKENDS: tuple[_Backend, ...] = (
    _Backend(binary="clip", argv=("clip",), encode=_utf16_le_bom),
)

_X11_BACKENDS: tuple[_Backend, ...] = (
    _Backend(binary="xclip", argv=("xclip", "-selection", "clipboard"), encode=_utf8),
    _Backend(binary="xsel", argv=("xsel", "--clipboard", "--input"), encode=_utf8),
)

_WAYLAND_BACKENDS: tuple[_Backend, ...] = (
    _Backend(binary="wl-copy", argv=("wl-copy",), encode=_utf8),
)


def _linux_backends() -> tuple[_Backend, ...]:
    """Ordered Linux backends: Wayland first iff the session is Wayland."""
    if os.environ.get("WAYLAND_DISPLAY"):
        # Prefer native Wayland, but fall through to X11 tools because
        # many Wayland compositors also run XWayland and users may have
        # only xclip/xsel installed.
        return _WAYLAND_BACKENDS + _X11_BACKENDS
    return _X11_BACKENDS


def _backends_for(system: str) -> tuple[_Backend, ...]:
    if system == "Darwin":
        return _MAC_BACKENDS
    if system == "Windows":
        return _WINDOWS_BACKENDS
    if system == "Linux":
        return _linux_backends()
    return ()


def _select_backend(backends: tuple[_Backend, ...]) -> _Backend | None:
    for backend in backends:
        if shutil.which(backend.binary) is not None:
            return backend
    return None


def _missing_backend_message(system: str, backends: tuple[_Backend, ...]) -> str:
    """Build the RuntimeError message when no backend is available."""
    if not backends:
        return (
            f"Clipboard copy is not supported on {system!r}; "
            "no known helper binary for this platform."
        )
    if system == "Linux":
        # Always list every supported Linux tool so users learn their
        # options regardless of whether WAYLAND_DISPLAY happens to be
        # set (some containers, remote sessions, or kiosk setups have
        # unusual environments).
        return (
            "Clipboard copy on Linux requires one of: wl-copy (Wayland), "
            "xclip (X11), or xsel (X11). None were found on PATH - "
            "install `wl-clipboard`, `xclip`, or `xsel` via your "
            "package manager."
        )
    names = ", ".join(backend.binary for backend in backends)
    return (
        f"Clipboard copy on {system} requires `{names}` on PATH, "
        "but it was not found."
    )


def copy_to_clipboard(text: str) -> None:
    """Copy ``text`` to the system clipboard.

    Args:
        text: The string to place on the clipboard.

    Raises:
        RuntimeError: If the current platform has no known clipboard
            backend, or if every candidate backend is missing from
            ``PATH``. The message names the tools the caller should
            install.
        subprocess.CalledProcessError: If the chosen helper exits
            non-zero (vanishingly rare; usually a broken install).
    """
    system = platform.system()
    backends = _backends_for(system)
    backend = _select_backend(backends)
    if backend is None:
        raise RuntimeError(_missing_backend_message(system, backends))
    subprocess.run(
        list(backend.argv), input=backend.encode(text), check=True
    )  # nosec B603
