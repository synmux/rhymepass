# rhymepass

Generate memorable, rhyming passphrases from the CMU Pronouncing Dictionary, with an interactive terminal picker.

```plaintext
The underground parade / an undelivered accolade / 38
My yearning tailor / its xenial whaler / 67
Those nimble amyloid / such gentle android / 16
```

Each passphrase is a rhyming couplet built from real English words, padded with light filler words, plus two random digits. Readable, pronounceable, easy to transcribe, and awkward to guess.

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

Requires Python 3.11 or newer. The clipboard copy step is currently macOS-only (see [Limitations](#limitations)).

## Usage

Two commands land the same tool on your `$PATH`:

- `rhymepass` - the canonical name.
- `rp` - a short alias.

### In a terminal

```sh
rhymepass            # shows five passphrases in an interactive picker
rhymepass 10         # shows ten
rhymepass --help     # usage summary
rhymepass --version  # print the installed version
```

Use the arrow keys to highlight a passphrase, then press enter - the selected passphrase is copied to your clipboard and the tool exits.

| Key         | What it does                                                                                                                                                                                                                                |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `↑` / `↓`   | Move the highlight.                                                                                                                                                                                                                         |
| `enter`     | Copy the highlighted passphrase and exit.                                                                                                                                                                                                   |
| `x`         | Toggle whether spaces are shown. The per-row character count reflects the displayed form, so toggling spaces off makes every count drop. The character **limit**, however, is always enforced against the spaced form, so toggling is safe. |
| `l`         | Prompt for a character limit. `0` means no limit (the default); any positive value must be at least 9 characters. The batch regenerates so every passphrase fits under the new limit.                                                       |
| `r`         | Regenerate the batch with the current settings.                                                                                                                                                                                             |
| `esc` / `q` | Exit without copying anything.                                                                                                                                                                                                              |

Under a tight character budget the picker first drops filler words from the rhyming couplet, then (below ~16 characters) falls back to a single-statement form like `Half dally / 17`. The `" / NN"` two-digit suffix is always preserved.

### In a pipe

When `stdout` is not a TTY, `rhymepass` skips the picker and just prints one passphrase per line. The interactive Textual dependency is never imported on this path, so pipe invocations start fast and stay light.

```sh
rhymepass 3 | cat
# Anchor pool: 24,439 words
#
# Those nimble amyloid / such gentle android / 16
# Our bold missourian / some hopeful centurion / 84
# Any tactile contemn / much calm condemn / 84
```

### As a library

```python
from rhymepass import generate, build_anchor_pool, load_real_words

real_words = load_real_words()
pool = build_anchor_pool(real_words)

print(generate(pool, real_words))              # no length limit
print(generate(pool, real_words, limit=24))    # fit under 24 characters
```

[`load_real_words`](./src/rhymepass/anchors.py) and [`build_anchor_pool`](./src/rhymepass/anchors.py) are comparatively expensive; call them once per process and reuse the result for as many `generate` calls as you need.

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

See `pyproject.toml` for the exact pin set; the lock file covers transitive dependencies.

## Limitations

- **macOS-only clipboard.** The picker copies via the system `pbcopy` utility. Running the picker on Linux or Windows raises `RuntimeError` with a helpful message rather than silently failing; the generator itself (and the pipe/library paths) work everywhere. Cross-platform clipboard support (xclip/wl-copy/Windows clip) is planned but not implemented yet.
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
