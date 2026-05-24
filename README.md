# MCP Personal Finance Manager

A specialized Model Context Protocol (MCP) server for personal finance analysis and transaction management. It allows AI agents to read, query, analyze, create, update, and delete financial transaction data from CSV files, providing intelligent insights into income, expenses, balances, categories, and spending habits.

Now supports **AWS Serverless Deployment** for accessing financial tools via a secure HTTP API, including **ChatGPT Actions** via OpenAPI. The local and AWS versions share the same core finance operations, with local data stored in `pfm-gio.csv` and AWS data stored in S3.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Architecture](#project-architecture)
- [Prerequisites](#prerequisites)
- [Installation & Setup (Local)](#installation--setup-local)
- [AWS Deployment](#aws-deployment)
- [Usage](#usage)
- [Data Format](#data-format)
- [Tools & Resources](#tools--resources)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

This project implements a custom MCP server that bridges the gap between raw financial data (CSV) and LLMs (like GPT-4o). It enables natural language queries such as:

> "What were my total expenses in 2025?"
> "List my last 5 restaurant transactions."
> "How much did I spend on education in January?"
> "Add this restaurant expense for today."
> "Update this transaction category."

## ✨ Features

- **CSV Data Ingestion**: Automatically reads and cleans financial data from `pfm-gio.csv` (Local) or S3 (AWS).
- **Intelligent Parsing**: Handles mixed date formats (ISO and LatAm DD/MM/YYYY) and currency cleaning.
- **Stable Transaction IDs**: Automatically adds and maintains a `transaction_id` column when missing, enabling safe updates and deletes.
- **Financial Tools**:
  - **`calculate_totals`**: Aggregates income, expenses, and balance by year, month, or category.
  - **`list_transactions`**: Retrieves specific transactions with filters for category, date range, year, month, day, and limit.
  - **`expenses_by_category`**: Aggregates expenses grouped by category for a given year/month.
  - **`expenses_by_month_for_category`**: Aggregates monthly expenses for one category.
  - **`add_transaction`**: Adds a single income or expense.
  - **`add_transactions_batch`**: Adds multiple transactions in one operation, up to 20 per batch.
  - **`update_transaction`**: Updates an existing transaction by `transaction_id`.
  - **`delete_transaction`**: Deletes an existing transaction by `transaction_id`.
- **Dual Modes**:
  - **Local MCP**: Standard stdio-based server for local agents (Claude, IDEs).
  - **AWS Serverless**: REST API via API Gateway + Lambda for remote integrations (Custom GPTs, ChatGPT Actions, Telegram).
- **Assistant Instructions**: Includes `instructions.md` with recommended assistant behavior, category mapping, confirmation rules for mutations, and payroll slip extraction guidance.

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

   The Lambda will read and write `pfm-gio.csv` in this bucket. Mutation tools such as `add_transaction`, `update_transaction`, and `delete_transaction` persist changes back to S3.

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

**Example: Expenses by Category**

```bash
curl -X POST https://<your-api-url>/Prod/tools/expenses_by_category \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_SECRET_KEY" \
  -d '{"year": 2025, "month": 3}'
```

**Example: Expenses by Month for a Category**

```bash
curl -X POST https://<your-api-url>/Prod/tools/expenses_by_month_for_category \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_SECRET_KEY" \
  -d '{"category": "restaurant", "year": 2025}'
```

**Example: Add Transaction**

```bash
curl -X POST https://<your-api-url>/Prod/tools/add_transaction \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_SECRET_KEY" \
  -d '{
    "description": "Coffee",
    "transaction_type": "expensive",
    "amount": 12000,
    "category": "restaurant",
    "date": "2025-03-15"
  }'
```

**Example: Add Transactions Batch**

```bash
curl -X POST https://<your-api-url>/Prod/tools/add_transactions_batch \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_SECRET_KEY" \
  -d '{
    "transactions": [
      {
        "description": "Lunch",
        "transaction_type": "expensive",
        "amount": 28000,
        "category": "restaurant",
        "date": "2025-03-15"
      },
      {
        "description": "Book",
        "transaction_type": "expensive",
        "amount": 45000,
        "category": "education",
        "date": "2025-03-16"
      }
    ]
  }'
```

**Example: Update Transaction**

```bash
curl -X POST https://<your-api-url>/Prod/tools/update_transaction \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_SECRET_KEY" \
  -d '{
    "transaction_id": "TRANSACTION_UUID",
    "category": "food",
    "amount": 30000
  }'
```

**Example: Delete Transaction**

```bash
curl -X POST https://<your-api-url>/Prod/tools/delete_transaction \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_SECRET_KEY" \
  -d '{"transaction_id": "TRANSACTION_UUID"}'
```

### 3. ChatGPT Actions (OpenAPI)

Use `aws-deploy/chatgpt_openapi.yaml` in the ChatGPT Actions console. It is OpenAPI **3.1.0** and includes `x-api-key` auth in `components.securitySchemes`.

**Important:**
- Base URL must match your API Gateway stage: `https://<api-id>.execute-api.us-east-1.amazonaws.com/Prod/tools`
- All operations are `POST` and require `Content-Type: application/json` and `x-api-key` (when `API_KEY_SECRET` is set).
- `list_transactions` returns a **JSON array** of transaction objects (not a JSON string).
- `expenses_by_category` returns a **JSON array** of `{ category, total }`.
- Mutation operations require a valid payload and persist changes to the backing CSV (`pfm-gio.csv` locally or S3 in AWS).
- Use `instructions.md` as the assistant prompt when connecting a Custom GPT. It includes confirmation requirements before any create, update, or delete operation.

## 📄 Data Format

The finance dataset is a semicolon-delimited CSV. Required columns:

| Column | Description |
|--------|-------------|
| `Description` | Human-readable transaction description. |
| `Income/expensive` | Transaction type. Must be `income` or `expensive`. |
| `Amount` | Positive numeric amount. Colombian currency formatting is cleaned when possible. |
| `Category` | Category name, usually stored in English. |
| `Date` | Transaction date. Mixed formats are supported and normalized when persisted. |

Optional but recommended:

| Column | Description |
|--------|-------------|
| `transaction_id` | Stable UUID used for updates and deletes. If missing or empty, it is generated automatically. |

When the server normalizes data, it saves dates as `YYYY-MM-DD` and writes columns in this order when present:

```text
transaction_id;Description;Income/expensive;Amount;Category;Date
```

## 🛠️ Tools & Resources

### Tools (Functions)

- **`calculate_totals(year, month, category)`**
  - Returns: `income`, `expenses`, `balance`, `transaction_count`.
- **`list_transactions(limit, category, start_date, end_date, year, month, day)`**
  - Returns: List of transaction objects.
- **`expenses_by_category(year, month)`**
  - Returns: List of `{ category, total }` objects (JSON array).
- **`expenses_by_month_for_category(category, year)`**
  - Returns: List of `{ month, total }` objects.
- **`add_transaction(description, transaction_type, amount, category, date)`**
  - Adds a single transaction and returns the created transaction, including `transaction_id`.
- **`add_transactions_batch(transactions)`**
  - Adds up to 20 transactions and returns the created transactions.
- **`update_transaction(transaction_id, description, transaction_type, amount, category, date)`**
  - Updates one or more fields on an existing transaction.
- **`delete_transaction(transaction_id)`**
  - Deletes a transaction and returns the deleted transaction.

### Resources

- **`financial://transactions`** (Local Only)
  - Provides the full dataset for direct context reading.

## ⚙️ Configuration

| Variable | Description | Context |
|----------|-------------|---------|
| `GITHUB_TOKEN` | Token for Azure AI / GitHub Models. | Local |
| `DATA_BUCKET` | Name of the S3 bucket containing CSV data. | AWS (Lambda) |
| `API_KEY_SECRET` | Secret key for authenticating API requests. | AWS (Lambda) |
| `CHAT_HISTORY_TABLE` | DynamoDB table name reserved for chat history. | AWS (Lambda) |
| `TZ` | Timezone setting (e.g., `America/Bogota`). | AWS (Lambda) |

## 🐛 Troubleshooting

### Local

- **"GITHUB_TOKEN not set"**: Ensure `.env` exists and `python-dotenv` is installed.
- **Parsing Errors**: Check `pfm-gio.csv` format compatibility (ISO or DD/MM/YYYY).
- **Unexpected CSV changes**: The server may persist normalized dates and generated `transaction_id` values back to `pfm-gio.csv`.
- **Transaction update/delete fails**: Call `list_transactions` first and use the returned `transaction_id`.

### AWS

- **"Forbidden: Invalid API Key"**: Ensure you are sending the `x-api-key` header matching the GitHub Secret.
- **"Error loading S3 data"**:
  - Check if the S3 bucket name is correctly set in the Lambda environment variables.
  - Ensure `pfm-gio.csv` exists in the root of that bucket.
- **Mutation does not appear in later requests**:
  - Confirm the Lambda has S3 write permission.
  - Confirm the request used the correct deployed API and bucket.
  - Check CloudWatch logs for validation errors.
