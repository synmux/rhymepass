"""Interactive terminal UI for picking a passphrase.

This module wires up a small :class:`textual.app.App` around the
generator: a scrollable list of passphrases with a status bar, a
character-limit modal, and a background worker that re-draws the
batch when the limit changes or the user hits ``r``.

Importing this module pulls Textual into the process, which is a
heavy tree (Rich, mdit, pygments, …). :mod:`rhymepass.cli` therefore
imports this module *lazily*, only on the TTY branch, so pipe and
scripted callers never pay the cost.

Public API:

* :class:`LimitModal` - the character-limit prompt.
* :class:`PassphraseApp` - the picker itself.
* :func:`run_interactive_app` - convenience wrapper that instantiates
  :class:`PassphraseApp` and returns the chosen passphrase (or
  ``None`` if the user cancels).
"""

from __future__ import annotations

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Static
from textual.worker import Worker, WorkerState

from rhymepass.generator import MIN_SINGLE_LEN, generate
from rhymepass.randomgen import (
    ALL_SYMBOLS,
    DEFAULT_RANDOM_LEN,
    DIGITS,
    LOWERCASE,
    SAFE_SYMBOLS,
    UPPERCASE,
    generate_random,
)
from rhymepass.strength import format_strength, score_passphrase

_CLASS_KEY_ORDER: tuple[tuple[str, str, str], ...] = (
    ("1", "Upper", "upper"),
    ("2", "Lower", "lower"),
    ("3", "Digits", "digits"),
    ("4", "Safe", "safe"),
    ("5", "All", "all"),
)
"""Display order for the charset bar: ``(key, label, internal_name)``.

The internal name is the value stored in :attr:`PassphraseApp.charset`;
the key is the binding (and the visible chip in the bar) and the label
is the human-readable column. Single source of truth so the bar text,
the bindings, and the actions cannot drift out of sync.
"""

_DEFAULT_CHARSET: frozenset[str] = frozenset({"upper", "lower", "digits", "safe"})
"""Initial random-mode charset: every default class except "all"."""


def _score_both_forms(passphrase: str) -> tuple[int, int]:
    """Score a passphrase in both display forms.

    Returns ``(score_with_spaces, score_without_spaces)``. The picker
    caches both up front so toggling ``spaces_on`` can flip the
    indicator instantly without re-running zxcvbn on the UI thread.
    """
    return (
        score_passphrase(passphrase),
        score_passphrase(passphrase.replace(" ", "")),
    )


class LimitModal(ModalScreen[int | None]):
    """Modal prompt for a character-limit integer.

    Dismisses with the validated integer (``0`` meaning "no limit")
    or ``None`` if the user presses ``Escape``. Values between ``1``
    and ``min_value - 1`` are rejected inline via a toast.

    The ``min_value`` is supplied by the parent screen because it
    depends on the current generation mode: rhyming mode uses
    :data:`rhymepass.generator.MIN_SINGLE_LEN` (9), while random mode
    can go as low as :data:`rhymepass.randomgen.MIN_RANDOM_LEN` (4).
    """

    DEFAULT_CSS = """
    LimitModal {
        align: center middle;
    }
    LimitModal > Vertical {
        width: 50;
        height: auto;
        padding: 1 2;
        border: thick $primary;
        background: $surface;
    }
    LimitModal .hint {
        color: $text-muted;
        padding-top: 1;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, min_value: int = MIN_SINGLE_LEN) -> None:
        """Store the mode-dependent minimum for use in the validator.

        Args:
            min_value: Smallest accepted non-zero limit. Defaults to
                :data:`rhymepass.generator.MIN_SINGLE_LEN` so existing
                rhyming-mode call sites need no change.
        """
        super().__init__()
        self._min_value = min_value

    def compose(self) -> ComposeResult:
        """Build the modal content: a label, an input, and a hint."""
        yield Vertical(
            Label(f"Character limit (0 = no limit, min {self._min_value}):"),
            Input(
                value="0",
                type="integer",
                restrict=r"[0-9]*",
                id="limit-input",
            ),
            Label("ENTER: confirm · ESC: cancel", classes="hint"),
        )

    def on_mount(self) -> None:
        """Focus the input and pre-select the default so typing overwrites.

        Newer Textual releases expose ``action_select_all``; older
        ones do not. For the latter, we reach into the private
        ``_input.Selection`` helper. As a last resort, clear the
        input so the first keystroke becomes the whole value.
        """
        inp = self.query_one("#limit-input", Input)
        inp.focus()
        try:
            inp.action_select_all()
        except AttributeError:
            try:
                from textual.widgets._input import Selection

                inp.selection = Selection(0, len(inp.value))
            except Exception:
                inp.value = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Validate the typed value and dismiss with the integer."""
        raw = event.value.strip()
        value = int(raw) if raw else 0
        if value != 0 and value < self._min_value:
            self.app.notify(
                f"Limit must be 0 or at least {self._min_value} characters.",
                severity="error",
            )
            return
        self.dismiss(value)

    def action_cancel(self) -> None:
        """Dismiss without returning a new limit."""
        self.dismiss(None)


