# Introduction

**Maia** is a local agent forked from [CowAgent](https://github.com/zhayujie/CowAgent) (MIT, Copyright (c) 2022 zhayujie, © 2026 dubhagen). Chat runs in the web console. The local terminal is also available. Every model call goes to one LiteLLM endpoint. The current version is 0.99.0.

- [GitHub](https://github.com/dubhagen/Maia) — Source repository

## Core Capabilities

- [Autonomous Task Planning](./architecture.md) — Decomposes complex tasks and executes them step by step, looping over tools and skills until the goal is reached.

- [Long-term Memory](../memory/index.md) — Three-tier architecture (context → daily → core), automatic Deep Dream distillation, hybrid keyword + vector retrieval.

- [Personal Knowledge Base](../knowledge/index.md) — Auto-curates structured knowledge into a Markdown wiki, builds an evolving knowledge graph with visual browsing.

- [Self-Evolution](../memory/self-evolution.md) — Reviews conversations automatically to improve skills, follow up on unfinished tasks, and consolidate memory and knowledge, growing through everyday use.

- [Skills System](../skills/index.md) — A complete skill creation and execution engine. Install a skill from a git URL you type, or generate one in conversation.

- [Tool System](../tools/index.md) — Built-in file I/O, terminal, browser, scheduler, memory retrieval, web search, and more — with native MCP integration.

- [Command System](../cli/index.md) — Terminal CLI and in-chat commands for process management, skill installation, configuration, and context inspection.

- [Pluggable Models](../models/index.md) — Every model id is sent to one LiteLLM endpoint. Pick the id in the Web console.

- [Web console and terminal](../channels/index.md) — Chat in the web console. A local terminal channel is also available.

- [Multi-Agent Teams](../multi-agent/team.md) — Create multiple Agents with distinct roles to form a team, with group-chat collaboration, task delegation, and sub-Agents in the web console, the desktop client, and the local terminal.

## Quick Start

Run one of the commands below to install, configure, and start Maia in a single step:

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

### Docker

```bash
git clone https://github.com/dubhagen/Maia.git
cd Maia
docker compose -f docker/docker-compose.yml up -d --build
```

Once started, open `http://localhost:9899` to access the **Web console** — chat, set the LiteLLM base URL, and install skills from a git URL.

- [Quick Start](../guide/quick-start.md) — Complete installation and run guide

- [Architecture](./architecture.md) — How the process is put together

## Disclaimer

1. This project is licensed under the [MIT License](https://github.com/dubhagen/Maia/blob/master/LICENSE). The notices are Copyright (c) 2022 zhayujie and © 2026 dubhagen. You are responsible for complying with applicable laws and regulations in your jurisdiction; the maintainers assume no liability for any consequences arising from use of this project.
2. **Cost & safety:** Agent mode consumes substantially more tokens than plain chat — pick models that balance quality and cost. The Agent has access to your local operating system; deploy only in trusted environments.
3. Maia does not participate in, authorize, or issue any cryptocurrency.

## Community

Questions and changes go to [GitHub issues](https://github.com/dubhagen/Maia/issues).
