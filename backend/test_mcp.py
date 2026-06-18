import asyncio
import os
from dotenv import load_dotenv

load_dotenv("../.env")


async def main():
    from app.clients.mcp_client import build_mcp_server_config
    from langchain_mcp_adapters.client import MultiServerMCPClient

    print("Building server config...")
    servers = await build_mcp_server_config()
    print(f"Servers: {list(servers.keys())}\n")

    print("Loading tools...")
    client = MultiServerMCPClient(servers)
    tools = await client.get_tools()
    print(f"\nTotal tools: {len(tools)}")
    for t in tools:
        print(f"  - {t.name}")


asyncio.run(main())
