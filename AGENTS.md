# AGENTS.md - `rhymepass`

Guide for AI agents (and humans) working inside this repository. `CLAUDE.md` is a symlink to this file; keep the symlink intact when moving files around.

## What this is

`rhymepass` is a standalone utility that generates rhyming passphrases. It picks a random anchor word, finds phonetic rhymes via the CMU Pronouncing Dictionary, filters them against the GCIDE English dictionary, wraps each side in filler words (determiners, adjectives), and appends two random digits.

Format: `"<Phrase A> / <phrase B> / <NN>"` - e.g. `"The underground parade / an undelivered accolade / 38"`.

In a TTY the user gets a Textual interface to pick a passphrase with live controls (spaces toggle, character limit, regenerate). In a pipe the tool just prints the generated passphrases, one per line, without importing Textual at all.

Two CLI entry points land here: `rhymepass` (canonical) and `rp` (short alias). Both call `rhymepass.cli:main`.

## Layout

```plaintext
src/rhymepass/
├── __init__.py        public API: generate, build_anchor_pool, load_real_words, __version__
├── wordbanks.py       DETERMINERS (33) and ADJECTIVES (112) - hand-curated filler banks
├── anchors.py         load_real_words, _syllable_count, _is_good_anchor, build_anchor_pool
├── phrases.py         _starts_with_vowel_sound, _pick_determiner, _build_phrase,
│                      _capitalise, _couplet_filler_splits
├── generator.py       shape constants (SUFFIX_LEN, COUPLET_SEP_LEN, MIN_*) and generate()
├── clipboard.py       copy_to_clipboard (cross-platform; pbcopy/wl-copy/xclip/xsel/clip)
├── cli.py             _parse_count, _handle_flags, main - thin orchestration
└── ui.py              PassphraseApp, LimitModal, run_interactive_app
tests/
├── conftest.py        session-scoped real_words + anchor_pool fixtures; tiny_pool
├── test_anchors.py    anchor-quality rules + pool construction
├── test_cli.py        _parse_count, --help/--version flag handling
├── test_clipboard.py  per-platform backend dispatch (mocked subprocess)
├── test_generator.py  generate() shape, limit enforcement, error paths
├── test_phrases.py    phrase builder helpers (monkeypatch for deterministic branches)
├── test_ui.py         Textual pilot: key bindings, modal validation
└── test_wordbanks.py  static invariants on the filler lists
```

## Public API

`rhymepass/__init__.py` exposes three functions and the version:

```python
from rhymepass import generate, build_anchor_pool, load_real_words, __version__
```

`load_real_words()` and `build_anchor_pool(real_words)` are comparatively expensive (~1 s combined on a warm import cache); call them once per process and reuse the result for any number of `generate()` calls.

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

## Textual UI

`rhymepass.ui` exposes two module-level classes and a launcher:

- **`LimitModal(ModalScreen[int | None])`** - centred dialog. `Input(type="integer", restrict=r"[0-9]*")` with value `"0"` pre-selected on mount (so the first digit overwrites rather than appending). ENTER validates and dismisses with the int (rejects values in 1..8 with a toast); ESC dismisses with `None`.
- **`PassphraseApp(App[str | None])`** - the picker. Centred card layout via `Screen { align: center middle }` + an inner `#card` `Container` with `width/height: auto; max-width/height: 90%`. Card auto-sizes to content; capped to 90% of terminal so it never overflows.
- **`run_interactive_app(count, pool, real_words, seeded)`** - instantiates the app and returns its result.

**Key bindings (documented in the card's key-hint label):**

| Key         | Action                                                                    |
| ----------- | ------------------------------------------------------------------------- |
| `↑` / `↓`   | navigate the passphrase list                                              |
| `x`         | toggle displayed spaces (the per-row count also updates, so it decreases) |
| `l`         | open the limit modal                                                      |
| `r`         | regenerate the current batch under the current limit                      |
| `enter`     | copy highlighted passphrase to clipboard (via `pbcopy`) and exit          |
| `esc` / `q` | exit without copying                                                      |

**Spaces toggle vs. limit enforcement** - these have two different roles and must not be conflated:

- The per-row `[N chars]` annotation reflects `len(display_form)`, so it decreases when spaces are toggled off.
- The character-limit check inside `generate()` always uses the canonical spaced length, so toggling spaces off on a batch that already fits can never push any phrase over the limit.

**Regeneration** happens in a `@work(thread=True, exclusive=True, name="regenerate")` worker. `on_worker_state_changed` swaps the batch atomically on success, or shows an error toast and leaves state untouched on failure. `exclusive=True` means spamming `r` cancels any in-flight regen rather than stacking.

## Gotchas

### Lazy Textual import at the module boundary

`rhymepass.ui` imports Textual at module top level, but `rhymepass.cli` only does `from rhymepass.ui import run_interactive_app` **inside the TTY branch** of `main()`. This keeps the non-TTY path (`rhymepass | cat`, CI usage) fast and free of Textual's dependency footprint (Textual transitively pulls ~9 packages including Rich and Pygments).

This is a deliberate departure from the previous single-file version, which nested the UI classes inside a function to achieve the same invariant. The module-boundary approach is cleaner, lets `ui.py` use standard top-level imports, and is still just as fast on the pipe path.

### Non-TTY gate in `cli.main()`

`if not sys.stdout.isatty(): print each; return` - Textual needs a real terminal. The gate is mandatory; never unconditionally call `run_interactive_app`.

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
- Keep modules focused. `generator.py` is the hot path; don't let UI concerns leak into it. `ui.py` is allowed to import from `generator`, but not the other way round.
- Update `README.md` (human-facing) whenever the hotkey set, CLI signature, or public API changes. `AGENTS.md` (this file) tracks the internals.
- Commits follow Conventional Commits with a leading gitmoji (see the repo's commit history for examples).
