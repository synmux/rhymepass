# AGENTS.md - `rhymepass`

Guide for AI agents (and humans) working inside this repository. `CLAUDE.md` is a symlink to this file; keep the symlink intact when moving files around.

## What this is

`rhymepass` is a standalone utility that generates passwords in two flavours from one interactive picker:

- **Rhyme mode (default).** Picks a random anchor word, finds phonetic rhymes via the CMU Pronouncing Dictionary, filters them against the GCIDE English dictionary, wraps each side in filler words (determiners, adjectives), and appends two random digits. Format: `"<Phrase A> / <phrase B> / <NN>"` - e.g. `"The underground parade / an undelivered accolade / 38"`.
- **Random mode.** Fully random fixed-length string drawn uniformly from a user-chosen subset of five character classes: uppercase, lowercase, numbers, safe symbols (`@-_.,:§`), and all symbols (the safe set plus the unsafe ASCII punctuation we normally exclude). One character from each enabled class is guaranteed; positions are shuffled with `secrets.SystemRandom`. Selectable in the picker by pressing `m` (flips the accent colour to violet); the active classes are toggled with keys `1`–`5` and shown in a charset bar that appears only in random mode.

Every candidate is also scored with [`zxcvbn`](https://pypi.org/project/zxcvbn/) and tagged with a strength indicator: an emoji (`🤮 / ☹️ / 🫤 / 😀 / 🥳`) plus a one-to-five star run, joined by `" | "`. In the picker the indicator is the trailing column of each row and is recomputed against the displayed form (so toggling spaces with `x` updates it). In pipe mode the indicator goes to **stderr**, so pipes/redirections that consume stdout still receive a clean passphrase stream.

In a TTY the user gets a Textual interface to pick a passphrase with live controls (spaces toggle, character limit, mode toggle, regenerate). In a pipe the tool just prints the generated passphrases, one per line, without importing Textual at all. Both flavours are reachable from both surfaces: every interactive control has a matching CLI flag (`--mode`, `--limit`, `--spaces`/`--no-spaces`, `--classes`), and the picker accepts those flags as its **opening reactive state** (the picker still mutates that state via its bindings - flags set the _opening_ state, not a lock).

Two CLI entry points land here: `rhymepass` (canonical) and `rp` (short alias). Both call `rhymepass.cli:main`, a `click.Command`.

## Layout

```plaintext
src/rhymepass/
├── __init__.py        public API: generate, generate_random, generate_batch,
│                      resolve_classes, build_anchor_pool, load_real_words,
│                      score_passphrase, format_strength, SAFE_SYMBOLS,
│                      DEFAULT_RANDOM_LEN, MIN_RANDOM_LEN, DEFAULT_CHARSET,
│                      CLASS_NAMES, __version__
├── wordbanks.py       DETERMINERS (33) and ADJECTIVES (112) - hand-curated filler banks
├── anchors.py         load_real_words, _syllable_count, _is_good_anchor, build_anchor_pool
├── phrases.py         _starts_with_vowel_sound, _pick_determiner, _build_phrase,
│                      _capitalise, _couplet_filler_splits
├── generator.py       shape constants (SUFFIX_LEN, COUPLET_SEP_LEN, MIN_*) and generate()
├── randomgen.py       LOWERCASE/UPPERCASE/DIGITS/SAFE_SYMBOLS/UNSAFE_SYMBOLS/
│                      ALL_SYMBOLS, DEFAULT_RANDOM_LEN, MIN_RANDOM_LEN,
│                      CLASS_NAMES, DEFAULT_CHARSET, generate_random(length,
│                      classes), resolve_classes(names)
├── batch.py           generate_batch(count, pool, real_words, *, random_mode,
│                      limit, classes) - rhyme/random dispatch shared by the
│                      CLI pipe path and the picker's regen worker
├── strength.py        score_passphrase (zxcvbn wrapper), format_strength (emoji + stars)
├── clipboard.py       copy_to_clipboard (cross-platform; pbcopy/wl-copy/xclip/xsel/clip)
├── cli.py             Click command exposing --mode/--limit/--spaces/--classes/
│                      --interactive plus -v/-h; lazy-loads the pool only when
│                      needed; pipe path uses generate_batch directly; TTY path
│                      forwards parsed flags to run_interactive_app as initial
│                      reactive state
└── ui.py              PassphraseApp (with random_mode + charset reactives,
                       keyword-only initial-state args), LimitModal,
                       run_interactive_app, _score_both_forms, _CLASS_KEY_ORDER
tests/
├── conftest.py        session-scoped real_words + anchor_pool fixtures; tiny_pool
├── test_anchors.py    anchor-quality rules + pool construction
├── test_batch.py      generate_batch dispatch shape; rhyme requires pool;
│                      random tolerates pool=None
├── test_cli.py        Click CliRunner: help/version, count, mode/limit/spaces/
│                      classes, validation errors, --no-interactive override,
│                      stderr-only strength indicator routing
├── test_clipboard.py  per-platform backend dispatch (mocked subprocess)
├── test_generator.py  generate() shape, limit enforcement, error paths
├── test_phrases.py    phrase builder helpers (monkeypatch for deterministic branches)
├── test_random.py     generate_random shape/length/error paths + SAFE_SYMBOLS
│                      content + resolve_classes name->constant mapping
├── test_strength.py   format_strength rubric + real zxcvbn scoring (no mocks)
├── test_ui.py         Textual pilot: key bindings, modal validation, strength
│                      rendering, mode toggle (TestPassphraseAppMode), charset
│                      toggles (TestPassphraseAppCharset), initial-state
│                      constructor args (TestPassphraseAppInitialState)
└── test_wordbanks.py  static invariants on the filler lists
```

## Public API

`rhymepass/__init__.py` exposes the generators, the supporting fixtures, the strength helpers, the random-mode constants and class-name registry, the batch dispatch helper, and the version:

```python
from rhymepass import (
    ALL_SYMBOLS,
    CLASS_NAMES,
    DEFAULT_CHARSET,
    DEFAULT_RANDOM_LEN,
    DIGITS,
    LOWERCASE,
    MIN_RANDOM_LEN,
    SAFE_SYMBOLS,
    UNSAFE_SYMBOLS,
    UPPERCASE,
    __version__,
    build_anchor_pool,
    format_strength,
    generate,
    generate_batch,
    generate_random,
    load_real_words,
    resolve_classes,
    score_passphrase,
)
```

`load_real_words()` and `build_anchor_pool(real_words)` are comparatively expensive (~1 s combined on a warm import cache); call them once per process and reuse the result for any number of `generate()` calls. `score_passphrase()` and `format_strength()` are cheap and stateless - safe to call per generation. `generate_random()` is constant-time in its `length` argument, has no setup cost, and never fails for `length >= MIN_RANDOM_LEN` (4); it does **not** need or accept the anchor pool. `generate_batch()` is a thin dispatch over `generate()` and `generate_random()` shared by the CLI pipe path and the picker's regen worker; rhyme mode requires the pool, random mode tolerates `pool=None`. `resolve_classes()` maps internal class names (`"upper"`, `"lower"`, `"digits"`, `"safe"`, `"all"`) to the corresponding string constants in display order; `"all"` replaces `"safe"` in the resolved tuple because `ALL_SYMBOLS` already contains the safe baseline.

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

`rhymepass.randomgen.resolve_classes(names)` is the canonical mapping from internal class names to character-set strings. It is the single source of truth shared by `PassphraseApp._active_classes()` and the CLI's `--classes` callback. Pass an iterable of names from `CLASS_NAMES` (`"upper"`, `"lower"`, `"digits"`, `"safe"`, `"all"`) and get back a tuple of class strings in **display order** (`UPPERCASE`, `LOWERCASE`, `DIGITS`, then `ALL_SYMBOLS` if `"all"` else `SAFE_SYMBOLS` if `"safe"`). The cascade matters: `"all"` and `"safe"` are mutually exclusive in the _output_ (since `ALL_SYMBOLS` already contains the safe baseline), even when both are present in the input. The picker keeps both names lit on the charset bar in that case, but the resolved tuple is the same.

`rhymepass.randomgen.DEFAULT_CHARSET` (`frozenset({"upper", "lower", "digits", "safe"})`) is the shared default for both the CLI's `--classes` option and `PassphraseApp.charset`. Lifting it out of `ui.py` means the CLI default and the picker default cannot drift.

## CLI surface

`rhymepass.cli:main` is a `click.Command` that exposes every interactive picker control as a flag. The CLI is the user-facing entry point for both console scripts (`rhymepass` and `rp`).

Flag map (every key binding has a matching flag; the picker still accepts the binding):

| Flag                                 | Picker key | Semantics                                                                                                                                                |
| ------------------------------------ | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `[count]` (positional)               | n/a        | Number of passphrases. Default `5`, must be `>= 1`. Click's `IntRange(min=1)` validates.                                                                 |
| `-m, --mode {rhyme,random}`          | `m`        | Mode. Click's `Choice(case_sensitive=False)` accepts `RANDOM`, `Random`, etc.                                                                            |
| `-l, --limit INT`                    | `l`        | Length constraint. Rhyme: max chars (0 or `>= MIN_SINGLE_LEN`). Random: exact length (0 means `DEFAULT_RANDOM_LEN`, otherwise `>= len(active_classes)`). |
| `--spaces` / `--no-spaces`           | `x`        | Whether rhyme output keeps interior spaces. Silent no-op in random mode (rejecting it would force scripts to special-case mode).                         |
| `-c, --classes CSV`                  | `1`-`5`    | Comma-separated subset of `CLASS_NAMES`. The callback validates membership and lower-cases for case-insensitive input. **Rejected with `--mode rhyme`.** |
| `--interactive` / `--no-interactive` | n/a        | Force the picker on/off; default is `sys.stdout.isatty()`.                                                                                               |
| `-v, --version`                      | n/a        | Click's `version_option`; prints `rhymepass <__version__>`.                                                                                              |
| `-h, --help`                         | n/a        | Click's auto-generated help. `context_settings={"help_option_names": ["-h", "--help"]}` makes both spellings work.                                       |

Validation is layered:

1. **Click parameter types** catch trivial input errors (`--limit -1`, `--mode foobar`, missing values).
2. **`_parse_classes_csv` callback** rejects unknown class names with a `BadParameter` listing the valid choices.
3. **Body-level `UsageError`s** catch combinations Click cannot express in its decorators: `--classes` outside random mode, rhyme `--limit` below `MIN_SINGLE_LEN`, random `--limit` below `len(active_classes)`. These fire **before** any pool load so the user gets fast feedback on misuse.

Pool loading is **lazy and conditional**. The CLI loads `real_words` and the anchor pool only if `use_picker or mode == "rhyme"`. Random pure-pipe invocations (`rhymepass --mode random | cat`) skip the ~1 s GCIDE+CMU load entirely. The picker always loads it because the user can press `m` to flip back to rhyme mode mid-session.

Flag flow into the picker. When the TTY branch fires, parsed flags are passed to `run_interactive_app(count, pool, real_words, seeded, *, spaces_on, limit, random_mode, charset)` as keyword arguments. `PassphraseApp.__init__` assigns each one to its matching reactive **before** mount, and `on_mount` calls `set_class(self.random_mode, "random-mode")` so the violet accent paints from first frame instead of waiting for the user to press `m`. The picker's bindings still mutate the same reactives - flags set the _opening_ state, not a lock.

The pipe path uses `generate_batch(...)` directly (no picker, no clipboard). For rhyme output it applies the `--no-spaces` strip via `phrase.replace(" ", "")` before printing - this matches the picker's `_display_form` exactly. Strength indicators go to **stderr** when stderr is a TTY, mirroring the previous behaviour. The TTY path goes straight from the seeded batch into `run_interactive_app`; there is no pre-picker chrome (the previous "Anchor pool: N words" header was removed because the picker's status bar already shows the pool size, and on the pipe side it mixed metadata into the password stream).

