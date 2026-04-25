"""Command-line entry point.

Two console scripts land here via ``[project.scripts]`` in
``pyproject.toml``:

* ``rhymepass`` - the canonical command name used in docs.
* ``rp`` - a short alias that preserves muscle memory.

Both invoke :func:`main`, a :class:`click.Command`. The interactive
Textual UI module is imported lazily (inside the TTY branch of
:func:`main`) so piped and scripted callers never pay the Textual
import cost. When ``stdout`` is not a TTY, the tool just prints its
generated passphrases, one per line.

The CLI exposes every knob the interactive picker has key bindings
for: mode (``-m``), limit (``-l``), spaces (``--spaces`` /
``--no-spaces``), and the random-mode character classes (``-c``).
When the picker opens, those flags become its **initial reactive
state**; the picker still mutates that state interactively.
"""

from __future__ import annotations

import sys

import click

from rhymepass import __version__
from rhymepass.anchors import build_anchor_pool, load_real_words
from rhymepass.batch import generate_batch
from rhymepass.clipboard import copy_to_clipboard
from rhymepass.generator import MIN_SINGLE_LEN
from rhymepass.randomgen import (
    CLASS_NAMES,
    DEFAULT_CHARSET,
    resolve_classes,
)
from rhymepass.strength import format_strength, score_passphrase

_CLASS_CHOICES_HELP: str = ", ".join(CLASS_NAMES)
"""Comma-joined list of valid class names for use in help text and errors."""


def _parse_classes_csv(
    ctx: click.Context,
    param: click.Parameter,
    value: str | None,
) -> frozenset[str] | None:
    """Click callback: parse ``--classes upper,lower,...`` into a frozen set.

    Empty input (option not supplied) returns ``None`` so the command
    body can apply the right default for the chosen mode. Whitespace
    around individual names is stripped; names are lower-cased so
    ``--classes Upper,DIGITS`` works the same as
    ``--classes upper,digits``.

    Args:
        ctx: Click context (passed automatically).
        param: The parameter being parsed (passed automatically).
        value: The raw string the user typed, or ``None``.

    Returns:
        Frozen set of validated class names, or ``None`` if the option
        was not supplied.

    Raises:
        click.BadParameter: If the input is empty after stripping or
            contains an unknown class name.
    """
    if value is None:
        return None
    names = {part.strip().lower() for part in value.split(",") if part.strip()}
    if not names:
        raise click.BadParameter(
            "at least one class name is required",
            ctx=ctx,
            param=param,
        )
    invalid = names - set(CLASS_NAMES)
    if invalid:
        raise click.BadParameter(
            f"unknown class name(s): {sorted(invalid)}. "
            f"Valid choices: {_CLASS_CHOICES_HELP}.",
            ctx=ctx,
            param=param,
        )
    return frozenset(names)


