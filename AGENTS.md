# AGENTS.md - `rhymepass`

Guide for AI agents (and humans) working inside this repository. `CLAUDE.md` is a symlink to this file; keep the symlink intact when moving files around.

## What this is

`rhymepass` is a standalone utility that generates passwords in two flavours from one interactive picker:

- **Rhyme mode (default).** Picks a random anchor word, finds phonetic rhymes via the CMU Pronouncing Dictionary, filters them against the GCIDE English dictionary, wraps each side in filler words (determiners, adjectives), and appends two random digits. Format: `"<Phrase A> / <phrase B> / <NN>"` - e.g. `"The underground parade / an undelivered accolade / 38"`.
- **Random mode.** Fully random fixed-length string drawn uniformly from a user-chosen subset of five character classes: uppercase, lowercase, numbers, safe symbols (`@-_.,:§`), and all symbols (the safe set plus the unsafe ASCII punctuation we normally exclude). One character from each enabled class is guaranteed; positions are shuffled with `secrets.SystemRandom`. Selectable in the picker by pressing `m` (flips the accent colour to violet); the active classes are toggled with keys `1`–`5` and shown in a charset bar that appears only in random mode.

Every candidate is also scored with [`zxcvbn`](https://pypi.org/project/zxcvbn/) and tagged with a strength indicator: an emoji (`🤮 / 🙁 / 🫤 / 🙂 / 🥳`) plus a one-to-five star run, joined by `" | "`. In the picker the indicator is the trailing column of each row and is recomputed against the displayed form (so toggling spaces with `x` updates it). In pipe mode the indicator goes to **stderr**, so pipes/redirections that consume stdout still receive a clean passphrase stream.

In a TTY the user gets a Textual interface to pick a passphrase with live controls (spaces toggle, character limit, mode toggle, regenerate). In a pipe the tool just prints the generated passphrases, one per line, without importing Textual at all. The CLI / pipe path is currently rhyme-only; the random mode is reachable only from the interactive picker (a `--random` flag is a follow-up candidate, not implemented).

Two CLI entry points land here: `rhymepass` (canonical) and `rp` (short alias). Both call `rhymepass.cli:main`.

## Layout

```plaintext
src/rhymepass/
├── __init__.py        public API: generate, generate_random, build_anchor_pool,
│                      load_real_words, score_passphrase, format_strength,
│                      SAFE_SYMBOLS, DEFAULT_RANDOM_LEN, MIN_RANDOM_LEN, __version__
├── wordbanks.py       DETERMINERS (33) and ADJECTIVES (112) - hand-curated filler banks
├── anchors.py         load_real_words, _syllable_count, _is_good_anchor, build_anchor_pool
├── phrases.py         _starts_with_vowel_sound, _pick_determiner, _build_phrase,
│                      _capitalise, _couplet_filler_splits
├── generator.py       shape constants (SUFFIX_LEN, COUPLET_SEP_LEN, MIN_*) and generate()
├── randomgen.py       LOWERCASE/UPPERCASE/DIGITS/SAFE_SYMBOLS/UNSAFE_SYMBOLS/
│                      ALL_SYMBOLS, DEFAULT_RANDOM_LEN, MIN_RANDOM_LEN,
│                      generate_random(length, classes)
├── strength.py        score_passphrase (zxcvbn wrapper), format_strength (emoji + stars)
├── clipboard.py       copy_to_clipboard (cross-platform; pbcopy/wl-copy/xclip/xsel/clip)
├── cli.py             _parse_count, _handle_flags, main - thin orchestration
└── ui.py              PassphraseApp (with random_mode + charset reactives),
                       LimitModal, run_interactive_app, _score_both_forms,
                       _CLASS_KEY_ORDER, _DEFAULT_CHARSET
tests/
├── conftest.py        session-scoped real_words + anchor_pool fixtures; tiny_pool
├── test_anchors.py    anchor-quality rules + pool construction
├── test_cli.py        _parse_count, --help/--version flag handling
├── test_clipboard.py  per-platform backend dispatch (mocked subprocess)
├── test_generator.py  generate() shape, limit enforcement, error paths
├── test_phrases.py    phrase builder helpers (monkeypatch for deterministic branches)
├── test_random.py     generate_random shape/length/error paths + SAFE_SYMBOLS content
├── test_strength.py   format_strength rubric + real zxcvbn scoring (no mocks)
├── test_ui.py         Textual pilot: key bindings, modal validation, strength rendering,
│                      mode toggle (TestPassphraseAppMode)
└── test_wordbanks.py  static invariants on the filler lists
```

## Public API

`rhymepass/__init__.py` exposes the generators, the supporting fixtures, the strength helpers, three random-mode constants, and the version:

```python
from rhymepass import (
    DEFAULT_RANDOM_LEN,
    MIN_RANDOM_LEN,
    SAFE_SYMBOLS,
    __version__,
    build_anchor_pool,
    format_strength,
    generate,
    generate_random,
    load_real_words,
    score_passphrase,
)
```

`load_real_words()` and `build_anchor_pool(real_words)` are comparatively expensive (~1 s combined on a warm import cache); call them once per process and reuse the result for any number of `generate()` calls. `score_passphrase()` and `format_strength()` are cheap and stateless - safe to call per generation. `generate_random()` is constant-time in its `length` argument, has no setup cost, and never fails for `length >= MIN_RANDOM_LEN` (4); it does **not** need or accept the anchor pool.

## Generator strategy

`generate()` respects an optional character limit by walking through progressively shorter output forms **for the same anchor** before drawing a new anchor:

1. **Couplet descent**: if `word_a` has good rhymes, pick `word_b` and try `total_fillers` from 4 down to 0. For each total, iterate every legal `(fillers_a, fillers_b)` split with both halves in `[0, 2]`. Return the first candidate that fits.
2. **Single-statement fallback** (limit-only): if a couplet form can't fit under a non-zero `limit` (or `word_a` has no good rhymes), drop the rhyme partner and try `"<phrase_a> / NN"` with fillers 2 -> 1 -> 0. This step is **skipped entirely when `limit == 0`** - unlimited generation must stay rhyming, so we redraw instead of emitting a non-rhyming phrase.
3. If neither form fits this anchor, draw a new anchor and restart. After `max_attempts` fruitless draws, raise `RuntimeError`.

The `" / NN"` two-digit suffix is always preserved. Shortest possible output is `"Abcd / 12"` (9 chars); any non-zero limit below `MIN_SINGLE_LEN` (9) is guaranteed to fail.

Constants to know (all live in `rhymepass.generator`):

| Constant          | Value | Meaning                                |
| ----------------- | ----- | -------------------------------------- |
| `SUFFIX_LEN`      | 5     | `" / NN"`                              |
| `COUPLET_SEP_LEN` | 3     | `" / "` between halves                 |
| `MIN_ANCHOR_LEN`  | 4     | matches the check in `_is_good_anchor` |
| `MIN_COUPLET_LEN` | 16    | `"Abcd / abcd / 12"`                   |
| `MIN_SINGLE_LEN`  | 9     | `"Abcd / 12"`                          |

## Random generator strategy

`rhymepass.randomgen.generate_random(length, classes=...)` is a peer to `generate()` for the picker's random mode. It is intentionally **simpler** than the rhyming generator: no anchor pool, no descent loop, no `max_attempts` retry budget. The function:

1. Draws one character from each entry in `classes` (defaulting to `(LOWERCASE, UPPERCASE, DIGITS, SAFE_SYMBOLS)` when omitted) so every output contains at least one character from each requested class.
2. Fills the remaining `length - len(classes)` slots with uniform draws from the union of `classes`.
3. Shuffles the resulting list with `secrets.SystemRandom().shuffle(...)` so the mandatory characters are not always in the first `len(classes)` positions.

Every random draw uses `secrets.choice` (CSPRNG); `random.random()` is never used. The per-class guarantee introduces a microscopic positional bias relative to a strict-uniform draw - well below the resolution of `zxcvbn`, and not visible in any real attack model.

The function raises `ValueError` if `classes` is empty, contains an empty string, or if `length < len(classes)`. The picker's `_active_classes()` always produces a non-empty tuple (the at-least-one-class invariant is enforced when toggling), so the `length < len(classes)` case is the only failure path the worker must handle gracefully.

Constants (in `rhymepass.randomgen`):

| Constant             | Value                               | Meaning                                                                                          |
| -------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------ |
| `LOWERCASE`          | `a..z`                              | 26 chars                                                                                         |
| `UPPERCASE`          | `A..Z`                              | 26 chars                                                                                         |
| `DIGITS`             | `0..9`                              | 10 chars                                                                                         |
| `SAFE_SYMBOLS`       | `@-_.,:§`                           | 7 chars: no shell, URL, regex, or CSV special meaning                                            |
| `UNSAFE_SYMBOLS`     | `string.punctuation - SAFE_SYMBOLS` | the 26 ASCII puncts we normally exclude; computed mechanically so no drift                       |
| `ALL_SYMBOLS`        | `SAFE_SYMBOLS + UNSAFE_SYMBOLS`     | 33 chars: the full punctuation set used when "all symbols" is on                                 |
| `DEFAULT_RANDOM_LEN` | `24`                                | length used when the picker's limit is `0` (no limit)                                            |
| `MIN_RANDOM_LEN`     | `4`                                 | smallest length under the _default_ four classes; the picker enforces `len(classes)` dynamically |

The 69-char default alphabet gives ≈ 6.11 bits per character, so the 24-char default carries ~146 bits of entropy. With "all symbols" enabled the alphabet grows to 95 chars (~6.57 bits/char). `SAFE_SYMBOLS` was deliberately chosen to skip every ASCII shell metacharacter and every URL-special character, plus a single Unicode addition (`§`) that is UTF-8 safe across well-formed HTTP forms. **If you change `SAFE_SYMBOLS`, update the rationale table in this file and the README, and check `tests/test_random.py::TestSafeSymbolsContent` and `TestSymbolUnion` still assert the right invariants.**

## Textual UI

`rhymepass.ui` exposes two module-level classes and a launcher:

- **`LimitModal(ModalScreen[int | None])`** - centred dialog. `Input(type="integer", restrict=r"[0-9]*")` with value `"0"` pre-selected on mount (so the first digit overwrites rather than appending). The constructor takes a `min_value` (defaulting to `MIN_SINGLE_LEN`); the parent screen passes `MIN_RANDOM_LEN` (4) when in random mode. ENTER validates and dismisses with the int (rejects values below `min_value` via a toast); ESC dismisses with `None`.
- **`PassphraseApp(App[str | None])`** - the picker. Centred card layout via `Screen { align: center middle }` + an inner `#card` `Container` with `width/height: auto; max-width/height: 90%`. Card auto-sizes to content; capped to 90% of terminal so it never overflows. Four reactives drive its state: `spaces_on`, `limit`, `random_mode`, and `charset` (a `frozenset[str]` holding the active class names: `upper`, `lower`, `digits`, `safe`, `all`).
- **`run_interactive_app(count, pool, real_words, seeded)`** - instantiates the app and returns its result.

**Key bindings (documented in the card's key-hint label, which itself adapts to the mode):**

| Key         | Action                                                                                              |
| ----------- | --------------------------------------------------------------------------------------------------- |
| `↑` / `↓`   | navigate the passphrase list                                                                        |
| `x`         | toggle displayed spaces (rhyme mode only; silent no-op in random mode, hidden from the footer hint) |
| `l`         | open the limit modal (min 9 in rhyme mode; in random mode min = number of enabled classes, 1..5)    |
| `m`         | toggle rhyme/random; flips accent to violet, reveals the charset bar, regenerates                   |
| `1`–`5`     | random mode only: toggle a class (upper/lower/digits/safe/all). Silent no-op in rhyme mode          |
| `r`         | regenerate the current batch under the current limit, mode, and charset                             |
| `enter`     | copy highlighted passphrase to clipboard (via the platform helper) and exit                         |
| `esc` / `q` | exit without copying                                                                                |

**Row format** is `"<password padded>  [N chars]  <indicator>"` where `<indicator>` is the `format_strength` output for the score that matches the current display form.

**Spaces toggle vs. limit enforcement** - these have two different roles and must not be conflated:

- The per-row `[N chars]` annotation and the strength indicator both reflect `display_form` (i.e. the password the user would actually copy), so toggling spaces with `x` updates both columns to match.
- The character-limit check inside `generate()` always uses the canonical spaced length, so toggling spaces off on a batch that already fits can never push any phrase over the limit.

**Strength score cache** - `PassphraseApp` keeps a parallel `self._scores: list[tuple[int, int]]` where each entry is `(score_with_spaces, score_without_spaces)`. Both scores are computed up front (in `__init__` for the seeded batch, in `_regenerate_worker` for fresh batches) so toggling `spaces_on` is a pure lookup, not a `zxcvbn` call. The helper `_score_both_forms(passphrase)` is a tiny module-level wrapper that builds these pairs. **In random mode** the strip-of-spaces is a no-op so the tuple stores the same score twice; the existing toggle lookup falls through cleanly without any branching.

**Regeneration** happens in a `@work(thread=True, exclusive=True, name="regenerate")` worker that takes `new_limit`, a `random_mode: bool` snapshot, and a `classes: tuple[str, ...]` snapshot of the resolved random-mode charset. All three are captured on the main thread by `_regenerate_under` and passed in explicitly, so the worker thread never touches a Textual reactive (which would be a cross-thread read against an object owned by the main loop). The worker returns `tuple[list[str], list[tuple[int, int]]]` so phrases and their score pairs land in `on_worker_state_changed` together; the handler asserts the tuple shape and swaps both lists atomically. `exclusive=True` means spamming `r`, `m`, or any of `1`–`5` cancels any in-flight regen rather than stacking; on failure (`generate()` raises `RuntimeError`, or `generate_random()` raises `ValueError` because the limit is below `len(classes)`), the previous batch and its scores stay in place.

### Mode toggle (`m`) - state, CSS, footer hints

`action_toggle_mode` does four things in this order:

1. Flips `self.random_mode`.
2. Calls `self.set_class(self.random_mode, "random-mode")` to add or remove a CSS class on the App. The CSS rules `PassphraseApp.random-mode #card`, `PassphraseApp.random-mode #status-bar`, and `PassphraseApp.random-mode #charset-bar` swap the rhyming-blue accents (`$primary`) for Tailwind violet-500 (`#8b5cf6`) and reveal the charset bar (`display: block`). The literal hex avoids depending on Textual's theme-scoped `$accent` token, which can vary between light and dark themes; the override is class-scoped so the rhyme-mode rules are never mutated. `LimitModal` keeps its `$primary` border in both modes (the modal is a separate `ModalScreen` and threading the mode through is a follow-up).
3. Calls `_refresh_status()` and `_refresh_key_hints()`. The status bar suppresses the `Spaces:` field in random mode (it has nothing to act on) and shows `Mode: random` instead. The footer hint drops the `x: toggle spaces` entry in random mode and adds `1-5: charset` while keeping every other key.
4. Calls `_regenerate_under(self.limit)` so the visible batch is replaced with output from the new mode immediately, rather than the user staring at rhymes alongside a `Mode: random` label.

The dispatch inside `_regenerate_worker` is a single branch:

```python
if random_mode:
    target_len = new_limit if new_limit > 0 else DEFAULT_RANDOM_LEN
    phrases = [generate_random(length=target_len, classes=classes)
               for _ in range(self._count)]
else:
    phrases = [generate(self._pool, self._real_words, limit=new_limit)
               for _ in range(self._count)]
```

In random mode `new_limit` is interpreted as the **exact** length (with `0` meaning the default of 24); in rhyme mode it remains an upper bound. This semantic shift is intentional - random mode has no descent loop, so "fit under" doesn't translate. The status bar always shows the raw integer or `none`.

### Charset toggles (`1`–`5`) - state, bar, constraints

The random-mode generator runs against a caller-chosen subset of the five character classes. The picker tracks the active subset in `self.charset: reactive[frozenset[str]]` (initial value `{"upper", "lower", "digits", "safe"}` - the four defaults) and exposes one binding per class via `_CLASS_KEY_ORDER`:

| Key | Internal name | Class string                    |
| --- | ------------- | ------------------------------- |
| `1` | `upper`       | `UPPERCASE`                     |
| `2` | `lower`       | `LOWERCASE`                     |
| `3` | `digits`      | `DIGITS`                        |
| `4` | `safe`        | `SAFE_SYMBOLS`                  |
| `5` | `all`         | `ALL_SYMBOLS` (replaces `safe`) |

`_CLASS_KEY_ORDER` is the single source of truth for chip ordering in the bar, the binding labels, and the action names; the bar text, the bindings, and the actions cannot drift out of sync because they all derive from this tuple.

`_active_classes()` materialises the reactive into the tuple of strings the worker needs. It treats `safe` and `all` as a unit: when `all` is enabled, `ALL_SYMBOLS` is appended in place of `SAFE_SYMBOLS`. The `_toggle_class` constraints below make `all`-without-`safe` impossible, so the safe baseline is never lost.

**Direction-aware constraints** in `_toggle_class(name)`:

1. _Enabling_ `all` (key `5`) forces `safe` on too. ALL_SYMBOLS already contains the safe baseline; this just keeps the charset bar honest about which conceptual classes are active.
2. _Disabling_ `safe` (key `4` while `safe` was on) forces `all` off too. Without the safe baseline, "all symbols" would mean "unsafe only", which is almost certainly not what the user wants.

Both rules are gated on the toggle direction (captured in `turning_on = name not in self.charset` _before_ the mutation). Bidirectional rules on the final state would cancel out: removing `safe` while `all` is on would remove `safe`, then the "`all` implies `safe`" rule would re-add it - no progress. Direction-aware rules fire at most once per action and always reflect the user's intent.

After constraints, the charset must contain at least one class. The last remaining toggle refuses to disable and emits a warning toast instead. A no-op guard (`frozenset(new) == self.charset`) skips the regeneration entirely if the constrained result equals the current state - useful, e.g., when the user presses `5` while `all` is already on (key `5` toggles the same set the constraints produce).

**Charset bar visibility** is class-scoped CSS:

```css
#charset-bar { display: none; ... }
PassphraseApp.random-mode #charset-bar {
    display: block;
    background: #8b5cf6 20%;
}
```

The bar exists in both modes but is removed from the layout (`display: none`) in rhyme mode, so the card auto-shrinks back to its rhyme-mode size when the user flips `m`. The `_charset_text()` helper renders one chip per class with Rich markup: bold + `✓` for enabled, dim + `·` for disabled.

**Modal minimum** in random mode is `len(self._active_classes())` (1..5), not the static `MIN_RANDOM_LEN`. The modal validator enforces it inline so the user gets immediate feedback if they request a length below the class count. Below that the worker would otherwise raise `ValueError("length must be at least N to fit one of each ...")` and the previous batch would stay in place via the existing failure-rollback path.

**No-ops in rhyme mode**: keys `1`–`5` early-return when `random_mode` is False. The bindings stay registered (Textual doesn't easily support per-mode binding sets) so pressing them in rhyme mode is silent and harmless.

## Gotchas

### Lazy Textual import at the module boundary

`rhymepass.ui` imports Textual at module top level, but `rhymepass.cli` only does `from rhymepass.ui import run_interactive_app` **inside the TTY branch** of `main()`. This keeps the non-TTY path (`rhymepass | cat`, CI usage) fast and free of Textual's dependency footprint (Textual transitively pulls ~9 packages including Rich and Pygments).

This is a deliberate departure from the previous single-file version, which nested the UI classes inside a function to achieve the same invariant. The module-boundary approach is cleaner, lets `ui.py` use standard top-level imports, and is still just as fast on the pipe path.

### Non-TTY gate in `cli.main()`

`if not sys.stdout.isatty(): print each; return` - Textual needs a real terminal. The gate is mandatory; never unconditionally call `run_interactive_app`.

### Pipe-mode stdout/stderr split for the strength indicator

In the non-TTY branch, passphrases go to **stdout** and the strength indicator goes to **stderr**, one line each per passphrase, both with `flush=True`:

```python
if not sys.stdout.isatty():
    show_strength = sys.stderr.isatty()
    for passphrase in passphrases:
        print(passphrase, flush=True)
        if show_strength:
            print(format_strength(score_passphrase(passphrase)),
                  file=sys.stderr, flush=True)
    return
```

This keeps `rhymepass 5 | xargs ...` and `rhymepass 5 > file` clean (consumers receive only the password) while still showing the indicator on an attached terminal. The `sys.stderr.isatty()` gate skips scoring entirely when stderr is also redirected (`> file 2>/dev/null`) - no point spending zxcvbn time on output nobody will see.

The `flush=True` on both streams is correctness-critical: with default block-buffering on a non-TTY stdout, all the password lines would buffer and emit only at process exit, after every indicator. Don't remove the flushes.

### Cross-platform clipboard

`rhymepass.clipboard.copy_to_clipboard` dispatches to a per-platform helper binary, with every platform check confined to this module:

| Platform        | Backend(s) tried, in order                               |
| --------------- | -------------------------------------------------------- |
| macOS           | `pbcopy`                                                 |
| Linux (Wayland) | `wl-copy`, then `xclip`, then `xsel` (XWayland fallback) |
| Linux (X11)     | `xclip`, then `xsel`                                     |
| Windows         | `clip` (payload encoded as UTF-16LE with BOM)            |
| Anything else   | `RuntimeError` - no backend known                        |

Wayland vs X11 is detected via `$WAYLAND_DISPLAY`. Each backend is a `_Backend` dataclass (binary name, argv tuple, stdin encoder); `_select_backend` walks the list and picks the first one `shutil.which()` resolves, so falling back across helpers is just tuple concatenation. Adding a new backend (e.g. `termux-clipboard-set`) is one tuple entry, not a new branch.

When every candidate is missing, `RuntimeError` is raised with a message that names the install targets (`wl-clipboard`, `xclip`, `xsel`, etc.) rather than letting `FileNotFoundError` leak from `subprocess`. Call sites stay a bare `copy_to_clipboard(text)` - platform awareness never leaks out.

Tests in `tests/test_clipboard.py` monkeypatch `platform.system`, `shutil.which`, `os.environ`, and `subprocess.run`, so they cover every backend path on any host without mutating the developer's real clipboard.

### Python 3.11+

Type annotations use `X | Y` union syntax and `set[str]` / `list[str]` built-in generics, both of which require Python 3.10+. `pyproject.toml` pins `>=3.11` to match the oldest CPython still receiving bug fixes. If you lower the pin, make sure the syntax still parses on the older target.

### `pronouncing` version pin

`pronouncing >= 0.3.0` dropped the dead `from pkg_resources import resource_stream` import that made earlier versions break on `setuptools >= 82`. The project used to ship a `pkg_resources` shim to compensate; that shim has been removed now that the minimum is 0.3.0. If you lower the `pronouncing` pin, reintroduce the shim (the old code is in git history).

## Development

Tool versions: Python `3.14` for local dev (pinned in `.python-version`), package supports `>=3.11`. Managed with `uv`; task runner is `mise` (`mise.toml`).

### mise tasks

| Task           | What it does                                             |
| -------------- | -------------------------------------------------------- |
| `sync`         | `uv sync --extra dev` - install / refresh dev deps       |
| `test`         | `uv run pytest`                                          |
| `test-verbose` | `uv run pytest -v`                                       |
| `run`          | `uv run rhymepass` - launch interactive picker           |
| `smoke`        | `uv run rhymepass 8 \| cat` - non-TTY pipe test          |
| `smoke-lib`    | Call `generate()` directly via `uv run python -c ...`    |
| `clean`        | `rm -rf dist/`                                           |
| `build`        | Clean dist/, then `uv build` (wheel + sdist)             |
| `check`        | `uvx twine check dist/*` - preflight metadata check      |
| `publish-dry`  | `uv publish --dry-run` - rehearse upload without sending |
| `publish-test` | build -> check -> publish to TestPyPI                    |
| `publish`      | build -> check -> publish to PyPI                        |

```bash
mise run sync
mise run test
mise run test-verbose
mise run pytest tests/test_generator.py   # single file (bypass mise)
mise run run
mise run smoke
mise run smoke-lib
mise run build
mise run check
mise run publish-dry
mise run publish-test
mise run publish
```

One-off commands that have no mise wrapper:

```bash
uv run rhymepass --version
uv run rhymepass --help
uv run rp [count]                         # short alias
uv run pytest tests/test_generator.py     # single-file test run
```

### Headless UI testing

Textual's `run_test` pilot is the right tool for testing the UI without a TTY. Tests live in `tests/test_ui.py`; the pattern is:

```python
async def test_something(tiny_pool: list[str], real_words: set[str]) -> None:
    app = PassphraseApp(count=3, pool=tiny_pool, real_words=real_words, seeded=[...])
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        # assert on app state
```

`asyncio_mode = "auto"` in `[tool.pytest]` in `pyproject.toml` auto-applies `@pytest.mark.asyncio` to every `async def` test, so no decorator is required. Session-scoped `real_words` and `anchor_pool` fixtures in `conftest.py` keep the suite fast.

## Conventions

- British English spelling in prose.
- `uv` for all Python package management; never call `pip` directly.
- Real service calls, not mocks, for tests that exercise dictionary data. Monkeypatching `secrets.choice` / `secrets.randbelow` is fine for deterministic branch coverage in `test_phrases.py`.
- No silent failures - raise with a useful message or `notify(severity="error")` in the UI.
- Keep modules focused. `generator.py` and `randomgen.py` are the two generation hot paths; don't let UI concerns leak into either. `ui.py` is allowed to import from both, but the dependency arrow never points the other way. `randomgen.py` is also independent of `generator.py` (and vice versa) - they are siblings, not a hierarchy.
- Update `README.md` (human-facing) whenever the hotkey set, CLI signature, or public API changes. `AGENTS.md` (this file) tracks the internals.
- Commits follow Conventional Commits with a leading gitmoji (see the repo's commit history for examples).