class PassphraseApp(App[str | None]):
    """Interactive passphrase picker.

    The app takes over the entire terminal, but the visible UI is a
    self-sizing card that auto-fits its content and is capped at 90%
    of each dimension so it never overflows the screen.

    Reactive state:

    * :attr:`spaces_on` - whether interior spaces are shown in the
      displayed passphrases.
    * :attr:`limit` - the current character limit (0 = unlimited).
    * :attr:`random_mode` - whether the picker generates fully random
      passwords (True) or rhyming passphrases (False, the default).
      Toggled with ``m``; flips the accent colour to violet.
    * :attr:`charset` - frozen set of internal class names enabled
      for random-mode generation. Default
      ``{"upper", "lower", "digits", "safe"}``; the user toggles
      members with ``1``..``5``. Ignored in rhyme mode.

    Regeneration runs in a background thread worker so the UI stays
    responsive. ``exclusive=True`` means a fresh regenerate cancels
    any in-flight worker rather than stacking.
    """

    CSS = """
    Screen {
        align: center middle;
        background: $background;
    }
    #card {
        width: auto;
        height: auto;
        max-width: 90%;
        max-height: 90%;
        padding: 1 2;
        border: thick $primary;
        background: $surface;
    }
    #status-bar {
        width: 100%;
        height: 1;
        background: $primary 30%;
        color: $text;
        padding: 0 1;
        margin-bottom: 1;
    }
    #passphrase-list {
        width: auto;
        height: auto;
        max-height: 20;
        border: none;
        padding: 0;
        background: $surface;
    }
    #key-hints {
        width: 100%;
        height: 1;
        color: $text-muted;
        margin-top: 1;
        text-align: center;
    }

    /* The charset bar is hidden in rhyme mode (it has nothing to
       do there) and revealed in random mode by the `random-mode`
       class on the App. Using `display: none` removes it from the
       layout, so the card auto-shrinks back to its rhyme-mode size
       when the user flips back. */
    #charset-bar {
        display: none;
        width: 100%;
        height: 1;
        color: $text;
        padding: 0 1;
        margin-bottom: 1;
    }

    /* Random-mode accent swap. Adding the `random-mode` class to the
       App swaps the rhyming-blue accents for Tailwind violet-500.
       The literal hex avoids depending on Textual's theme-scoped
       `$accent` token, which can vary between light/dark themes. */
    PassphraseApp.random-mode #card {
        border: thick #8b5cf6;
    }
    PassphraseApp.random-mode #status-bar {
        background: #8b5cf6 30%;
    }
    PassphraseApp.random-mode #charset-bar {
        display: block;
        background: #8b5cf6 20%;
    }
    """

    BINDINGS = [
        Binding("x", "toggle_spaces", "Toggle spaces"),
        Binding("l", "set_limit", "Set limit"),
        Binding("m", "toggle_mode", "Mode"),
        Binding("r", "regenerate", "Regenerate"),
        # Charset toggles (random mode only; silent no-op in rhyme mode).
        Binding("1", "toggle_class_upper", "Upper", show=False),
        Binding("2", "toggle_class_lower", "Lower", show=False),
        Binding("3", "toggle_class_digits", "Digits", show=False),
        Binding("4", "toggle_class_safe", "Safe", show=False),
        Binding("5", "toggle_class_all", "All", show=False),
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "cancel", "Cancel", show=False),
    ]

    spaces_on: reactive[bool] = reactive(True)
    limit: reactive[int] = reactive(0)
    random_mode: reactive[bool] = reactive(False)
    charset: reactive[frozenset[str]] = reactive(_DEFAULT_CHARSET)

    def __init__(
        self,
        count: int,
        pool: list[str],
        real_words: set[str],
        seeded: list[str],
    ) -> None:
        """Store the pool/word-set for regeneration and seed the list.

        Args:
            count: How many passphrases to keep visible at once.
            pool: Anchor pool used for regeneration.
            real_words: Word-set filter used to validate rhyme
                candidates during regeneration.
            seeded: Initial batch of passphrases to display.
        """
        super().__init__()
        self._count = count
        self._pool = pool
        self._real_words = real_words
        self._passphrases: list[str] = list(seeded)
        self._scores: list[tuple[int, int]] = [
            _score_both_forms(phrase) for phrase in seeded
        ]
        self._pending_limit: int | None = None

    def compose(self) -> ComposeResult:
        """Build the main-screen layout as a centred card.

        The charset bar sits between the status bar and the option
        list. CSS hides it in rhyme mode (``display: none``) so it
        does not occupy any space until the user enters random mode.
        """
        yield Container(
            Static(self._status_text(), id="status-bar"),
            Static(self._charset_text(), id="charset-bar"),
            OptionList(id="passphrase-list"),
            Static(self._key_hints_text(), id="key-hints"),
            id="card",
        )

    def on_mount(self) -> None:
        """Populate the list with the seeded batch once mounted."""
        self._refresh_list()

    # Rendering helpers ------------------------------------------------

    def _status_text(self) -> str:
        """Return the current status-bar string.

        In random mode the "Spaces:" entry is suppressed because the
        toggle has nothing to act on; the mode itself is shown
        instead so the user always knows which generator is active.
        """
        pool_size = f"{len(self._pool):,}"
        limit_txt = "none" if self.limit == 0 else str(self.limit)
        mode_txt = "random" if self.random_mode else "rhyme"
        if self.random_mode:
            return f" Pool: {pool_size}  ·  Limit: {limit_txt}  ·  Mode: {mode_txt}"
        spaces_txt = "on" if self.spaces_on else "off"
        return (
            f" Pool: {pool_size}  ·  Limit: {limit_txt}"
            f"  ·  Spaces: {spaces_txt}  ·  Mode: {mode_txt}"
        )

    def _key_hints_text(self) -> str:
        """Return the footer hint string for the current mode.

        The ``x`` toggle is hidden in random mode (no spaces to
        toggle); the binding stays registered so pressing ``x`` is a
        silent no-op rather than an error. The ``1-5`` charset
        toggles are hidden in rhyme mode for the same reason.
        """
        if self.random_mode:
            return (
                "1-5: charset  ·  l: set limit  ·  m: mode  ·  r: regenerate"
                "  ·  enter: copy  ·  esc: cancel"
            )
        return (
            "x: toggle spaces  ·  l: set limit  ·  m: mode  ·  r: regenerate"
            "  ·  enter: copy  ·  esc: cancel"
        )

    def _refresh_key_hints(self) -> None:
        """Re-render the footer hint from the current mode."""
        self.query_one("#key-hints", Static).update(self._key_hints_text())

    def _charset_text(self) -> str:
        """Return the random-mode charset bar text.

        Renders one chip per class showing its key, label, and
        on/off state. Bold + tick (``✓``) for enabled,
        muted + dot (``·``) for disabled. The chip order is fixed
        by :data:`_CLASS_KEY_ORDER`.
        """
        chips: list[str] = []
        for key, label, name in _CLASS_KEY_ORDER:
            if name in self.charset:
                chips.append(f"[b][{key}] {label} ✓[/b]")
            else:
                chips.append(f"[dim][{key}] {label} ·[/dim]")
        return " Charset:  " + "  ".join(chips)

    def _refresh_charset_bar(self) -> None:
        """Re-render the charset bar from the current charset reactive."""
        self.query_one("#charset-bar", Static).update(self._charset_text())

    def _active_classes(self) -> tuple[str, ...]:
        """Return the active character-class strings for ``generate_random``.

        Maps the internal class names in :attr:`charset` to the
        corresponding string constants in :mod:`rhymepass.randomgen`.
        ``"all"`` and ``"safe"`` are treated as a unit: when ``"all"``
        is enabled, :data:`ALL_SYMBOLS` (which already contains the
        safe set) is appended in place of :data:`SAFE_SYMBOLS`. The
        ``_toggle_class`` constraints make ``"all"`` without
        ``"safe"`` impossible, so we never lose the safe baseline.
        """
        parts: list[str] = []
        if "upper" in self.charset:
            parts.append(UPPERCASE)
        if "lower" in self.charset:
            parts.append(LOWERCASE)
        if "digits" in self.charset:
            parts.append(DIGITS)
        if "all" in self.charset:
            parts.append(ALL_SYMBOLS)
        elif "safe" in self.charset:
            parts.append(SAFE_SYMBOLS)
        return tuple(parts)

    def _display_form(self, spaced: str) -> str:
        """Return the passphrase in its current display form.

        Strips interior spaces when the toggle is off. The canonical
        (spaced) string is never mutated.
        """
        return spaced if self.spaces_on else spaced.replace(" ", "")

    def _refresh_status(self) -> None:
        """Re-render the status bar from current reactive state."""
        self.query_one("#status-bar", Static).update(self._status_text())

    def _refresh_list(self) -> None:
        """Re-render the option list, preserving the highlight index."""
        option_list = self.query_one("#passphrase-list", OptionList)
        previous = option_list.highlighted
        option_list.clear_options()

        if not self._passphrases:
            return

        # The per-row char count reflects the displayed form, so it
        # decreases when spaces are toggled off. The limit enforced
        # inside generate() always uses the canonical spaced length,
        # so toggling spaces off can never push any phrase over limit.
        # The strength indicator is looked up from the pre-cached
        # (spaced, unspaced) score pair so the toggle keystroke does
        # not block on a fresh zxcvbn call.
        display_forms = [self._display_form(phrase) for phrase in self._passphrases]
        column_width = max(len(form) for form in display_forms)
        rows = [
            f"{display:<{column_width}}  [{len(display)} chars]  "
            f"{format_strength(self._scores[i][0 if self.spaces_on else 1])}"
            for i, display in enumerate(display_forms)
        ]
        option_list.add_options(rows)

        if previous is None or previous >= len(self._passphrases):
            option_list.highlighted = 0
        else:
            option_list.highlighted = previous

    # Actions ----------------------------------------------------------

    def action_toggle_spaces(self) -> None:
        """Flip the display-spaces toggle; no regeneration needed."""
        self.spaces_on = not self.spaces_on
        self._refresh_list()
        self._refresh_status()

    def action_set_limit(self) -> None:
        """Prompt for a new character limit and regenerate if accepted.

        The minimum the modal will accept depends on mode: rhyming
        mode needs at least :data:`MIN_SINGLE_LEN` (9) chars to fit
        ``"Abcd / 12"``. Random mode's true minimum is the number of
        currently-enabled classes (one of each is guaranteed in every
        output), so the modal is told to enforce that count - which
        ranges from ``1`` (a single class enabled) up to ``5`` (every
        class enabled).
        """

        def handle(new_limit: int | None) -> None:
            if new_limit is None or new_limit == self.limit:
                return
            self._regenerate_under(new_limit)

        if self.random_mode:
            minimum = max(1, len(self._active_classes()))
        else:
            minimum = MIN_SINGLE_LEN
        self.push_screen(LimitModal(min_value=minimum), handle)

    def action_regenerate(self) -> None:
        """Draw a fresh batch of passphrases under the current limit."""
        self._regenerate_under(self.limit)

    def action_toggle_mode(self) -> None:
        """Flip between rhyming and random modes.

        The mode change has three visible effects:

        1. The ``random-mode`` CSS class is toggled on the App, which
           swaps the accent colour from blue to violet via the rules
           defined in :attr:`CSS`. The same class also reveals the
           charset bar via the ``display: block`` override.
        2. The status bar and footer hints are re-rendered to reflect
           the new mode (random hides the ``Spaces:`` field and the
           ``x`` hint, and adds the ``1-5: charset`` hint).
        3. A regeneration is kicked off under the current limit so
           the user immediately sees output in the new mode rather
           than rhymes alongside a "Mode: random" label.
        """
        self.random_mode = not self.random_mode
        self.set_class(self.random_mode, "random-mode")
        self._refresh_status()
        self._refresh_key_hints()
        self._regenerate_under(self.limit)

    # Charset toggles. Each binding is a thin wrapper around
    # `_toggle_class(name)` so the action name stays valid identifier-
    # syntax for Textual while the shared logic (constraints,
    # regeneration trigger) lives in one place.

    def action_toggle_class_upper(self) -> None:
        """Toggle the uppercase class in the random-mode charset."""
        self._toggle_class("upper")

    def action_toggle_class_lower(self) -> None:
        """Toggle the lowercase class in the random-mode charset."""
        self._toggle_class("lower")

    def action_toggle_class_digits(self) -> None:
        """Toggle the digits class in the random-mode charset."""
        self._toggle_class("digits")

    def action_toggle_class_safe(self) -> None:
        """Toggle the safe-symbols class in the random-mode charset."""
        self._toggle_class("safe")

    def action_toggle_class_all(self) -> None:
        """Toggle the all-symbols class in the random-mode charset."""
        self._toggle_class("all")

    def _toggle_class(self, name: str) -> None:
        """Flip ``name`` in the charset, apply constraints, regenerate.

        The constraints are **direction-aware** to avoid the rules
        cancelling each other out when both fire on the same final
        state:

        1. Enabling ``"all"`` forces ``"safe"`` on. ``ALL_SYMBOLS``
           contains the safe baseline, so this just keeps the
           charset bar honest about which classes are conceptually
           active.
        2. Disabling ``"safe"`` forces ``"all"`` off. Without the
           safe baseline, "all symbols" would mean "unsafe only" -
           which is almost certainly not what the user wants.

        Note that disabling ``"all"`` does not touch ``"safe"`` (the
        baseline stays as the user left it), and enabling ``"safe"``
        does not touch ``"all"`` (the user explicitly opted out of
        unsafe characters and we should not silently re-enable them).

        After constraints, the charset must contain at least one
        class. The last remaining toggle refuses to disable and emits
        a warning toast instead.

        In rhyme mode the keys are silent no-ops: the charset is a
        random-mode concept and changing it there would just confuse.
        """
        if not self.random_mode:
            return

        # Capture the toggle direction *before* mutating, so the
        # cascade rules below can act on intent rather than final state.
        turning_on = name not in self.charset
        new = set(self.charset)
        if turning_on:
            new.add(name)
        else:
            new.discard(name)

        # Direction-aware cascades.
        if name == "all" and turning_on:
            new.add("safe")
        if name == "safe" and not turning_on:
            new.discard("all")

        # At-least-one-class guard.
        if not new:
            self.notify(
                "At least one character class must be enabled.",
                severity="warning",
            )
            return

        # No-op guard: if the constrained result equals the current
        # charset, we would trigger a pointless regeneration.
        if frozenset(new) == self.charset:
            return

        self.charset = frozenset(new)
        self._refresh_charset_bar()
        self._regenerate_under(self.limit)

    def action_cancel(self) -> None:
        """Exit without copying anything."""
        self.exit(None)

    # Regeneration -----------------------------------------------------

    @work(thread=True, exclusive=True, name="regenerate")
    def _regenerate_worker(
        self,
        new_limit: int,
        random_mode: bool,
        classes: tuple[str, ...],
    ) -> tuple[list[str], list[tuple[int, int]]]:
        """Regenerate the passphrase batch on a worker thread.

        Dispatches on the mode captured by the caller on the main
        thread: rhyming mode calls
        :func:`rhymepass.generator.generate`, random mode calls
        :func:`rhymepass.randomgen.generate_random` with the resolved
        ``classes`` tuple. Capturing both ``random_mode`` and
        ``classes`` at the call site (rather than reading the
        reactives here) keeps the worker free of any cross-thread
        reactive reads.

        Returning normally signals success; raising
        :class:`ValueError` (from ``generate_random`` when the limit
        is below ``len(classes)``) or :class:`RuntimeError` (from
        ``generate`` when no rhyming output fits) signals failure.
        Both land in :meth:`on_worker_state_changed`, which dispatches
        the UI update on the main thread.

        Scoring happens here, off the UI thread, so the picker stays
        responsive even though zxcvbn analysis takes tens of ms per
        passphrase. ``_score_both_forms`` is a no-op for the strip on
        space-less random output, so the cached pair holds the same
        score twice and the toggle lookup falls through cleanly.

        Args:
            new_limit: The character limit to enforce for this batch.
                In rhyming mode this is an upper bound; in random
                mode it is the exact length (with ``0`` meaning
                :data:`DEFAULT_RANDOM_LEN`).
            random_mode: ``True`` to call ``generate_random``,
                ``False`` to call the rhyming generator. Captured
                snapshot from the main thread at dispatch time.
            classes: Resolved character-class strings for random
                mode, produced by :meth:`_active_classes`. Ignored
                in rhyme mode but always passed for shape stability.

        Returns:
            A tuple of ``(passphrases, scores)`` where ``scores`` is a
            parallel list of ``(score_with_spaces, score_without_spaces)``
            pairs. Both lists have length ``self._count``.
        """
        if random_mode:
            target_len = new_limit if new_limit > 0 else DEFAULT_RANDOM_LEN
            phrases = [
                generate_random(length=target_len, classes=classes)
                for _ in range(self._count)
            ]
        else:
            phrases = [
                generate(self._pool, self._real_words, limit=new_limit)
                for _ in range(self._count)
            ]
        scores = [_score_both_forms(phrase) for phrase in phrases]
        return phrases, scores

    def _regenerate_under(self, new_limit: int) -> None:
        """Kick off a background regeneration under ``new_limit``.

        Snapshots :attr:`random_mode` and the resolved active classes
        here, on the main thread, and passes them to the worker as
        explicit arguments. This keeps the worker thread free of
        reactive reads and means a mode (or charset) flip mid-
        generation does not race against an in-flight batch.
        """
        self._pending_limit = new_limit
        self._regenerate_worker(new_limit, self.random_mode, self._active_classes())

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Swap in the regenerated batch, or roll back on failure."""
        if event.worker.name != "regenerate":
            return
        pending = self._pending_limit
        if pending is None:
            return

        if event.state is WorkerState.SUCCESS:
            result = event.worker.result
            # Worker returns ``(passphrases, scores)`` - keep them in
            # lockstep so the index used by ``_refresh_list`` always
            # finds a matching score pair.
            if (
                isinstance(result, tuple)
                and len(result) == 2
                and isinstance(result[0], list)
                and isinstance(result[1], list)
            ):
                phrases, scores = result
                self.limit = pending
                self._passphrases = phrases
                self._scores = scores
                self._refresh_list()
                self._refresh_status()
            self._pending_limit = None
        elif event.state is WorkerState.ERROR:
            self.notify(
                f"Could not fit {self._count} passphrases under "
                f"{pending} characters.",
                severity="error",
            )
            self.notify(
                f"Keeping previous limit "
                f"({'none' if self.limit == 0 else self.limit}).",
                severity="warning",
            )
            self._pending_limit = None

    # Selection --------------------------------------------------------

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Copy the highlighted passphrase's display form and exit."""
        index = event.option_index
        if index is None or index < 0 or index >= len(self._passphrases):
            return
        chosen = self._passphrases[index]
        self.exit(self._display_form(chosen))


def run_interactive_app(
    count: int,
    pool: list[str],
    real_words: set[str],
    seeded: list[str],
) -> str | None:
    """Launch the interactive picker and return the chosen passphrase.

    Args:
        count: Number of passphrases to keep visible.
        pool: Anchor pool for regeneration.
        real_words: GCIDE word filter for regeneration.
        seeded: The initial batch of passphrases to display.

    Returns:
        The selected passphrase in the display form the user saw
        (spaces stripped if the toggle was off), or ``None`` if the
        user cancelled.
    """
    app = PassphraseApp(count=count, pool=pool, real_words=real_words, seeded=seeded)
    return app.run()