stdout in pipe mode therefore contains exactly `count` lines, one passphrase per line, with no header or blank lines. Consumers like `rhymepass 5 | head -1` and `rhymepass 5 > file` can rely on every line being a complete passphrase.

## Textual UI

`rhymepass.ui` exposes two module-level classes and a launcher:

- **`LimitModal(ModalScreen[int | None])`** - centred dialog. `Input(type="integer", restrict=r"[0-9]*")` with value `"0"` pre-selected on mount (so the first digit overwrites rather than appending). The constructor takes a `min_value` (defaulting to `MIN_SINGLE_LEN`); the parent screen passes `MIN_RANDOM_LEN` (4) when in random mode. ENTER validates and dismisses with the int (rejects values below `min_value` via a toast); ESC dismisses with `None`.
- **`PassphraseApp(App[str | None])`** - the picker. Centred card layout via `Screen { align: center middle }` + an inner `#card` `Container` with `width/height: auto; max-width/height: 90%`. Card auto-sizes to content; capped to 90% of terminal so it never overflows. Four reactives drive its state: `spaces_on`, `limit`, `random_mode`, and `charset` (a `frozenset[str]` holding the active class names: `upper`, `lower`, `digits`, `safe`, `all`). The constructor accepts a matching set of **keyword-only** initial-state arguments (`spaces_on`, `limit`, `random_mode`, `charset`) so the CLI can seed the picker's opening state. Defaults match the class-level reactive defaults so existing callers (and existing tests) need no change.
- **`run_interactive_app(count, pool, real_words, seeded, *, spaces_on, limit, random_mode, charset)`** - instantiates the app and returns its result. Forwards every initial-state argument to `PassphraseApp.__init__`.

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

