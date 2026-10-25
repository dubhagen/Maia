# One-click Install

The project provides scripts for one-click install, configuration, startup, and management. Script-based deployment is recommended for quick setup.

Supports Linux, macOS, and Windows. Requires Python 3.7-3.13 (3.9 recommended).

## Install Command

### Linux / macOS

```bash
git clone https://github.com/dubhagen/Maia.git
cd Maia
bash run.sh
```

### Windows (PowerShell)

```powershell
git clone https://github.com/dubhagen/Maia.git
cd Maia
.\scripts\run.ps1
```

The script automatically performs these steps:

1. Check Python environment (requires Python 3.7+)
2. Install required tools (git, curl, etc.)
3. Clone the project to `~/Maia`
4. Install Python dependencies and Maia CLI
5. Guided configuration for AI model and channel
6. Start service

By default, the Web console starts after installation. Access `http://localhost:9899` to begin chatting.

> **Note.** **Deploying on a server?** By default `web_host` only listens on `127.0.0.1` (local access only). Set `web_host` to `0.0.0.0` in `config.json` to make the console reachable from outside, and set `web_password` to protect it. Don't forget to open port `9899` in your firewall or security group — ideally restricted to specific IPs.

## Management Commands

After installation, use the `maia` command to manage the service:

| Command | Description |
| --- | --- |
| `maia start` | Start service |
| `maia stop` | Stop service |
| `maia restart` | Restart service |
| `maia status` | Check run status |
| `maia logs` | View real-time logs |
| `maia update` | Update code and restart |
| `maia install-browser` | Install browser tool dependencies |

See the [Commands documentation](../cli/index.md) for more details.

> **Note.** If the `maia` command is not available, you can use `./run.sh <command>` (Linux/macOS) or `.\scripts\run.ps1 <command>` (Windows) as a fallback. Both are functionally equivalent.
