"""System clipboard helper.

Currently only macOS is supported, via the ``pbcopy`` utility that
ships with the operating system. Running on any other platform raises
:class:`RuntimeError` with a message that names the detected OS, so
callers can catch the failure and surface it to the user rather than
having a :class:`FileNotFoundError` leak through from
:mod:`subprocess`.

Cross-platform support is a future enhancement. The intended pattern
is to keep all platform detection inside :func:`copy_to_clipboard`
and dispatch to the appropriate utility
(``pbcopy`` on macOS, ``xclip`` / ``wl-copy`` on Linux,
``clip`` on Windows, etc.) rather than sprinkling platform checks
across call sites.
"""

from __future__ import annotations

import platform
import shutil
import subprocess


def copy_to_clipboard(text: str) -> None:
    """Copy ``text`` to the macOS system clipboard via ``pbcopy``.

    Args:
        text: The string to place on the clipboard. Encoded as UTF-8
            before being piped to ``pbcopy``.

    Raises:
        RuntimeError: If the current operating system is not macOS,
            or if ``pbcopy`` is not available on the system ``PATH``.
        subprocess.CalledProcessError: If ``pbcopy`` exits non-zero
            (vanishingly rare; would suggest a broken install).
    """
    system = platform.system()
    if system != "Darwin":
        raise RuntimeError(
            f"Clipboard copy is currently only supported on macOS; "
            f"detected {system!r}."
        )
    if shutil.which("pbcopy") is None:
        raise RuntimeError(
            "Clipboard copy requires `pbcopy` on PATH, but it was not found."
        )
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
