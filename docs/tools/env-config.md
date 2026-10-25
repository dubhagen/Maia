# env_config - Environment

Manage environment variables (API keys and secrets) in the workspace `.env` file, with secure conversational updates. Built-in security protection and desensitization.

## Dependencies

| Dependency | Install Command |
| --- | --- |
| `python-dotenv` ≥ 1.0.0 | `pip install python-dotenv>=1.0.0` |

Included when installing optional dependencies: `pip3 install -r requirements-optional.txt`

## Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `action` | string | Yes | Operation type: `get`, `set`, `list`, `delete` |
| `key` | string | No | Environment variable name |
| `value` | string | No | Environment variable value (only for `set`) |

## Usage

Tell the Agent what key you need to configure, and it will automatically invoke this tool:

- "Configure my BOCHA_API_KEY"
- "Set OPENAI_API_KEY to sk-xxx"
- "Show configured environment variables"

Configured keys are automatically injected into the `bash` tool's execution environment. The Config page's API key is the LiteLLM credential, not this file.
