from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
import json
import os
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

# Load environment variables from .env file
load_dotenv()

server_params = StdioServerParameters(
    command="mcp", 
    args=["run", "server.py"],  
    env=None,
)

def call_llm(prompt, functions):
    token = os.getenv("GITHUB_TOKEN")  # Read token from environment variable
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is not set")
    
    endpoint = "https://models.inference.ai.azure.com"

    model_name = "gpt-4o"

    client = ChatCompletionsClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(token),
    )

    print("CALLING LLM")
    response = client.complete(
        messages=[
            {
            "role": "system",
            "content": "You are a helpful assistant.",
            },
            {
            "role": "user",
            "content": prompt,
            },
        ],
        model=model_name,
        tools = functions,
        temperature=1.,
        max_tokens=1000,
        top_p=1.    
    )

    response_message = response.choices[0].message
    
    functions_to_call = []

    if response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            print("TOOL: ", tool_call)
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            functions_to_call.append({ "name": name, "args": args })

    return functions_to_call

def convert_to_llm_tool(tool):
    tool_schema = {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "type": "function",
            "parameters": {
                "type": "object",
                "properties": tool.inputSchema["properties"]
            }
        }
    }

    return tool_schema

async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(
            read, write
        ) as session:
            await session.initialize()

            resources = await session.list_resources()
            print("LISTING RESOURCES")
            for resource in resources:
                print("Resource: ", resource)

            tools = await session.list_tools()
            print("LISTING TOOLS")
            for tool in tools.tools:
                print("Tool: ", tool.name) 

            print("READING RESOURCE")
            content, mime_type = await session.read_resource("greeting://hello")  

            print("CALL TOOL")
            result = await session.call_tool("add", arguments={"x": 17, "y": 7})
            print(result.content)

            functions = []

            for tool in tools.tools:
                print("Tool: ", tool.name)
                print("Tool", tool.inputSchema["properties"])
                functions.append(convert_to_llm_tool(tool))
            
            prompt = "Add 2 to 20"

            functions_to_call = call_llm(prompt, functions)

            for f in functions_to_call:
                result = await session.call_tool(f["name"], arguments=f["args"])
                print("TOOLS result: ", result.content)
              

if __name__ == "__main__":
    import asyncio

    asyncio.run(run())