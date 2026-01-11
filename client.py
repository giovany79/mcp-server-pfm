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

def call_llm(messages, functions):
    token = os.getenv("GITHUB_TOKEN")
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
        messages=messages,
        model=model_name,
        tools=functions,
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
            functions_to_call.append({ "name": name, "args": args, "id": tool_call.id })

    return functions_to_call, response_message

def call_llm_final(messages, functions):
    # Reuse call_llm but just return content
    _, response_message = call_llm(messages, functions)
    return response_message.content

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

            # Discover capabilities
            tools = await session.list_tools()
            
            # Prepare tools for LLM
            llm_tools = [convert_to_llm_tool(tool) for tool in tools.tools]
            print(f"Connected to MCP Server. Available tools: {[t.name for t in tools.tools]}")
            
            # Interactive loop
            while True:
                try:
                    user_input = input("\nQuery (or 'quit' to exit): ")
                    if user_input.lower() in ['quit', 'exit']:
                        break
                        
                    # 1. Call LLM with user query
                    # Provide the list of valid categories for better mapping
                    valid_categories = [
                        'health', 'pasive incomes', 'solidarity', 'entertainment', 'food', 
                        'restaurant', 'vehicle', 'education', 'loan', 'parents', 'public services', 
                        'other', 'internet help', 'salary', 'Saving', 'pension', 'Taxes', 
                        'personal presentation', 'home', 'gift', 'imprevistos', 'clothes', 'pet'
                    ]
                    
                    system_prompt = (
                        "You are a helpful financial assistant. Use the provided tools to analyze the user's financial data. "
                        "Always summarize the results found by the tools.\n\n"
                        "IMPORTANT: The database uses the following categories in ENGLISH:\n"
                        f"{', '.join(valid_categories)}.\n"
                        "If the user asks in Spanish (or any other language), you MUST translate the category to the closest match "
                        "in the English list above when calling the tools. "
                        "Example: 'comida' -> 'food' or 'restaurant', 'transporte' -> 'vehicle'.\n\n"
                        "TOOL USAGE GUIDELINES:\n"
                        "1. When listing transactions for a specific month/year, ALWAYS use the 'year' and 'month' parameters of 'list_transactions' instead of 'start_date'. This prevents future data from interfering (e.g. 2026 data appearing when asking for 2025).\n"
                        "2. The default limit is 10. If the user asks for 'all' transactions or implies a full list, set the 'limit' parameter to a higher value (e.g., 50 or 100) to ensure complete results."
                    )

                    messages = [
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": user_input
                        }
                    ]
                    
                    # Initial call to get tool calls
                    functions_to_call, original_response = call_llm(messages, llm_tools)
                    
                    # Loop while the LLM wants to call tools
                    while functions_to_call:
                        # Add assistant's message (with tool calls) to history
                        messages.append({
                            "role": "assistant",
                            "tool_calls": original_response.tool_calls
                        })
                        
                        for f in functions_to_call:
                            print(f"Executing tool: {f['name']} with args: {f['args']}")
                            
                            try:
                                result = await session.call_tool(f["name"], arguments=f["args"])
                                result_content = result.content[0].text if result.content else str(result)
                                
                                # Add tool result to messages
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": f["id"],
                                    "content": result_content
                                })
                            except Exception as e:
                                print(f"Error executing tool {f['name']}: {e}")
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": f["id"],
                                    "content": f"Error: {str(e)}"
                                })
                        
                        # Call LLM again with tool outputs
                        # It might return MORE tool calls or the final answer
                        functions_to_call, original_response = call_llm(messages, llm_tools)
                    
                    # No more tool calls, print final response
                    print("\nAssistant:", original_response.content)

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"An error occurred: {e}")

if __name__ == "__main__":
    import asyncio

    asyncio.run(run())