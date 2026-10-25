# Tools Overview

Tools are the core capability for Agent to access operating system resources. The Agent intelligently selects and invokes tools based on task requirements, performing file operations, command execution, web search, scheduled tasks, and more. Tools are implemented in the `agent/tools/` directory.

## Built-in Tools

The following tools are available by default with no extra configuration:

- [read - File Read](./read.md) — Read file content, supports text, images, PDF

- [write - File Write](./write.md) — Create or overwrite files

- [edit - File Edit](./edit.md) — Edit files via precise text replacement

- [ls - Directory List](./ls.md) — List directory contents

- [search_files - File Search](./search-files.md) — Search file contents, or find files by name

- [bash - Terminal](./bash.md) — Execute system commands

- [send - File Send](./send.md) — Send files or images to user

- [memory - Memory](./memory.md) — Search and read long-term memory

- [agent_delegate - Delegation](./delegate.md) — Hand a task to another Agent in the session

- [subagent - Sub-Agent](./subagent.md) — Create temporary sub-Agents to run independent tasks in parallel

## Optional Tools

The following tools require additional dependencies or API key configuration:

- [env_config - Environment](./env-config.md) — Manage API keys and secrets

- [scheduler - Scheduler](./scheduler.md) — Create and manage scheduled tasks

- [web_search - Web Search](./web-search.md) — Search the internet for real-time information

## MCP Tools

Integrate thousands of community tools (maps, GitHub, Notion, etc.) via the [Model Context Protocol](https://modelcontextprotocol.io). Configure `mcp.json` once, ready to use:

- [MCP - External Tool Ecosystem](./mcp.md) — Supports standard stdio / SSE transports. Hot-reload, zero code changes.
