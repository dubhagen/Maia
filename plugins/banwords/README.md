# Banwords

Filters messages against a word list. Enabled by default.

Put one word per line in `banwords.txt` in this directory. Copy `config.json.template` to `config.json` if you want to change the defaults.

| Field | Meaning |
| --- | --- |
| `action` | What to do with a matching user message. `ignore` drops it. `replace` masks the word with `*` |
| `reply_filter` | Also scan the model's reply |
| `reply_action` | `ignore` or `replace` for a matching reply |

The default action is `ignore`. The matcher is the bundled `WordsSearch` implementation.