`click` is imported at `cli.py`'s module top and is **always** loaded, even on the pipe path - but it is a single, lightweight package with no transitive dependencies, so the cost is negligible. Do not move it inside the TTY branch; the `@click.command` decorator runs at import time.

### Non-TTY gate in `cli.main()`

The picker is shown when `sys.stdout.isatty()` is true (Textual needs a real terminal) **unless** the user overrides via `--interactive` / `--no-interactive`. The resolved decision lives in `use_picker = interactive if interactive is not None else sys.stdout.isatty()`. Never call `run_interactive_app` unconditionally - the lazy import is gated on the same boolean.

### Pipe-mode stdout/stderr split for the strength indicator

In the pipe branch, passphrases go to **stdout** and the strength indicator goes to **stderr**, one line each per passphrase. The code uses `click.echo` (which flushes per call) instead of bare `print(..., flush=True)`:

```python
if not use_picker:
    show_strength = sys.stderr.isatty()
    check_weak = mode != "random" and limit > 0
    any_weak = False
    for phrase in seeded:
        display = (
            phrase if mode == "random" or spaces else phrase.replace(" ", "")
        )
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
```

This keeps `rhymepass 5 | xargs ...` and `rhymepass 5 > file` clean (consumers receive only the password) while still showing the indicator on an attached terminal. The `sys.stderr.isatty()` gate skips scoring for the _indicator_ when stderr is redirected (`> file 2>/dev/null`), but the weak-score check (`check_weak`) is not gated on `isatty()`: the warning is useful for scripts and CI pipelines, not just interactive sessions.

