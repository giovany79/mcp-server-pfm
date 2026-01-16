from mcp.server.fastmcp import FastMCP
import pandas as pd
from datetime import datetime
from typing import List, Optional, Dict, Any

# Create an MCP Server
mcp = FastMCP("Personal Finance Manager")

DATA_PATH = "pfm-gio.csv"

def load_data() -> pd.DataFrame:
    """Loads and cleans the financial data from CSV."""
    try:
        # Read encoded with utf-8 or latin-1, delimiter is ';'
        df = pd.read_csv(DATA_PATH, sep=";", encoding="utf-8")
        
        # Clean column names (strip spaces)
        df.columns = [c.strip() for c in df.columns]
        
        # Clean Amount column
        # Remove '$', '.', and spaces. 
        # Note: valid for currency format like $1.000.000 (where . is thousand separator)
        if df['Amount'].dtype == 'object':
            df['Amount'] = df['Amount'].astype(str).str.replace(r'[$. ]', '', regex=True)
            df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
            
        # Drop rows where Amount is NaN (invalid or missing)
        df = df.dropna(subset=['Amount'])

        # Convert Date to datetime handling mixed formats (likely DD/MM/YY)
        df['Date'] = pd.to_datetime(df['Date'], format='mixed', dayfirst=True, errors='coerce')
        
        # Drop rows with invalid dates
        df = df.dropna(subset=['Date'])
        
        return df
    except Exception as e:
        raise RuntimeError(f"Error loading data: {str(e)}")

@mcp.resource("financial://transactions")
def get_transactions_resource() -> str:
    """Get the raw transaction data as a JSON string."""
    df = load_data()
    # Convert dates to string for JSON serialization
    return df.to_json(orient="records", date_format="iso")

@mcp.tool()
def calculate_totals(year: Optional[int] = None, month: Optional[int] = None, category: Optional[str] = None) -> Dict[str, float]:
    """
    Calculate total income, expenses, and balance based on filters.
    
    Args:
        year: The year to filter by (e.g., 2025).
        month: The month to filter by (1-12).
        category: The category to filter by (case-insensitive substring match).
    """
    df = load_data()
    
    if year:
        df = df[df['Date'].dt.year == year]
    
    if month:
        df = df[df['Date'].dt.month == month]
        
    if category:
        # Case insensitive filtering
        df = df[df['Category'].str.contains(category, case=False, na=False)]
        
    # Calculate totals
    # Assuming 'Income/expensive' column distinguishes transaction type
    # 'income' vs 'expensive' (based on CSV view)
    
    income = df[df['Income/expensive'].str.lower() == 'income']['Amount'].sum()
    expenses = df[df['Income/expensive'].str.lower() == 'expensive']['Amount'].sum()
    
    balance = income - expenses
    
    return {
        "income": float(income),
        "expenses": float(expenses),
        "balance": float(balance),
        "transaction_count": int(len(df))
    }

@mcp.tool()
def list_transactions(limit: int = 10, category: Optional[str] = None, start_date: Optional[str] = None, year: Optional[int] = None, month: Optional[int] = None) -> str:
    """
    List individual transactions matching criteria.
    
    Args:
        limit: Max number of transactions to return (default 10).
        category: Filter by category name.
        start_date: Filter transactions on or after this date (format YYYY-MM-DD).
        year: Filter by specific year.
        month: Filter by specific month.
    """
    df = load_data()
    
    if year:
        df = df[df['Date'].dt.year == year]
    
    if month:
        df = df[df['Date'].dt.month == month]
    
    if start_date:
        start_dt = pd.to_datetime(start_date)
        df = df[df['Date'] >= start_dt]
        
    if category:
        df = df[df['Category'].str.contains(category, case=False, na=False)]
        
    # Sort by date desc (most recent first)
    df = df.sort_values(by='Date', ascending=False)
    
    result = df.head(limit)
    
    # Return as readable string or JSON
    return result.to_json(orient="records", date_format="iso")

@mcp.tool()
def expenses_by_category(year: Optional[int] = None, month: Optional[int] = None) -> List[Dict[str, float]]:
    """
    Calculate expenses grouped by category for the given year/month.
    
    Args:
        year: The year to filter by (e.g., 2025).
        month: The month to filter by (1-12).
    """
    df = load_data()
    
    if year:
        df = df[df['Date'].dt.year == year]
    
    if month:
        df = df[df['Date'].dt.month == month]
    
    expenses = df[df['Income/expensive'].str.lower() == 'expensive']
    grouped = expenses.groupby('Category', dropna=False)['Amount'].sum().sort_values(ascending=False)
    result = grouped.reset_index().rename(columns={'Category': 'category', 'Amount': 'total'})
    
    return result.to_dict(orient="records")

@mcp.tool()
def expenses_by_month_for_category(category: str, year: Optional[int] = None) -> List[Dict[str, float]]:
    """
    Calculate expenses grouped by month for a given category and optional year.
    
    Args:
        category: The category to filter by (case-insensitive substring match).
        year: The year to filter by (e.g., 2025).
    """
    df = load_data()

    if not category:
        return []
    
    if year:
        df = df[df['Date'].dt.year == year]
    
    expenses = df[df['Income/expensive'].str.lower() == 'expensive']
    expenses = expenses[expenses['Category'].str.contains(category, case=False, na=False)]
    expenses = expenses.assign(month=expenses['Date'].dt.month)
    
    grouped = expenses.groupby('month', dropna=False)['Amount'].sum().sort_index()
    result = grouped.reset_index().rename(columns={'month': 'month', 'Amount': 'total'})
    
    return result.to_dict(orient="records")

@mcp.tool()
def add_transaction(
    description: str,
    transaction_type: str,
    amount: float,
    category: str,
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add a new transaction to the local CSV file.
    
    Args:
        description: Transaction description.
        transaction_type: 'income' or 'expensive'.
        amount: Transaction amount (positive number).
        category: Category name.
        date: Optional date string (YYYY-MM-DD or similar).
    """
    if not description or not description.strip():
        raise ValueError("Description is required")
    if not category or not category.strip():
        raise ValueError("Category is required")
    if not transaction_type or not transaction_type.strip():
        raise ValueError("Transaction type is required")

    normalized_type = transaction_type.strip().lower()
    if normalized_type not in {"income", "expensive"}:
        raise ValueError("Transaction type must be 'income' or 'expensive'")

    try:
        amount_value = float(amount)
    except (TypeError, ValueError):
        raise ValueError("Amount must be a number")

    if amount_value <= 0:
        raise ValueError("Amount must be greater than zero")

    if date:
        try:
            parsed_date = pd.to_datetime(date, format='mixed', dayfirst=True, errors='raise')
        except (TypeError, ValueError):
            raise ValueError("Date must be a valid date string")
    else:
        parsed_date = pd.to_datetime(datetime.now().date())

    df = load_data()
    new_row = {
        "Description": description.strip(),
        "Income/expensive": normalized_type,
        "Amount": amount_value,
        "Category": category.strip(),
        "Date": parsed_date
    }

    updated = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    updated = updated[["Description", "Income/expensive", "Amount", "Category", "Date"]]
    updated.to_csv(DATA_PATH, sep=";", index=False)

    return {
        "status": "ok",
        "transaction": {
            "Description": new_row["Description"],
            "Income/expensive": new_row["Income/expensive"],
            "Amount": float(new_row["Amount"]),
            "Category": new_row["Category"],
            "Date": parsed_date.strftime("%Y-%m-%d")
        },
        "transaction_count": int(len(updated))
    }

if __name__ == "__main__":
    mcp.run()
