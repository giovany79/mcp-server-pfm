import json
import os
import boto3
from tools import FinanceTools

# Initialize tools once (warm start optimization)
tools = FinanceTools()

def lambda_handler(event, context):
    """
    Main Handler for API Gateway.
    Supports:
    1. POST /tools/{tool_name} -> Direct tool execution (for ChatGPT/OpenAPI)
    2. POST /telegram -> Webhook for Telegram Bot (future implementation)
    """
    path = event.get('path', '')
    http_method = event.get('httpMethod', '')
    
    print(f"Request: {http_method} {path}")
    
    # Enable CORS
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'OPTIONS,POST'
    }
    
    
    if http_method == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}

    # --- SECURITY CHECK ---
    # Verificar que el GPT envíe el secreto correcto
    # En ChatGPT se configura como "API Key" -> "Auth Type: Custom Header" -> "Header Name: x-api-key"
    expected_key = os.environ.get('API_KEY_SECRET')
    incoming_key = event.get('headers', {}).get('x-api-key')
    
    # Solo validamos si la variable de entorno está configurada (para no romper en local/dev si no se quiere)
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
            body = json.loads(event.get('body', '{}'))
            
            result = {}
            if tool_name == 'calculate_totals':
                result = tools.calculate_totals(
                    year=body.get('year'), 
                    month=body.get('month'), 
                    category=body.get('category')
                )
            elif tool_name == 'list_transactions':
                result = tools.list_transactions(
                    limit=body.get('limit', 10),
                    category=body.get('category'),
                    start_date=body.get('start_date'),
                    year=body.get('year'),
                    month=body.get('month')
                )
            else:
                return {'statusCode': 404, 'headers': headers, 'body': json.dumps({'error': 'Tool not found'})}
                
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps(result) if isinstance(result, dict) else result
            }
            
        elif path == '/telegram':
            # --- Telegram Bot Mode (Placeholder) ---
            # Parsing logic for Telegram Update would go here
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({'message': 'Telegram logic not yet implemented'})
            }
            
        else:
            return {'statusCode': 404, 'headers': headers, 'body': json.dumps({'error': 'Path not found'})}

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }
