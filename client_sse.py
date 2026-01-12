import asyncio
import sys
from mcp import ClientSession, SseServerParameters
from mcp.client.sse import sse_client
from dotenv import load_dotenv

load_dotenv()

async def run(url: str):
    print(f"Connecting to SSE endpoint: {url}")
    
    # SSE connection parameters
    params = SseServerParameters(
        url=url,
    )

    try:
        async with sse_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # 1. List Tools
                print("\n--- Listing Tools ---")
                tools = await session.list_tools()
                for tool in tools.tools:
                    print(f"- {tool.name}: {tool.description}")

                # 2. Test Execution (calculate_totals)
                print("\n--- Testing Tool: calculate_totals ---")
                # Using a test year (adjust if needed)
                test_args = {"year": 2025, "month": 1}
                print(f"Calling calculate_totals with {test_args}...")
                
                try:
                    result = await session.call_tool("calculate_totals", arguments=test_args)
                    print("Result:")
                    print(result.content[0].text)
                except Exception as e:
                    print(f"Tool execution failed: {e}")

    except Exception as e:
        print(f"\nConnection failed: {e}")
        print("Ensure the server is running and the URL is correct.")

if __name__ == "__main__":
    # Default to local uvicorn URL if not provided
    # AWS URL would be passed as argument
    target_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/sse"
    asyncio.run(run(target_url))
