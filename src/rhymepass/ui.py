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


class LimitModal(ModalScreen[int | None]):
    """Modal prompt for a character-limit integer.

    Dismisses with the validated integer (``0`` meaning "no limit")
    or ``None`` if the user presses ``Escape``. Values between ``1``
    and :data:`rhymepass.generator.MIN_SINGLE_LEN` minus one are
    rejected inline via a toast because no passphrase shorter than
    ``"Abcd / 12"`` can be built.
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

    def compose(self) -> ComposeResult:
        """Build the modal content: a label, an input, and a hint."""
        yield Vertical(
            Label(f"Character limit (0 = no limit, min {MIN_SINGLE_LEN}):"),
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
        if value != 0 and value < MIN_SINGLE_LEN:
            self.app.notify(
                f"Limit must be 0 or at least {MIN_SINGLE_LEN} characters.",
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
    """

    BINDINGS = [
        Binding("x", "toggle_spaces", "Toggle spaces"),
        Binding("l", "set_limit", "Set limit"),
        Binding("r", "regenerate", "Regenerate"),
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "cancel", "Cancel", show=False),
    ]

    spaces_on: reactive[bool] = reactive(True)
    limit: reactive[int] = reactive(0)

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
        self._pending_limit: int | None = None

    def compose(self) -> ComposeResult:
        """Build the main-screen layout as a centred card."""
        yield Container(
            Static(self._status_text(), id="status-bar"),
            OptionList(id="passphrase-list"),
            Static(
                "x: toggle spaces  ·  l: set limit  ·  r: regenerate"
                "  ·  enter: copy  ·  esc: cancel",
                id="key-hints",
            ),
            id="card",
        )

    def on_mount(self) -> None:
        """Populate the list with the seeded batch once mounted."""
        self._refresh_list()

    # Rendering helpers ------------------------------------------------

    def _status_text(self) -> str:
        """Return the current status-bar string."""
        pool_size = f"{len(self._pool):,}"
        limit_txt = "none" if self.limit == 0 else str(self.limit)
        spaces_txt = "on" if self.spaces_on else "off"
        return f" Pool: {pool_size}  ·  Limit: {limit_txt}" f"  ·  Spaces: {spaces_txt}"

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
        display_forms = [self._display_form(phrase) for phrase in self._passphrases]
        column_width = max(len(form) for form in display_forms)
        rows = [
            f"{display:<{column_width}}  [{len(display)} chars]"
            for display in display_forms
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
        """Prompt for a new character limit and regenerate if accepted."""

        def handle(new_limit: int | None) -> None:
            if new_limit is None or new_limit == self.limit:
                return
            self._regenerate_under(new_limit)

        self.push_screen(LimitModal(), handle)

    def action_regenerate(self) -> None:
        """Draw a fresh batch of passphrases under the current limit."""
        self._regenerate_under(self.limit)

    def action_cancel(self) -> None:
        """Exit without copying anything."""
        self.exit(None)

    # Regeneration -----------------------------------------------------

    @work(thread=True, exclusive=True, name="regenerate")
    def _regenerate_worker(self, new_limit: int) -> list[str]:
        """Regenerate the passphrase batch on a worker thread.

        Returning normally signals success; raising
        :class:`RuntimeError` (from :func:`generate`) signals failure.
        Both land in :meth:`on_worker_state_changed`, which dispatches
        the UI update on the main thread.

        Args:
            new_limit: The character limit to enforce for this batch.

        Returns:
            A freshly-generated batch of ``self._count`` passphrases.
        """
        return [
            generate(self._pool, self._real_words, limit=new_limit)
            for _ in range(self._count)
        ]

    def _regenerate_under(self, new_limit: int) -> None:
        """Kick off a background regeneration under ``new_limit``."""
        self._pending_limit = new_limit
        self._regenerate_worker(new_limit)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Swap in the regenerated batch, or roll back on failure."""
        if event.worker.name != "regenerate":
            return
        pending = self._pending_limit
        if pending is None:
            return

        if event.state is WorkerState.SUCCESS:
            result = event.worker.result
            if isinstance(result, list):
                self.limit = pending
                self._passphrases = result
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