@click.command(
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=(
        # Click's epilog rewraps paragraphs by default; the leading
        # `\b` marker disables rewrapping for the block so the example
        # column alignment survives.
        "Examples:\n"
        "\n"
        "\b\n"
        "  rhymepass                              Picker, 5 rhyming phrases.\n"
        "  rhymepass 10                           Picker with 10 phrases.\n"
        "  rhymepass --mode random 1              One 24-char random password.\n"
        "  rhymepass -m random -l 16 1            One 16-char random password.\n"
        "  rhymepass -m random -c upper,digits    Random with upper+digits only.\n"
        "  rhymepass --no-spaces 3 | pbcopy       Pipe rhymes; no interior spaces.\n"
    ),
)
@click.argument("count", type=click.IntRange(min=1), default=5)
@click.option(
    "-m",
    "--mode",
    type=click.Choice(["rhyme", "random"], case_sensitive=False),
    default="rhyme",
    show_default=True,
    help="Generation mode.",
)
@click.option(
    "-l",
    "--limit",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    help=(
        "Length constraint. Rhyme mode: max total length, must be 0 "
        "or >= 9. Random mode: exact length, must be 0 (default 24) "
        "or >= the number of enabled classes."
    ),
)
@click.option(
    "--spaces/--no-spaces",
    default=True,
    show_default=True,
    help="Show interior spaces in rhyme output. No-op in random mode.",
)
@click.option(
    "-c",
    "--classes",
    callback=_parse_classes_csv,
    default=None,
    metavar="CSV",
    help=(
        f"Comma-separated random-mode classes from {_CLASS_CHOICES_HELP}. "
        "Random mode only.  [default: upper,lower,digits,safe]"
    ),
)
@click.option(
    "--interactive/--no-interactive",
    default=None,
    help=(
        "Force the picker on/off. By default the picker is shown "
        "when stdout is a TTY."
    ),
)
@click.version_option(
    __version__,
    "-v",
    "--version",
    prog_name="rhymepass",
    message="%(prog)s %(version)s",
)
def main(
    count: int,
    mode: str,
    limit: int,
    spaces: bool,
    classes: frozenset[str] | None,
    interactive: bool | None,
) -> None:
    """Generate memorable rhyming passphrases or fully random passwords.

    In a TTY the interactive picker opens with the supplied options as
    its initial state; the picker still mutates that state via its
    bindings (m/l/x/r/1-5), so flags set the *opening* state - not a
    lock.

    In a pipe (or with --no-interactive) the batch is generated once
    and printed to stdout, one passphrase per line. The strength
    indicator is written to stderr when stderr is a TTY.
    """
    mode = mode.lower()

    # --classes only makes sense in random mode; surface mismatched
    # combinations as Click usage errors before paying any pool-load
    # or generation cost.
    if classes is not None and mode != "random":
        raise click.UsageError("--classes is only valid with --mode random.")

    # Resolve the random-mode charset early so the per-mode --limit
    # validation can reference the count of enabled classes (the
    # generator's per-class minimum).
    if mode == "random":
        charset = classes if classes is not None else DEFAULT_CHARSET
        active_classes = resolve_classes(charset)
        if 0 < limit < len(active_classes):
            raise click.UsageError(
                f"In random mode --limit must be 0 (default 24) or at "
                f"least {len(active_classes)} (one character per "
                f"enabled class). Got {limit}."
            )
    else:
        charset = DEFAULT_CHARSET
        active_classes = resolve_classes(charset)
        if 0 < limit < MIN_SINGLE_LEN:
            raise click.UsageError(
                f"In rhyme mode --limit must be 0 or at least "
                f"{MIN_SINGLE_LEN}. Got {limit}."
            )

    use_picker = interactive if interactive is not None else sys.stdout.isatty()

    # Random pure-pipe mode skips the ~1 s GCIDE+CMU load entirely.
    # The picker may flip back to rhyme via the `m` key, so it always
    # needs the pool even if the user opens it in random mode.
    needs_pool = use_picker or mode == "rhyme"
    pool: list[str] = []
    real_words: set[str] = set()
    if needs_pool:
        real_words = load_real_words()
        pool = build_anchor_pool(real_words)

    try:
        seeded = generate_batch(
            count,
            pool if needs_pool else None,
            real_words if needs_pool else None,
            random_mode=(mode == "random"),
            limit=limit,
            classes=active_classes,
        )
    except (ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc

    if not use_picker:
        # Pipe path: stdout = passphrases, stderr = strength indicator.
        # Splitting the streams keeps `rhymepass | xargs ...` and
        # `rhymepass > file` consumers receiving only the passphrases,
        # while an attached terminal still sees the indicators
        # interleaved. ``click.echo`` flushes per call, so stdout and
        # stderr stay ordered when a terminal merges them.
        show_strength = sys.stderr.isatty()
        # When a character limit is active in rhyme mode the generator
        # walks progressively shorter output forms to fit each phrase
        # under the cap, which can push zxcvbn scores below the
        # five-star threshold. We score every phrase in that case
        # (even when the strength indicator itself is suppressed) so
        # we can warn the user to consider switching to random mode.
        check_weak = mode != "random" and limit > 0
        any_weak = False
        for phrase in seeded:
            display = phrase if mode == "random" or spaces else phrase.replace(" ", "")
            click.echo(display)
            if show_strength or check_weak:
                s = score_passphrase(display)
                if show_strength:
                    click.echo(format_strength(s), err=True)
                if check_weak and s <= 3:
                    any_weak = True
        if any_weak:
            click.echo(
                "Warning: one or more passphrases scored 4 stars or below "
                "with the current character limit. Consider using "
                "--mode random for stronger passwords.",
                err=True,
            )
        return

    # Lazy import: keeps Textual out of the import graph for the
    # non-TTY path. The TTY path loads the UI module (which pulls
    # Textual and its dependency tree) only once we know we are
    # actually going to show it.
    from rhymepass.ui import run_interactive_app

    chosen = run_interactive_app(
        count=count,
        pool=pool,
        real_words=real_words,
        seeded=seeded,
        spaces_on=spaces,
        limit=limit,
        random_mode=(mode == "random"),
        charset=charset,
    )
    if chosen is None:
        click.echo("No passphrase selected.")
        return

    copy_to_clipboard(chosen)
    click.echo(f"Copied to clipboard: {chosen}")


if __name__ == "__main__":
    # Click's @command decorator returns a Command whose __call__
    # parses sys.argv; the original function's parameters are
    # supplied at parse time. Pyright sees the bare signature and
    # flags the call - the ignore is the standard Click idiom.
    main()  # type: ignore[call-arg]
