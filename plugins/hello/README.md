# Hello

Example plugin. It is disabled by default.

On a join, leave, or pat event it can reply with a fixed string or a prompt. The web console and the local terminal do not emit group join events, so this plugin stays idle there.

## Config

Copy `config.json.template` to `config.json` in this directory. A missing file falls back to the template.

| Field | Meaning |
| --- | --- |
| `group_welc_fixed_msg` | Map of chat name to a fixed welcome string |
| `group_welc_prompt` | Prompt used when no fixed welcome is set. `{nickname}` is replaced |
| `group_exit_prompt` | Prompt used when a member leaves |
| `patpat_prompt` | Prompt used for a pat event |

`use_character_desc` in the template is ignored. A global fallback welcome can be set as `group_welcome_msg` in the root `config.json`.

Keep `config.json` valid JSON. Do not leave comments in it.
