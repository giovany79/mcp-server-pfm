import pandas as pd
import boto3
import io
import os
from datetime import datetime
from typing import Optional, Dict, List, Any
import uuid

class FinanceTools:
    def __init__(self):
        # Read bucket name from env var or default
        self.bucket_name = os.environ.get('DATA_BUCKET')
        self.file_key = "pfm-gio.csv"
        self._df = None
        self.s3 = boto3.client('s3')
        self.id_column = "transaction_id"
        self.base_columns = [self.id_column, "Description", "Income/expensive", "Amount", "Category", "Date"]
        self.max_batch_transactions = 20

    def _generate_transaction_ids(self, count: int) -> List[str]:
        return [str(uuid.uuid4()) for _ in range(count)]

    def _normalize_dataframe(self, df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
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

        if self.id_column not in df.columns:
            df[self.id_column] = self._generate_transaction_ids(len(df))
            changed = True
        else:
            ids = df[self.id_column].astype("string")
            missing_mask = ids.isna() | ids.str.strip().eq("")
            if missing_mask.any():
                df.loc[missing_mask, self.id_column] = self._generate_transaction_ids(int(missing_mask.sum()))
                changed = True
            df[self.id_column] = df[self.id_column].astype(str).str.strip()

        return df, changed

    def _write_dataframe_to_s3(self, df: pd.DataFrame) -> None:
        output = df.copy()
        if "Date" in output.columns:
            output["Date"] = pd.to_datetime(output["Date"], errors="coerce").dt.strftime("%Y-%m-%d")

        ordered_cols = [c for c in self.base_columns if c in output.columns]
        remaining_cols = [c for c in output.columns if c not in ordered_cols]
        output = output[ordered_cols + remaining_cols]

        buffer = io.StringIO()
        output.to_csv(buffer, sep=";", index=False)
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=self.file_key,
            Body=buffer.getvalue().encode("utf-8")
        )

    def _save_dataframe(self, df: pd.DataFrame) -> None:
        self._write_dataframe_to_s3(df)
        self._df = df.copy()

    def _serialize_transaction(self, row: pd.Series) -> Dict[str, Any]:
        date_value = row["Date"]
        if pd.isna(date_value):
            serialized_date = None
        else:
            serialized_date = pd.to_datetime(date_value).strftime("%Y-%m-%d")

        return {
            self.id_column: str(row[self.id_column]),
            "Description": str(row["Description"]),
            "Income/expensive": str(row["Income/expensive"]),
            "Amount": float(row["Amount"]),
            "Category": str(row["Category"]),
            "Date": serialized_date,
        }

    def _build_transaction_row(
        self,
        description: str,
        transaction_type: str,
        amount: float,
        category: str,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        if not description or not str(description).strip():
            raise ValueError("Description is required")
        if not category or not str(category).strip():
            raise ValueError("Category is required")
        if not transaction_type or not str(transaction_type).strip():
            raise ValueError("Transaction type is required")

        normalized_type = str(transaction_type).strip().lower()
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
                parsed_date = pd.to_datetime(date, format="mixed", dayfirst=True, errors="raise")
            except (TypeError, ValueError):
                raise ValueError("Date must be a valid date string")
        else:
            parsed_date = pd.to_datetime(datetime.now().date())

        return {
            self.id_column: str(uuid.uuid4()),
            "Description": str(description).strip(),
            "Income/expensive": normalized_type,
            "Amount": amount_value,
            "Category": str(category).strip(),
            "Date": parsed_date
        }

    def load_data(self) -> pd.DataFrame:
        """Loads data from S3, caching it in memory for the lambda execution context."""
        if self._df is not None:
            return self._df
            
        try:
            print(f"Loading data from S3: {self.bucket_name}/{self.file_key}")
            obj = self.s3.get_object(Bucket=self.bucket_name, Key=self.file_key)
            csv_content = obj['Body'].read()
            
            # Read CSV from bytes
            df = pd.read_csv(io.BytesIO(csv_content), sep=";", encoding="utf-8")
            
            df, changed = self._normalize_dataframe(df)
            if changed:
                self._write_dataframe_to_s3(df)
            self._df = df
            return df
        except Exception as e:
            print(f"Error loading S3 data: {e}")
            raise

    def calculate_totals(self, year: Optional[int] = None, month: Optional[int] = None, category: Optional[str] = None) -> Dict[str, float]:
        df = self.load_data()
        
        if year:
            df = df[df['Date'].dt.year == year]
        if month:
            df = df[df['Date'].dt.month == month]
        if category:
            df = df[df['Category'].str.contains(category, case=False, na=False)]
            
        income = df[df['Income/expensive'].str.lower() == 'income']['Amount'].sum()
        expenses = df[df['Income/expensive'].str.lower() == 'expensive']['Amount'].sum()
        balance = income - expenses
        
        return {
            "income": float(income),
            "expenses": float(expenses),
            "balance": float(balance),
            "transaction_count": int(len(df))
        }

    def list_transactions(
        self,
        limit: Optional[int] = 10,
        category: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        day: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        df = self.load_data()
        
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
        if category and category.lower() != 'all':
            df = df[df['Category'].str.contains(category, case=False, na=False)]
            
        df = df.sort_values(by='Date', ascending=False)
        if limit and limit > 0:
            result = df.head(limit).copy()
        else:
            result = df.copy()
        result['Date'] = result['Date'].dt.strftime('%Y-%m-%d')

        return result.to_dict(orient="records")

    def expenses_by_category(self, year: Optional[int] = None, month: Optional[int] = None) -> List[Dict[str, Any]]:
        df = self.load_data()

        if year:
            df = df[df['Date'].dt.year == year]
        if month:
            df = df[df['Date'].dt.month == month]

        expenses = df[df['Income/expensive'].str.lower() == 'expensive']
        grouped = expenses.groupby('Category', dropna=False)['Amount'].sum().sort_values(ascending=False)

        result = grouped.reset_index().rename(columns={'Category': 'category', 'Amount': 'total'})
        return result.to_dict(orient="records")

    def expenses_by_month_for_category(self, category: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        df = self.load_data()

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

    def add_transaction(
        self,
        description: str,
        transaction_type: str,
        amount: float,
        category: str,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self.bucket_name:
            raise RuntimeError("DATA_BUCKET is not configured")

        df = self.load_data()
        new_row = self._build_transaction_row(description, transaction_type, amount, category, date)

        updated = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        self._save_dataframe(updated)

        return {
            "status": "ok",
            "transaction": self._serialize_transaction(pd.Series(new_row)),
            "transaction_count": int(len(updated))
        }

    def add_transactions_batch(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.bucket_name:
            raise RuntimeError("DATA_BUCKET is not configured")
        if not isinstance(transactions, list) or len(transactions) == 0:
            raise ValueError("transactions must be a non-empty list")
        if len(transactions) > self.max_batch_transactions:
            raise ValueError(f"Maximum {self.max_batch_transactions} transactions per batch")

        new_rows: List[Dict[str, Any]] = []
        for index, tx in enumerate(transactions):
            if not isinstance(tx, dict):
                raise ValueError(f"Transaction at index {index} must be an object")
            try:
                row = self._build_transaction_row(
                    description=tx.get("description"),
                    transaction_type=tx.get("transaction_type"),
                    amount=tx.get("amount"),
                    category=tx.get("category"),
                    date=tx.get("date"),
                )
            except ValueError as exc:
                raise ValueError(f"Invalid transaction at index {index}: {str(exc)}")
            new_rows.append(row)

        df = self.load_data()
        updated = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        self._save_dataframe(updated)

        return {
            "status": "ok",
            "added_count": len(new_rows),
            "transactions": [self._serialize_transaction(pd.Series(row)) for row in new_rows],
            "transaction_count": int(len(updated))
        }

    def update_transaction(
        self,
        transaction_id: str,
        description: Optional[str] = None,
        transaction_type: Optional[str] = None,
        amount: Optional[float] = None,
        category: Optional[str] = None,
        date: Optional[str] = None
    ) -> Dict[str, Any]:
        if not transaction_id or not transaction_id.strip():
            raise ValueError("transaction_id is required")

        if all(v is None for v in [description, transaction_type, amount, category, date]):
            raise ValueError("At least one field must be provided to update")

        df = self.load_data()
        row_mask = df[self.id_column].astype(str) == transaction_id.strip()
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

        self._save_dataframe(df)
        updated_transaction = self._serialize_transaction(df.loc[idx])

        return {
            "status": "ok",
            "transaction": updated_transaction,
            "transaction_count": int(len(df))
        }

    def delete_transaction(self, transaction_id: str) -> Dict[str, Any]:
        if not transaction_id or not transaction_id.strip():
            raise ValueError("transaction_id is required")

        df = self.load_data()
        row_mask = df[self.id_column].astype(str) == transaction_id.strip()
        if not row_mask.any():
            raise ValueError(f"Transaction not found: {transaction_id}")

        deleted_row = df[row_mask].iloc[0]
        updated = df[~row_mask].copy()
        self._save_dataframe(updated)

        return {
            "status": "ok",
            "deleted_transaction": self._serialize_transaction(deleted_row),
            "transaction_count": int(len(updated))
        }
