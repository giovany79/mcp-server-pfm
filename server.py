# server.py
from mcp.server.fastmcp import FastMCP

# Create an MCP Server
mcp = FastMCP("Demo")

# Add an additional tool
@mcp.tool()
def add(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y

# Add a static greeting resource
@mcp.resource("greeting://hello")
def greet() -> str:
    """Get a personalized greeting message."""
    return "Hello, World!"

# Run the server
if __name__ == "__main__":
    mcp.run()