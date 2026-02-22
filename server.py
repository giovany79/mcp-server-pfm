from mcp.server.fastmcp import FastMCP
import pandas as pd
from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid

# Create an MCP Server
mcp = FastMCP("Personal Finance Manager")

DATA_PATH = "pfm-gio.csv"
ID_COLUMN = "transaction_id"
BASE_COLUMNS = [ID_COLUMN, "Description", "Income/expensive", "Amount", "Category", "Date"]


def _generate_transaction_ids(count: int) -> List[str]:
    return [str(uuid.uuid4()) for _ in range(count)]


def _normalize_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    changed = False

    df.columns = [c.strip() for c in df.columns]

    required = {"Description", "Income/expensive", "Amount", "Category", "Date"}
    missing_required = required.difference(df.columns)
    if missing_required:
        raise ValueError(f"Missing required columns: {sorted(missing_required)}")

    if df["Amount"].dtype == "object":
        df["Amount"] = df["Amount"].astype(str).str.replace(r"[$. ]", "", regex=True)
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df = df.dropna(subset=["Amount"])

    df["Date"] = pd.to_datetime(df["Date"], format="mixed", dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Date"])

    if ID_COLUMN not in df.columns:
        df[ID_COLUMN] = _generate_transaction_ids(len(df))
        changed = True
    else:
        ids = df[ID_COLUMN].astype("string")
        missing_mask = ids.isna() | ids.str.strip().eq("")
        if missing_mask.any():
            df.loc[missing_mask, ID_COLUMN] = _generate_transaction_ids(int(missing_mask.sum()))
            changed = True
        df[ID_COLUMN] = df[ID_COLUMN].astype(str).str.strip()

    return df, changed


def _persist_dataframe(df: pd.DataFrame) -> None:
    output = df.copy()
    if "Date" in output.columns:
        output["Date"] = pd.to_datetime(output["Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    ordered_cols = [c for c in BASE_COLUMNS if c in output.columns]
    remaining_cols = [c for c in output.columns if c not in ordered_cols]
    output = output[ordered_cols + remaining_cols]
    output.to_csv(DATA_PATH, sep=";", index=False)


def _serialize_transaction(row: pd.Series) -> Dict[str, Any]:
    date_value = row["Date"]
    if pd.isna(date_value):
        serialized_date = None
    else:
        serialized_date = pd.to_datetime(date_value).strftime("%Y-%m-%d")

    return {
        ID_COLUMN: str(row[ID_COLUMN]),
        "Description": str(row["Description"]),
        "Income/expensive": str(row["Income/expensive"]),
        "Amount": float(row["Amount"]),
        "Category": str(row["Category"]),
        "Date": serialized_date,
    }

def load_data() -> pd.DataFrame:
    """Loads and cleans the financial data from CSV."""
    try:
        try:
            df = pd.read_csv(DATA_PATH, sep=";", encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(DATA_PATH, sep=";", encoding="latin-1")

        df, changed = _normalize_dataframe(df)
        if changed:
            _persist_dataframe(df)
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
def list_transactions(
    limit: Optional[int] = 10,
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None
) -> str:
    """
    List individual transactions matching criteria.
    
    Args:
        limit: Max number of transactions to return (default 10).
        category: Filter by category name.
        start_date: Filter transactions on or after this date (format YYYY-MM-DD).
        end_date: Filter transactions on or before this date (format YYYY-MM-DD).
        year: Filter by specific year.
        month: Filter by specific month.
        day: Filter by specific day of month.
    """
    df = load_data()
    
    if year:
        df = df[df['Date'].dt.year == year]
    
    if month:
        df = df[df['Date'].dt.month == month]

    if day:
        df = df[df['Date'].dt.day == day]
    
    if start_date:
        start_dt = pd.to_datetime(start_date)
        df = df[df['Date'] >= start_dt]

    if end_date:
        end_dt = pd.to_datetime(end_date)
        df = df[df['Date'] <= end_dt]
        
    if category:
        df = df[df['Category'].str.contains(category, case=False, na=False)]
        
    # Sort by date desc (most recent first)
    df = df.sort_values(by='Date', ascending=False)
    
    result = df.head(limit) if limit and limit > 0 else df
    
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
    transaction_id = str(uuid.uuid4())
    new_row = {
        ID_COLUMN: transaction_id,
        "Description": description.strip(),
        "Income/expensive": normalized_type,
        "Amount": amount_value,
        "Category": category.strip(),
        "Date": parsed_date
    }

    updated = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    _persist_dataframe(updated)

    return {
        "status": "ok",
        "transaction": _serialize_transaction(pd.Series(new_row)),
        "transaction_count": int(len(updated))
    }


@mcp.tool()
def update_transaction(
    transaction_id: str,
    description: Optional[str] = None,
    transaction_type: Optional[str] = None,
    amount: Optional[float] = None,
    category: Optional[str] = None,
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update an existing transaction by transaction_id.
    """
    if not transaction_id or not transaction_id.strip():
        raise ValueError("transaction_id is required")

    if all(v is None for v in [description, transaction_type, amount, category, date]):
        raise ValueError("At least one field must be provided to update")

    df = load_data()
    row_mask = df[ID_COLUMN].astype(str) == transaction_id.strip()
    if not row_mask.any():
        raise ValueError(f"Transaction not found: {transaction_id}")

    idx = df[row_mask].index[0]

    if description is not None:
        if not description.strip():
            raise ValueError("Description cannot be empty")
        df.at[idx, "Description"] = description.strip()

    if transaction_type is not None:
        normalized_type = transaction_type.strip().lower()
        if normalized_type not in {"income", "expensive"}:
            raise ValueError("Transaction type must be 'income' or 'expensive'")
        df.at[idx, "Income/expensive"] = normalized_type

    if amount is not None:
        try:
            amount_value = float(amount)
        except (TypeError, ValueError):
            raise ValueError("Amount must be a number")
        if amount_value <= 0:
            raise ValueError("Amount must be greater than zero")
        df.at[idx, "Amount"] = amount_value

    if category is not None:
        if not category.strip():
            raise ValueError("Category cannot be empty")
        df.at[idx, "Category"] = category.strip()

    if date is not None:
        try:
            parsed_date = pd.to_datetime(date, format="mixed", dayfirst=True, errors="raise")
        except (TypeError, ValueError):
            raise ValueError("Date must be a valid date string")
        df.at[idx, "Date"] = parsed_date

    _persist_dataframe(df)
    updated_transaction = _serialize_transaction(df.loc[idx])

    return {
        "status": "ok",
        "transaction": updated_transaction,
        "transaction_count": int(len(df))
    }


@mcp.tool()
def delete_transaction(transaction_id: str) -> Dict[str, Any]:
    """
    Delete a transaction by transaction_id.
    """
    if not transaction_id or not transaction_id.strip():
        raise ValueError("transaction_id is required")

    df = load_data()
    row_mask = df[ID_COLUMN].astype(str) == transaction_id.strip()
    if not row_mask.any():
        raise ValueError(f"Transaction not found: {transaction_id}")

    deleted_row = df[row_mask].iloc[0]
    updated = df[~row_mask].copy()
    _persist_dataframe(updated)

    return {
        "status": "ok",
        "deleted_transaction": _serialize_transaction(deleted_row),
        "transaction_count": int(len(updated))
    }

if __name__ == "__main__":
    mcp.run()
