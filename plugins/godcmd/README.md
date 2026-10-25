# Godcmd

Admin commands for the running process. Enabled by default.

## Setup

Copy `config.json.template` to `config.json` and set `password`. If `password` is empty, the process logs a one-time password at startup. Do not share that line.

In a direct chat:

```text
#auth <password>
#help
```

`#auth` is refused in a group. `#help` lists the commands available to the current user.

`admin_users` in `config.json` is the list of user ids that stay authenticated.
