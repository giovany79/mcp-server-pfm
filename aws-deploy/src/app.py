import json
import os
import boto3
from tools import FinanceTools
from mcp.server.fastmcp import FastMCP
from mangum import Mangum
from typing import Optional, Dict, List

# Initialize tools once (warm start optimization)
tools = FinanceTools()

# Initialize MCP Server
mcp = FastMCP("Personal Finance Manager")

@mcp.tool()
def calculate_totals(year: Optional[int] = None, month: Optional[int] = None, category: Optional[str] = None) -> Dict[str, float]:
    """Calculate total income, expenses, and balance based on filters."""
    return tools.calculate_totals(year, month, category)

@mcp.tool()
def list_transactions(limit: int = 10, category: Optional[str] = None, start_date: Optional[str] = None, year: Optional[int] = None, month: Optional[int] = None) -> str:
    """List individual transactions matching criteria."""
    return tools.list_transactions(limit, category, start_date, year, month)

@mcp.tool()
def expenses_by_category(year: Optional[int] = None, month: Optional[int] = None) -> List[Dict[str, float]]:
    """Calculate expenses grouped by category for the given year/month."""
    return tools.expenses_by_category(year, month)

@mcp.tool()
def expenses_by_month_for_category(category: str, year: Optional[int] = None) -> List[Dict[str, float]]:
    """Calculate expenses grouped by month for a given category and optional year."""
    return tools.expenses_by_month_for_category(category, year)

@mcp.tool()
def add_transaction(
    description: str,
    transaction_type: str,
    amount: float,
    category: str,
    date: Optional[str] = None
) -> Dict[str, object]:
    """Add a new transaction to the dataset."""
    return tools.add_transaction(description, transaction_type, amount, category, date)

# Initialize Mangum handler for MCP (ASGI)
# This handles the SSE endpoints automatically provided by FastMCP
asgi_handler = Mangum(mcp.sse_app)

def lambda_handler(event, context):
    """
    Main Handler for API Gateway.
    Supports:
    1. MCP Protocol -> /mcp/* handled by Mangum/FastMCP
    2. POST /tools/{tool_name} -> Direct tool execution (Legacy/ChatGPT)
    3. POST /telegram -> Webhook for Telegram Bot
    """
    path = event.get('path', '')
    http_method = event.get('httpMethod', '')
    
    print(f"Request: {http_method} {path}")

    # --- MCP Handler ---
    # Redirect generic MCP paths or explicit /mcp prefix to Mangum
    # Note: Configure API Gateway to route /sse and /messages here, or use /mcp/{proxy+}
    if path.startswith('/mcp') or path in ['/sse', '/messages']:
        return asgi_handler(event, context)

    # --- REST / Legacy Handler ---
    
    # Enable CORS
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'OPTIONS,POST',
        'Content-Type': 'application/json'
    }
    
    if http_method == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}

    # --- SECURITY CHECK ---
    # Verificar que el GPT envíe el secreto correcto
    expected_key = os.environ.get('API_KEY_SECRET')
    incoming_key = event.get('headers', {}).get('x-api-key')
    
    # Solo validamos si la variable de entorno está configurada
    if expected_key and incoming_key != expected_key:
        print(f"Unauthorized: Invalid API Key")
        return {
            'statusCode': 403,
            'headers': headers,
            'body': json.dumps({'error': 'Forbidden: Invalid API Key'})
        }
    # ----------------------

    try:
        if path.startswith('/tools/'):
            # --- ChatGPT / OpenAPI Mode ---
            tool_name = path.split('/')[-1]
            body = json.loads(event.get('body', '{}') or '{}')
            
            result = {}
            if tool_name == 'calculate_totals':
                result = tools.calculate_totals(
                    year=int(body.get('year')) if body.get('year') else None, 
                    month=int(body.get('month')) if body.get('month') else None, 
                    category=body.get('category')
                )
            elif tool_name == 'list_transactions':
                result = tools.list_transactions(
                    limit=int(body.get('limit', 10)),
                    category=body.get('category'),
                    start_date=body.get('start_date'),
                    year=int(body.get('year')) if body.get('year') else None,
                    month=int(body.get('month')) if body.get('month') else None
                )
            elif tool_name == 'expenses_by_category':
                result = tools.expenses_by_category(
                    year=int(body.get('year')) if body.get('year') else None,
                    month=int(body.get('month')) if body.get('month') else None
                )
            elif tool_name == 'expenses_by_month_for_category':
                result = tools.expenses_by_month_for_category(
                    category=body.get('category', ''),
                    year=int(body.get('year')) if body.get('year') else None
                )
            elif tool_name == 'add_transaction':
                result = tools.add_transaction(
                    description=body.get('description', ''),
                    transaction_type=body.get('transaction_type', ''),
                    amount=body.get('amount'),
                    category=body.get('category', ''),
                    date=body.get('date')
                )
            else:
                return {'statusCode': 404, 'headers': headers, 'body': json.dumps({'error': 'Tool not found'})}
                
            body = json.dumps(result) if isinstance(result, (dict, list)) else result
            return {
                'statusCode': 200,
                'headers': headers,
                'body': body
            }
            
        elif path == '/telegram':
            # --- Telegram Bot Mode ---
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({'message': 'Telegram logic not yet implemented'})
            }
            
        else:
            return {'statusCode': 404, 'headers': headers, 'body': json.dumps({'error': 'Path not found'})}

    except Exception as e:
        print(f"Error: {str(e)}")
        # Print stack trace in Lambda logs for debugging
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }
