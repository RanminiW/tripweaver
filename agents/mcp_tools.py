import os
from langchain_mcp_adapters.client import MultiServerMCPClient
import json

MCP_SERVERS = {
    "hotel": {
        "url": os.environ.get("HOTEL_SERVICE_URL", "http://localhost:8001/mcp"),
        "transport": "streamable_http",
    },
    "flight": {
        "url": os.environ.get("FLIGHT_SERVICE_URL", "http://localhost:8000/mcp"),
        "transport": "streamable_http",
    },
}

_tools_cache: dict = {}

async def init_mcp_tools():
    """Call once at app startup. Populates the tool cache."""
    global _tools_cache
    client = MultiServerMCPClient(MCP_SERVERS)
    hotel_tools = await client.get_tools(server_name="hotel")
    flight_tools = await client.get_tools(server_name="flight")
    _tools_cache = {t.name: t for t in hotel_tools + flight_tools}

def get_tool(name: str):
    tool = _tools_cache.get(name)
    if tool is None:
        raise RuntimeError(f"MCP tool '{name}' is not available")
    return tool

def parse_mcp_result(result):
    """
    MCP tool results come back as a list of content blocks like:
    [{"type": "text", "text": "<json string>"}, ...]
    This unwraps them into plain dicts.
    """
    if not isinstance(result, list):
        return result

    parsed = []
    for item in result:
        if isinstance(item, dict) and item.get("type") == "text":
            try:
                parsed.append(json.loads(item["text"]))
            except (json.JSONDecodeError, TypeError):
                continue
        else:
            parsed.append(item)
    return parsed