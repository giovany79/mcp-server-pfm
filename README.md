# MCP Personal Finance Manager

A specialized Model Context Protocol (MCP) server for personal finance analysis. It allows AI agents to read, query, and analyze financial transaction data from CSV files, providing intelligent insights into income, expenses, and spending habits.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Architecture](#project-architecture)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Usage](#usage)
- [Tools & Resources](#tools--resources)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

This project implements a custom MCP server that bridges the gap between raw financial data (CSV) and LLMs (like GPT-4o). It enables natural language queries such as:

> "What were my total expenses in 2025?"
> "List my last 5 restaurant transactions."
> "How much did I spend on education in January?"

## ✨ Features

- **CSV Data Ingestion**: Automatically reads and cleans financial data from `pfm-gio.csv`.
- **Intelligent Parsing**: Handles mixed date formats (ISO and LatAm DD/MM/YYYY) and currency cleaning.
- **Financial Tools**:
  - **`calculate_totals`**: Aggregates income, expenses, and balance by year, month, or category.
  - **`list_transactions`**: Retrieves specific transactions with filtering options.
- **Interactive Client**: A Python-based chat interface that maintains context and executes tools dynamically.
- **Pandas Integration**: Uses powerful dataframes for efficient querying.

## 🏗️ Project Architecture

```text
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   client.py     │────────▶│   server.py      │────────▶│  Azure AI       │
│  (Chat Interface)│  stdio │ (FastMCP + Pandas)│   API   │  (GPT-4o)       │
│                 │◀────────│ [pfm-gio.csv]    │◀────────│                 │
└─────────────────┘         └──────────────────┘         └─────────────────┘
       │                            │
       │                            ├─ Tool: calculate_totals()
       │                            ├─ Tool: list_transactions()
       │                            └─ Resource: financial://transactions
       │
       └─ User asks natural language question
       └─ Client sends query to LLM
       └─ LLM requests tool execution
       └─ Client runs tool on Server and returns result
```

## 🔧 Prerequisites

- **Python 3.10+**
- **Node.js** (optional, for MCP Inspector)
- **GitHub Personal Access Token** (for Azure AI via GitHub Models)

## 🚀 Installation & Setup

1. **Clone the Repository**

   ```bash
   git clone <repository-url>
   cd mcp-server-pfm
   ```

2. **Create Virtual Environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   *Note: Requires `pandas`, `fastmcp`, `mcp[cli]`, `azure-ai-inference`, `python-dotenv`.*

4. **Configure Environment**
   Create a `.env` file with your GitHub Token:

   ```bash
   cp .env.example .env
   # Add GITHUB_TOKEN=your_token_here in .env
   ```

## 💻 Usage

### 1. Start the Server

Run the MCP server in development mode. It will listen for incoming stdio connections.

```bash
mcp dev server.py
```

### 2. Run the Client

In a separate terminal (with `venv` activated), start the interactive chat client:

```bash
python client.py
```

### 3. Ask Questions

Once the client is running, you can type queries like:

- *Me puedes decir el total de ingresos y gastos para el 2025?*
- *Cuanto gasté en restaurantes el mes pasado?*
- *Dame el detalle de los gastos de educación.*

Type `quit` or `exit` to stop.

## 🛠️ Tools & Resources

### Tools (Functions)

These are exposed to the LLM:

- **`calculate_totals(year, month, category)`**
  - Returns `income`, `expenses`, `balance`, and `transaction_count`.
  - Useful for aggregation and high-level summaries.

- **`list_transactions(limit, category, start_date)`**
  - Returns raw transaction rows (JSON).
  - Useful for finding specific details or listing recent activity.

### Resources (Data)

- **`financial://transactions`**:
  - Provides the full dataset in JSON format.
  - Can be read by MCP clients for full-context analysis (if within token limits).

## 🐛 Troubleshooting

### Date Parsing Errors

If the server fails to read specific dates, ensure your CSV uses consistently recognizable formats. The server currently supports mixed ISO (`YYYY-MM-DD`) and Day-First (`DD/MM/YYYY`) formats.

### "GITHUB_TOKEN not set"

Make sure your `.env` file exists and `python-dotenv` is installed.

### Server Connection Failed

Ensure `mcp dev server.py` is running in one terminal BEFORE starting `python client.py`.
