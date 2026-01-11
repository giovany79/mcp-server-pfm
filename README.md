# MCP Server for Personal Finance Management

A Model Context Protocol (MCP) server implementation that demonstrates how to create custom tools and resources for AI agents, with integration to Azure AI Inference using GitHub Models.

## 📋 Table of Contents

- [Overview](#overview)
- [What is MCP?](#what-is-mcp)
- [Project Architecture](#project-architecture)
- [Project Files](#project-files)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Usage](#usage)
- [Configuration](#configuration)
- [Development](#development)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

This project demonstrates a complete MCP (Model Context Protocol) implementation that:

- Creates a custom MCP server with tools and resources
- Connects an AI client (GPT-4o via Azure AI) to the MCP server
- Enables the AI to discover and use server-provided tools dynamically
- Showcases the integration between MCP and Large Language Models

## 🤔 What is MCP?

**MCP (Model Context Protocol)** is an open protocol that standardizes how applications provide context to Large Language Models (LLMs). It enables:

- **Tools**: Functions that LLMs can call to perform actions
- **Resources**: Static or dynamic data that LLMs can access
- **Prompts**: Reusable prompt templates
- **Sampling**: LLM interaction capabilities

Learn more at the [official MCP documentation](https://modelcontextprotocol.io/).

## 🏗️ Project Architecture

```text
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   client.py     │────────▶│   server.py      │────────▶│  Azure AI       │
│  (MCP Client)   │  stdio  │  (MCP Server)    │   API   │  (GPT-4o)       │
│                 │◀────────│                  │◀────────│                 │
└─────────────────┘         └──────────────────┘         └─────────────────┘
       │                            │
       │                            ├─ Tool: add()
       │                            └─ Resource: greeting://hello
       │
       └─ Discovers tools & resources
       └─ Calls LLM with available tools
       └─ Executes tool calls via MCP
```

## 📁 Project Files

### Core Files

- **`server.py`** - MCP server implementation using FastMCP
  - Defines custom tools (e.g., `add` function)
  - Exposes resources (e.g., greeting message)
  - Runs the MCP server that clients can connect to

- **`client.py`** - MCP client with Azure AI integration
  - Connects to the MCP server via stdio
  - Lists available tools and resources
  - Integrates with Azure AI Inference (GPT-4o)
  - Demonstrates AI-driven tool calling

### Configuration Files

- **`requirements.txt`** - Python dependencies
  - `fastmcp` - Fast MCP server framework
  - `mcp[cli]` - MCP CLI tools
  - `azure-ai-inference` - Azure AI SDK
  - `python-dotenv` - Environment variable management

- **`.env.example`** - Template for environment variables
  - Shows required configuration format
  - Copy to `.env` and fill with actual values

- **`.env`** - Environment variables (git-ignored)
  - Contains sensitive data like `GITHUB_TOKEN`
  - Required for Azure AI authentication

- **`.gitignore`** - Git ignore rules
  - Excludes virtual environments, cache files
  - Protects sensitive files like `.env`
  - Standard Python gitignore patterns

## 🔧 Prerequisites

- **Python 3.8+** installed on your system
- **Node.js** (for MCP inspector tool)
- **GitHub Personal Access Token** with access to GitHub Models
- **Git** for version control

## 🚀 Installation & Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd mcp-server-pfm
```

### 2. Create Python Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install MCP CLI Tools

```bash
pip install "mcp[cli]"
```

### 5. Install UV (Optional Package Manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 6. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your GitHub token
# GITHUB_TOKEN=your_actual_github_token_here
```

**To get a GitHub token:**

1. Go to [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
2. Generate a new token (classic)
3. Copy the token and paste it in your `.env` file

## 💻 Usage

### Running the MCP Server

Start the server in development mode:

```bash
mcp dev server.py
```

The server will start and listen for client connections.

### Running the MCP Inspector

The inspector provides a web UI to test your MCP server:

```bash
npx @modelcontextprotocol/inspector mcp run server.py
```

This opens a browser interface where you can:

- View available tools and resources
- Test tool calls interactively
- Inspect server responses

### Running the Client

Execute the client to see the full integration:

```bash
python client.py
```

The client will:

1. Connect to the MCP server
2. List available resources and tools
3. Read a resource (`greeting://hello`)
4. Call a tool directly (`add(17, 7)`)
5. Send a prompt to GPT-4o with available tools
6. Execute the AI's tool calls via MCP

**Expected Output:**

```
LISTING RESOURCES
Resource: greeting://hello

LISTING TOOLS
Tool: add

READING RESOURCE
Hello, World!

CALL TOOL
24

CALLING LLM
TOOL: add(x=2, y=20)
TOOLS result: 22
```

## ⚙️ Configuration

### Environment Variables

| Variable       | Description                                  | Required |
|----------------|----------------------------------------------|----------|
| `GITHUB_TOKEN` | GitHub Personal Access Token for Azure AI    | Yes      |

### Server Configuration

Edit `server.py` to:

- Add new tools with the `@mcp.tool()` decorator
- Add new resources with the `@mcp.resource()` decorator
- Customize the server name (currently "Demo")

### Client Configuration

Edit `client.py` to:

- Change the AI model (default: `gpt-4o`)
- Modify prompts and test cases
- Adjust temperature and token limits

## 🛠️ Development

### Adding a New Tool

```python
@mcp.tool()
def my_custom_tool(param1: str, param2: int) -> str:
    """Description of what this tool does."""
    return f"Result: {param1} - {param2}"
```

### Adding a New Resource

```python
@mcp.resource("custom://my-resource")
def my_resource() -> str:
    """Description of this resource."""
    return "Resource content"
```

### Updating Dependencies

```bash
pip install --upgrade pip && pip install -r requirements.txt
```

### Testing Changes

1. Restart the MCP server
2. Run the client to test integration
3. Use the inspector for interactive testing

## 🔒 Security

- **Never commit `.env` files** - They contain sensitive tokens
- **Use environment variables** for all secrets
- **Rotate tokens regularly** - Update your GitHub token periodically
- **Limit token permissions** - Only grant necessary scopes
- **Review `.gitignore`** - Ensure sensitive files are excluded

## 🐛 Troubleshooting

### "GITHUB_TOKEN environment variable is not set"

**Solution:** Ensure you've created a `.env` file with your token:

```bash
cp .env.example .env
# Edit .env and add your token
```

### "Module not found" errors

**Solution:** Activate virtual environment and reinstall dependencies:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Server connection issues

**Solution:** Ensure the server is running before starting the client:

```bash
# Terminal 1
mcp dev server.py

# Terminal 2
python client.py
```

### Azure AI authentication errors

**Solution:** Verify your GitHub token has access to GitHub Models and is correctly set in `.env`

## 📚 Additional Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)
- [Azure AI Inference SDK](https://learn.microsoft.com/en-us/azure/ai-services/)
- [GitHub Models](https://github.com/marketplace/models)

## 📝 License

This project is for personal use and demonstration purposes.

---

**Note:** This is a demonstration project showing MCP integration patterns. For production use, implement proper error handling, logging, and security measures.
