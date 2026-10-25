from agent.tools.base_tool import BaseTool, ToolResult
from common.log import logger


class McpTool(BaseTool):
    """
    Wrap one MCP tool as a BaseTool.
    One MCP server can expose several tools, one McpTool each.
    """

    def __init__(self, client, tool_schema: dict, server_name: str, name_prefix: str = ""):
        """
        :param client: McpClient that owns this tool
        :param tool_schema: Tool description returned by MCP, shaped as:
            {"name": str, "description": str, "inputSchema": dict}
        :param server_name: Server name, used in logs
        """
        self.client = client
        self.server_name = server_name
        # Prefix only the local name; the server still expects its original name.
        self._remote_name = tool_schema["name"]
        self.name = name_prefix + self._remote_name
        self.description = tool_schema.get("description", "")
        self.params = tool_schema.get("inputSchema", {})

    def execute(self, params: dict) -> ToolResult:
        logger.info(f"[McpTool] server={self.server_name} tool={self.name} params={params}")
        try:
            result = self.client.call_tool(self._remote_name, params)
            return ToolResult.success(result)
        except Exception as e:
            logger.error(f"[McpTool] server={self.server_name} tool={self.name} error: {e}")
            return ToolResult.fail(str(e))