`click.echo` flushes its target stream after each call, so stdout and stderr stay correctly ordered when a terminal merges them. Don't replace it with bare `print` without restoring `flush=True`.

### Weak-strength warning

When the generator is constrained by a non-zero character limit in rhyme mode, it walks progressively shorter output forms to squeeze each couplet under the cap. The phonetic and lexical choices narrow with each step; below about 16 characters the rhyme partner is dropped entirely and output falls back to a single-statement form (`"Abcd / 12"`). This descent can push `zxcvbn` scores below the five-star threshold. Switching to random mode removes the tradeoff because the limit becomes an **exact** length rather than an upper bound, and every character position contributes uniformly to entropy.

**Interactive picker (`PassphraseApp._maybe_warn_weak_strength`)**

The method fires after every batch render in rhyme mode when `limit > 0`. It inspects `self._scores` using the current display-form index (matching `_refresh_list`), so the check reflects the password the user would actually copy. Suppression conditions:

| Condition                  | Suppressed? | Reason                                                            |
| -------------------------- | ----------- | ----------------------------------------------------------------- |
| `self.random_mode is True` | Yes         | Suggestion to switch to random would be circular.                 |
| `self.limit == 0`          | Yes         | Unconstrained generation does not trigger the phonetic narrowing. |
| All `pair[idx] > 3`        | Yes         | Every passphrase already scores 5 stars; no warning needed.       |

