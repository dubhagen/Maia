# Plugins

Plugins hook the path from an incoming message to the outgoing reply. Each plugin is a directory under `plugins/` with an `__init__.py` that imports the plugin class.

Bundled plugins are listed in `plugins/plugins.json`. There is no plugin marketplace. Install another plugin from a git URL you choose.

## Install

Copy the plugin into `plugins/PLUGIN_NAME/` so its code lives at `plugins/PLUGIN_NAME/*`, then install anything named in that folder's `requirements.txt`. Restart Maia, or run `#scanp` after an admin install.

From an authenticated admin chat:

```text
#installp https://github.com/owner/plugin.git
#scanp
```

`#installp` does not look up a name in a catalog. `plugins/source.json` is empty.

If the plugin ships `config.json.template`, copy it to `config.json` in the same directory and edit that file.

## Events

A plugin registers with `@plugins.register` and binds handlers in `__init__`. `desire_priority` is the default priority. Higher runs first. After the first load, edit priority in `plugins/plugins.json`.

```python
@plugins.register(name="Hello", desc="A simple plugin that says hello", version="0.1", author="example", desire_priority=-1)
class Hello(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
```

Events, in order:

| Event | When |
| --- | --- |
| `ON_RECEIVE_MESSAGE` | A message arrived |
| `ON_HANDLE_CONTEXT` | Before a reply is produced |
| `ON_DECORATE_REPLY` | A reply exists and can be changed |
| `ON_SEND_REPLY` | Before the reply is sent |

The handler receives an `EventContext`. Set `e_context.action` before returning:

- `EventAction.CONTINUE` — pass the event to the next plugin, then the default handler
- `EventAction.BREAK` — skip later plugins and run the default handler
- `EventAction.BREAK_PASS` — skip later plugins and skip the default handler

`plugins/hello/` is a small example. Keep one plugin class per directory. Leave priority below `Godcmd` (999) so admin commands still run first.

## Bundled plugins

| Directory | Enabled by default | Role |
| --- | --- | --- |
| `maia_cli` | yes | CLI helpers |
| `godcmd` | yes | Admin commands (`#auth`, `#help`) |
| `keyword` | yes | Fixed replies for matched keywords |
| `banwords` | yes | Word filter |
| `finish` | yes | Unknown-command check |
| `role` | yes | Role-play prompts |
| `dungeon` | no | Text adventure |
| `hello` | no | Example group welcome replies |
