# Backup and Restore

Maia can create a portable local archive for migration or disaster recovery.

## Create a backup

```bash
maia backup
maia backup --output /safe/location/maia-backup.zip
```

The archive contains:

- `config.json`
- Agent persona and user files such as `AGENT.md`, `USER.md`, and `MEMORY.md`
- Daily memory, session history, knowledge, custom skills, and scheduled tasks in the configured workspace
- The Agent registry, channel bindings, and every configured Agent workspace when multi-Agent mode is configured
- Legacy `user_datas.pkl`, when present

Transient `tmp/` data, caches, Git metadata, and symbolic links are skipped. The
archive is written with owner-only permissions where the operating system
supports them.

> **Warning.** A backup may contain API keys, conversation history, and other personal data.
> Store and transfer it as a secret. The ZIP file is not encrypted.

## Restore a backup

Stop Maia before restoring:

```bash
maia stop
maia restore /safe/location/maia-backup.zip
```

Use `--workspace` to migrate workspace files to a different location:

```bash
maia restore maia-backup.zip --workspace ~/maia-restored
```

For a multi-Agent archive, `--workspace` is the instance root. Maia restores
the default Agent into that root and every other Agent into
`<root>/agents/<agent-id>`, the same layout the Agent registry derives on its
own. Without the option, Agent IDs that already exist locally keep their current
workspace, and the rest are placed under the instance root this machine already
uses.

Restore validates the archive format and paths before writing anything. It
overwrites matching files but does not delete unrelated files already present
at the destination. When current Maia data exists, the command first
creates a `maia-pre-restore-*.zip` rollback archive beside the selected backup.

For unattended scripts, pass `--yes` to acknowledge overwrites.
