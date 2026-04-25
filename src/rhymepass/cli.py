"""Command-line entry point.

Two console scripts land here via ``[project.scripts]`` in
``pyproject.toml``:

* ``rhymepass`` - the canonical command name used in docs.
* ``rp`` - a short alias that preserves the previous project's
  muscle memory.

Both call :func:`main`. The interactive Textual UI module is imported
lazily (inside the TTY branch of :func:`main`) so piped and scripted
callers never pay the Textual import cost. When ``stdout`` is not a
TTY, the tool just prints its generated passphrases, one per line.
"""

from __future__ import annotations

import sys

from rhymepass.anchors import build_anchor_pool, load_real_words
from rhymepass.clipboard import copy_to_clipboard
from rhymepass.generator import generate
from rhymepass.strength import format_strength, score_passphrase

USAGE = """\
Usage: rhymepass [count]
       rhymepass [-v | --version]
       rhymepass [-h | --help]

Generate rhyming passphrases.

Positional arguments:
  count       Number of passphrases to generate (default: 5, min: 1).

Options:
  -v, --version   Print the installed rhymepass version and exit.
  -h, --help      Print this help message and exit.

In a TTY, rhymepass launches an interactive picker. Pipe the output
(for example `rhymepass 10 | cat`) to print plain passphrases instead.
"""


def _parse_count(argv: list[str]) -> int:
    """Parse the optional positional count argument.

    Args:
        argv: Raw command-line arguments, conventionally ``sys.argv``.
            Only ``argv[1]`` is inspected; arguments after the count
            are rejected.

    Returns:
        The requested passphrase count. Defaults to ``5`` when no
        count is supplied.

    Raises:
        SystemExit: If the count is not a positive integer, or if
            more than one positional argument is supplied.
    """
    positional = argv[1:]
    if not positional:
        return 5
    if len(positional) > 1:
        raise SystemExit("Too many arguments. Try `rhymepass --help`.")
    try:
        count = int(positional[0])
    except ValueError as exc:
        raise SystemExit("Count must be an integer.") from exc
    if count < 1:
        raise SystemExit("Count must be at least 1.")
    return count


def _handle_flags(argv: list[str]) -> bool:
    """Handle ``--help`` / ``--version`` flags if present.

    Args:
        argv: Raw command-line arguments.

    Returns:
        ``True`` if a flag was handled and the caller should exit;
        ``False`` otherwise (in which case normal argument parsing
        should continue).
    """
    if len(argv) < 2:
        return False
    flag = argv[1]
    if flag in ("-v", "--version"):
        from rhymepass import __version__

        print(f"rhymepass {__version__}")
        return True
    if flag in ("-h", "--help"):
        print(USAGE, end="")
        return True
    return False


def main() -> None:
    """Run the CLI end-to-end.

    Steps:

    1. Handle ``--help`` / ``--version`` flags.
    2. Parse the positional count.
    3. Load the GCIDE word set and build the anchor pool.
    4. Generate a batch of passphrases.
    5. In a TTY, hand control to the interactive picker and copy the
       chosen passphrase to the clipboard. Outside a TTY, print the
       batch to stdout and return.
    """
    argv = sys.argv
    if _handle_flags(argv):
        return

    count = _parse_count(argv)

    real_words = load_real_words()
    pool = build_anchor_pool(real_words)
    print(f"Anchor pool: {len(pool):,} words\n")

    passphrases = [generate(pool, real_words) for _ in range(count)]

    if not sys.stdout.isatty():
        # stdout stays the plain passphrase stream so pipes and
        # redirections receive only the password. The strength
        # indicator is written to stderr, one line per passphrase,
        # so an attached terminal still shows it but
        # ``rhymepass | xargs ...`` and ``rhymepass > file`` are
        # unaffected. ``flush=True`` on both streams keeps stdout
        # and stderr ordered when a terminal merges them - without
        # it Python's default block-buffering on a non-TTY stdout
        # would batch the password lines and emit them after all
        # the indicators.
        show_strength = sys.stderr.isatty()
        for passphrase in passphrases:
            print(passphrase, flush=True)
            if show_strength:
                indicator = format_strength(score_passphrase(passphrase))
                print(indicator, file=sys.stderr, flush=True)
        return

    # Lazy import: keeps Textual out of the import graph for the
    # non-TTY path. The TTY path loads the UI module (which pulls
    # Textual) only once we know we are actually going to show it.
    from rhymepass.ui import run_interactive_app

    chosen = run_interactive_app(count, pool, real_words, passphrases)
    if chosen is None:
        print("No passphrase selected.")
        return

    copy_to_clipboard(chosen)
    print(f"Copied to clipboard: {chosen}")


if __name__ == "__main__":
    main()
