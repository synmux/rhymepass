# rhymepass

Generate memorable, rhyming passphrases from the CMU Pronouncing Dictionary, with an interactive terminal picker.

```plaintext
The underground parade / an undelivered accolade / 38
My yearning tailor / its xenial whaler / 67
Those nimble amyloid / such gentle android / 16
```

Each passphrase is a rhyming couplet built from real English words, padded with light filler words, plus two random digits. Readable, pronounceable, easy to transcribe, and awkward to guess.

Need raw entropy instead - say, for a legacy field that caps at 8 characters, or anywhere a memorable phrase is overkill? Press `m` in the picker to flip into **random mode**: the same UX in violet, generating fixed-length passwords drawn from a curated, shell-/HTTP-safe character set.

```plaintext
KvR3@m,Lp9-T_eXq.j2bA:cN8
H§p.7-eR4z@nQ,sB
```

## Install

From PyPI:

```sh
pip install rhymepass
```

With [uv](https://docs.astral.sh/uv/):

```sh
uv pip install rhymepass
```

Or as a development checkout:

```sh
git clone https://github.com/synmux/rhymepass.git
cd rhymepass
uv sync
uv run rhymepass
```

Requires Python 3.11 or newer. Clipboard copy works on macOS (via `pbcopy`), Linux (via `wl-copy`, `xclip`, or `xsel` — install one through your package manager if none are present), and Windows (via `clip`).

## Usage

Two commands land the same tool on your `$PATH`:

- `rhymepass` - the canonical name.
- `rp` - a short alias.

### In a terminal

```sh
rhymepass            # picker, 5 rhyming phrases (default)
rhymepass 10         # picker with 10 phrases
rhymepass --help     # full option summary
rhymepass --version  # print the installed version
```

Every interactive picker control is also reachable as a CLI flag. The flags become the **opening state** of the picker (or the configuration of the one-shot pipe path); inside the picker, the same controls remain available as key bindings.

| Option                               | What it does                                                                                                                                                                      |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `[count]`                            | How many passphrases to generate. Default `5`, must be `≥ 1`.                                                                                                                     |
| `-m, --mode {rhyme,random}`          | Generation mode. `rhyme` (default) builds memorable couplets; `random` builds fixed-length passwords from a curated character set.                                                |
| `-l, --limit N`                      | Length constraint. Rhyme mode: maximum total length, must be `0` (no limit) or `≥ 9`. Random mode: exact length, must be `0` (default `24`) or `≥` the number of enabled classes. |
| `--spaces` / `--no-spaces`           | Show or hide interior spaces in rhyme output. Defaults to showing spaces. No-op in random mode.                                                                                   |
| `-c, --classes CSV`                  | Comma-separated random-mode character classes. Choose any non-empty subset of `upper,lower,digits,safe,all`. Defaults to `upper,lower,digits,safe`. Rejected in rhyme mode.       |
| `--interactive` / `--no-interactive` | Force the picker on or off. By default the picker is shown when stdout is a TTY.                                                                                                  |
| `-v, --version`                      | Print the installed version and exit.                                                                                                                                             |
| `-h, --help`                         | Print the help summary and exit.                                                                                                                                                  |

A few common one-liners:

```sh
rhymepass --mode random 1                          # one 24-char random password
rhymepass -m random -l 16 5                        # five 16-char random passwords
rhymepass -m random -c upper,digits 8              # eight uppercase+digit passwords
rhymepass -m random -c upper,lower,digits,all 1    # one max-entropy password
rhymepass --no-spaces 3 | pbcopy                   # rhymes with no interior spaces
rhymepass -l 24 5                                  # five rhymes, each ≤ 24 chars
```

#### In the picker

When stdout is a TTY (and `--no-interactive` is not set), `rhymepass` opens an interactive picker. Use the arrow keys to highlight a passphrase, then press enter - the selected passphrase is copied to your clipboard and the tool exits. CLI flags become the **opening** state, so `rhymepass --mode random --limit 32 --classes upper,digits` opens directly in random mode at limit 32 with that charset; the keys below still mutate the state interactively.

| Key         | What it does                                                                                                                                                                                                                                                                                                                                                                               |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `↑` / `↓`   | Move the highlight.                                                                                                                                                                                                                                                                                                                                                                        |
| `enter`     | Copy the highlighted passphrase and exit.                                                                                                                                                                                                                                                                                                                                                  |
| `x`         | Toggle whether spaces are shown (rhyme mode only). The per-row character count and the strength indicator both update to reflect the displayed form, since that is the password you would actually copy. The character **limit**, however, is always enforced against the spaced form, so toggling is safe.                                                                                |
| `l`         | Prompt for a character limit. `0` means no limit (the default). In rhyme mode the minimum is 9 characters (`"Abcd / 12"`); in random mode the minimum drops to 4. The batch regenerates so every passphrase fits the new limit.                                                                                                                                                            |
| `m`         | Toggle between **rhyme mode** (memorable couplets, the default) and **random mode** (fixed-length passwords from `a–z A–Z 0–9 @-_.,:§`). Random mode flips the accent colour to violet so it is always obvious which mode is active.                                                                                                                                                       |
| `1`–`5`     | **Random mode only.** Toggle character classes used by the random generator. `[1] Upper`, `[2] Lower`, `[3] Digits`, `[4] Safe symbols` (`@-_.,:§`), `[5] All symbols` (the safe set plus more dangerous symbols). Enabling `5` auto-enables `4`; disabling `4` auto-disables `5`. The charset bar at the top shows the current state and the batch regenerates instantly on every toggle. |
| `r`         | Regenerate the batch with the current settings.                                                                                                                                                                                                                                                                                                                                            |
| `esc` / `q` | Exit without copying anything.                                                                                                                                                                                                                                                                                                                                                             |

Each row in the picker ends with a strength indicator built from [`zxcvbn`](https://pypi.org/project/zxcvbn/). The score (`0`–`4`) is rendered as an emoji followed by `" | "` and a one-to-five star run:

| Score | Indicator        |
| ----- | ---------------- |
| 0     | 🤮 \| ⭐         |
| 1     | ☹️ \| ⭐⭐       |
| 2     | 🫤 \| ⭐⭐⭐     |
| 3     | 😀 \| ⭐⭐⭐⭐   |
| 4     | 🥳 \| ⭐⭐⭐⭐⭐ |

Under a tight character budget the picker first drops filler words from the rhyming couplet, then (below ~16 characters) falls back to a single-statement form like `Half dally / 17`. The `" / NN"` two-digit suffix is always preserved.

In random mode the limit is interpreted as the **exact** length (with `0` meaning the default of 24). Every output is guaranteed to contain at least one character from each currently-enabled class, with the remaining slots drawn uniformly from the union of those classes and the final order shuffled with `secrets.SystemRandom`. The "safe symbols" set is `@-_.,:§` - characters that have no special meaning in shells, URLs, regex, or common form-validation rules - so generated passwords paste cleanly into command lines, web forms, and config files without quoting. The "all symbols" toggle extends that with every other ASCII punctuation character (`! " # $ % & ' ( ) * + / ; < = > ? [ \ ] ^ \` { | } ~`) for cases where the receiving system accepts the full set and you want maximum entropy.

The minimum length the modal accepts in random mode is the number of currently-enabled classes (since each one contributes a guaranteed character): one class lets you go as low as 1, all five enabled bumps the minimum to 5.

**Weak-strength warning.** When a character limit is active in rhyme mode, the generator walks progressively shorter output forms to fit each couplet under the cap, narrowing the phonetic and lexical choices at each step. If any passphrase in the current batch scores 4 stars or below (`zxcvbn` score ≤ 3), the picker shows a warning toast suggesting you switch to random mode (press `m`). In random mode the limit is the _exact_ output length, so every character position contributes uniformly to entropy and the tradeoff disappears.

### In a pipe

When `stdout` is not a TTY, `rhymepass` skips the picker and just prints one passphrase per line. The interactive Textual dependency is never imported on this path, so pipe invocations start fast and stay light.

The strength indicator is written to **stderr**, one line per passphrase, while passphrases themselves go to stdout. Pipes and redirections that consume stdout therefore receive only the password, while an attached terminal still sees the indicators interleaved. If `stderr` is also redirected away from a TTY (for example `rhymepass 5 > file 2>/dev/null`), scoring is skipped entirely - no wasted `zxcvbn` work for output nobody will see.

When `--limit` is active in rhyme mode and any passphrase in the batch scores 4 stars or below, an additional warning line is written to **stderr** (unconditionally - not gated on whether stderr is a TTY) suggesting `--mode random` as an alternative. stdout is unaffected; the passphrase lines remain clean.

```sh
rhymepass 3 | cat
# stdout (visible to cat):
#   Those nimble amyloid / such gentle android / 16
#   Our bold missourian / some hopeful centurion / 84
#   Any tactile contemn / much calm condemn / 84
# stderr (visible only on the terminal):
#   🥳 | ⭐⭐⭐⭐⭐
#   🥳 | ⭐⭐⭐⭐⭐
#   🥳 | ⭐⭐⭐⭐⭐
```

stdout therefore contains exactly `count` lines, each a complete passphrase, with no header, blank lines, or other metadata. `rhymepass 5 | head -1` is guaranteed to return the first passphrase.

### As a library

```python
from rhymepass import (
    ALL_SYMBOLS,
    DEFAULT_RANDOM_LEN,
    DIGITS,
    LOWERCASE,
    SAFE_SYMBOLS,
    UPPERCASE,
    build_anchor_pool,
    format_strength,
    generate,
    generate_random,
    load_real_words,
    score_passphrase,
)

# Rhyming flavour
real_words = load_real_words()
pool = build_anchor_pool(real_words)

phrase = generate(pool, real_words)              # no length limit
print(generate(pool, real_words, limit=24))      # fit under 24 characters

score = score_passphrase(phrase)                 # 0..4 from zxcvbn
print(phrase, "|", format_strength(score))       # "<phrase> | 🥳 | ⭐⭐⭐⭐⭐"

# Random flavour - default classes (a-z, A-Z, 0-9, SAFE_SYMBOLS)
print(SAFE_SYMBOLS)                              # "@-_.,:§"
print(generate_random())                         # DEFAULT_RANDOM_LEN (24) chars
print(generate_random(length=12))                # exactly 12 chars

# Custom classes - pick any non-empty subset
print(generate_random(length=8, classes=(UPPERCASE, DIGITS)))   # uppercase + digits only
print(generate_random(length=24, classes=(LOWERCASE, UPPERCASE, DIGITS, ALL_SYMBOLS)))
```

[`load_real_words`](./src/rhymepass/anchors.py) and [`build_anchor_pool`](./src/rhymepass/anchors.py) are comparatively expensive; call them once per process and reuse the result for as many `generate` calls as you need. [`score_passphrase`](./src/rhymepass/strength.py) is fast (a few milliseconds per call) and safe to invoke per generation.

## How it works

Anchor words come from the intersection of two dictionaries:

- the CMU Pronouncing Dictionary (via [`pronouncing`](https://pypi.org/project/pronouncing/)) for phonetic rhymes and syllable counts,
- the GNU Collaborative International Dictionary of English (via [`english-words`](https://pypi.org/project/english-words/)) to exclude proper nouns, abbreviations, and obscure entries.

For every passphrase, `rhymepass` picks a random anchor, looks up phonetic rhymes, filters them through the same quality checks, and assembles two phrases by wrapping each anchor in zero, one, or two filler words drawn from a hand-curated list of determiners (`the`, `some`, `every`, …) and adjectives (`nimble`, `radiant`, `zesty`, …). A two-digit suffix (`10`–`99`) is appended to each passphrase.

All random choices use [`secrets`](https://docs.python.org/3/library/secrets.html) rather than `random`, so the output is suitable for use as an actual passphrase - though you should still pair it with whatever additional entropy your threat model demands.

When a character limit is set, the generator descends through progressively shorter output forms for the same anchor before giving up and drawing a new one, so common limits (20–30 characters) succeed in a few attempts. See [`AGENTS.md`](./AGENTS.md) for the exact descent strategy.

## Dependencies

- [`pronouncing`](https://pypi.org/project/pronouncing/) ≥ 0.3.0 - CMU Pronouncing Dictionary bindings.
- [`english-words`](https://pypi.org/project/english-words/) ≥ 2.0.2 - GCIDE word set for filtering.
- [`textual`](https://pypi.org/project/textual/) ≥ 0.80 - terminal UI. Only imported on the interactive path.
- [`zxcvbn`](https://pypi.org/project/zxcvbn/) ≥ 4.5.0 - realistic password-strength scoring used by the indicator.

See `pyproject.toml` for the exact pin set; the lock file covers transitive dependencies.

## Limitations

- **Clipboard requires a platform helper binary.** macOS ships `pbcopy` out of the box and Windows ships `clip` since Vista, so both work without extra setup. On Linux you need one of `wl-copy` (from the `wl-clipboard` package, preferred on Wayland), `xclip`, or `xsel`. If none are available, the picker raises `RuntimeError` with a message naming the options; the generator itself (and the pipe/library paths) work without any clipboard tool.
- **No history.** Each run produces a fresh batch; nothing is persisted between invocations.

## Contributing

For architecture, internal conventions, and the complete list of gotchas, see [`AGENTS.md`](./AGENTS.md). Run the test suite with:

```sh
uv sync --extra dev
uv run pytest
```

Bug reports, feature ideas, and pull requests are welcome at <https://github.com/synmux/rhymepass>.

## Licence

MIT - see [`LICENSE`](./LICENSE).