Call sites:

1. `on_mount()` — covers the seeded batch that was generated before the picker opened.
2. `on_worker_state_changed()` (SUCCESS path, inside the `isinstance` guard) — covers every subsequent regeneration.

**Pipe mode (`cli.main`)**

`check_weak = mode != "random" and limit > 0` gates the per-phrase scoring. `any_weak` is set to `True` on the first phrase whose score is ≤ 3. The final `if any_weak:` block writes the warning to stderr **unconditionally** (not gated on `sys.stderr.isatty()`). stdout is unaffected; passphrases remain clean for downstream consumers.

The `score_passphrase` call is shared between the strength-indicator path (`show_strength`) and the weak-check path (`check_weak`); computing the score once and branching avoids a redundant `zxcvbn` call when both flags are true.

### CLI flags become the picker's opening state, not a lock

When the TTY branch fires, parsed flags are passed into `PassphraseApp.__init__` as keyword-only arguments (`spaces_on`, `limit`, `random_mode`, `charset`). The picker assigns each one to its matching reactive **before** mount, and `on_mount` calls `self.set_class(self.random_mode, "random-mode")` so the violet accent paints from frame zero. The picker's bindings (`m`, `l`, `x`, `r`, `1`-`5`) still mutate those reactives - **flags set the _opening_ state, not a lock**. A user who runs `rhymepass --mode random` can press `m` to flip to rhyme mode without restarting.

Two consequences:

1. The pool is loaded **whenever the picker is going to open**, not only when `mode == "rhyme"` at startup. The picker may need it after the user presses `m`. The CLI's `needs_pool = use_picker or mode == "rhyme"` captures this.
2. The seeded batch must match the _opening_ mode/limit/charset; otherwise the user sees mismatched output for the first frame. The CLI guarantees this by passing the same parameters into `generate_batch` and into `run_interactive_app`.

### Click subsumes the parser; no more `_parse_count` / `_handle_flags`

The pre-Click `cli.py` had small helpers (`_parse_count`, `_handle_flags`, a `USAGE` string) that argparse-style libraries would have provided. They are gone. Click's decorators carry the full type system (`IntRange`, `Choice`), the help text, the version handling, and the option-name aliases (`-m` / `--mode`, `-h` / `--help` via `context_settings`).

Validation that Click's decorators cannot express - `--classes` only with `--mode random`, the per-mode `--limit` minimum - lives in the body of `main()` and raises `click.UsageError`. The error format matches Click's own usage errors so the user cannot tell whether a given check came from the decorator or from the body.

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
- Keep modules focused. `generator.py` and `randomgen.py` are the two generation hot paths; don't let UI or CLI concerns leak into either. `batch.py` is the orchestration helper that dispatches between them; it imports both but neither imports it. `cli.py` and `ui.py` both import from `batch.py`, so the dispatch lives in one place. The dependency arrow points: generators → batch → cli/ui (and ui imports batch directly to avoid round-tripping through cli).
- Update `README.md` (human-facing) whenever the hotkey set, CLI signature, or public API changes. `AGENTS.md` (this file) tracks the internals.
- Commits follow Conventional Commits with a leading gitmoji (see the repo's commit history for examples).
