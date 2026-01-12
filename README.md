# MCP Personal Finance Manager

A specialized Model Context Protocol (MCP) server for personal finance analysis. It allows AI agents to read, query, and analyze financial transaction data from CSV files, providing intelligent insights into income, expenses, and spending habits.

Now supports **AWS Serverless Deployment** for accessing financial tools via a secure HTTP API.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Architecture](#project-architecture)
- [Prerequisites](#prerequisites)
- [Installation & Setup (Local)](#installation--setup-local)
- [AWS Deployment](#aws-deployment)
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

- **CSV Data Ingestion**: Automatically reads and cleans financial data from `pfm-gio.csv` (Local) or S3 (AWS).
- **Intelligent Parsing**: Handles mixed date formats (ISO and LatAm DD/MM/YYYY) and currency cleaning.
- **Financial Tools**:
  - **`calculate_totals`**: Aggregates income, expenses, and balance by year, month, or category.
  - **`list_transactions`**: Retrieves specific transactions with filtering options.
- **Dual Modes**:
  - **Local MCP**: Standard stdio-based server for local agents (Claude, IDEs).
  - **AWS Serverless**: REST API via API Gateway + Lambda for remote integrations (Custom GPTs, Telegram).

## 🏗️ Project Architecture

```text
┌─────────────────┐                                   ┌────────────────────┐
│   Local Client  │                                   │   Remote Client    │
│ (Claude / IDE)  │                                   │ (Custom GPT / App) │
└────────┬────────┘                                   └─────────┬──────────┘
         │ stdio                                                │ HTTPS
         ▼                                                      ▼
┌─────────────────┐                                   ┌────────────────────┐
│    server.py    │ (Local)                           │    API Gateway     │
│    (FastMCP)    │                                   └─────────┬──────────┘
└────────┬────────┘                                             │
         │                                                      ▼
         │                                            ┌────────────────────┐
         │                                            │     AWS Lambda     │
         │                                            │ (app.py / tools.py)│
         │                                            └──────┬──────┬──────┘
         │                                                   │      │
         │                                       S3 API      │      │ Azure SDK
         │           ┌───────────────────────────────────────┘      │
         │           │                                              │
         ▼           ▼                                              ▼
    [pfm-gio.csv] (File/S3)                                    [GitHub Models]
                                                                  (GPT-4o)
```

## 🔧 Prerequisites

**For Local Development:**

- **Python 3.10+**
- **GitHub Personal Access Token** (for Azure AI via GitHub Models)

**For AWS Deployment:**

- **AWS CLI** (configured with Administrator access)
- **AWS SAM CLI** (for building and deploying serverless resources)
- **GitHub Actions** (enabled on the repository)

## 🚀 Installation & Setup (Local)

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

4. **Configure Environment**
   Create a `.env` file within the root directory:

   ```bash
   cp .env.example .env
   # Add GITHUB_TOKEN=your_token_here
   ```

## ☁️ AWS Deployment

This project uses **AWS SAM** and **GitHub Actions** to deploy a serverless stack (API Gateway + Lambda).

1. **Configure GitHub Secrets**
   Go to your repository settings > Secrets and variables > Actions, and add:
   - `AWS_ACCESS_KEY_ID`: Your AWS Access Key.
   - `AWS_SECRET_ACCESS_KEY`: Your AWS Secret Key.
   - `API_KEY_SECRET`: A strong random string (used to secure the API).

2. **Deploy via Git**
   Push changes to the `main` branch. The workflow in `.github/workflows/deploy.yml` will:
   - Build the Lambda function (`aws-deploy` folder).
   - Deploy the CloudFormation stack (`mcp-finance-stack`).
   - Create/Update the S3 bucket for data.

3. **Upload Data**
   After deployment, note the `DataBucketName` from the CloudFormation outputs (or check the S3 console). Upload your financial data file:

   ```bash
   aws s3 cp pfm-gio.csv s3://<your-deployed-bucket-name>/pfm-gio.csv
   ```

## 💻 Usage

### 1. Local Mode (MCP Server)

Run the MCP server in development mode.

```bash
mcp dev server.py
# Or run the client interface
python client.py
```

### 2. AWS Mode (REST API)

The deployed API exposes the tools via HTTP POST requests. You must include the `x-api-key` header matching your `API_KEY_SECRET`.

**Endpoint Structure:**
`POST https://<api-id>.execute-api.us-east-1.amazonaws.com/Prod/tools/{tool_name}`

**Example: Calculate Totals**

```bash
curl -X POST https://<your-api-url>/Prod/tools/calculate_totals \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_SECRET_KEY" \
  -d '{"year": 2025}'
```

**Example: List Transactions**

```bash
curl -X POST https://<your-api-url>/Prod/tools/list_transactions \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_SECRET_KEY" \
  -d '{"limit": 5, "category": "Food"}'
```

## 🛠️ Tools & Resources

### Tools (Functions)

- **`calculate_totals(year, month, category)`**
  - Returns: `income`, `expenses`, `balance`, `transaction_count`.
- **`list_transactions(limit, category, start_date)`**
  - Returns: List of transaction objects.

### Resources

- **`financial://transactions`** (Local Only)
  - Provides the full dataset for direct context reading.

## ⚙️ Configuration

| Variable | Description | Context |
|----------|-------------|---------|
| `GITHUB_TOKEN` | Token for Azure AI / GitHub Models. | Local |
| `DATA_BUCKET` | Name of the S3 bucket containing CSV data. | AWS (Lambda) |
| `API_KEY_SECRET` | Secret key for authenticating API requests. | AWS (Lambda) |
| `TZ` | Timezone setting (e.g., `America/Bogota`). | AWS (Lambda) |

## 🐛 Troubleshooting

### Local

- **"GITHUB_TOKEN not set"**: Ensure `.env` exists and `python-dotenv` is installed.
- **Parsing Errors**: Check `pfm-gio.csv` format compatibility (ISO or DD/MM/YYYY).

### AWS

- **"Forbidden: Invalid API Key"**: Ensure you are sending the `x-api-key` header matching the GitHub Secret.
- **"Error loading S3 data"**:
  - Check if the S3 bucket name is correctly set in the Lambda environment variables.
  - Ensure `pfm-gio.csv` exists in the root of that bucket.
