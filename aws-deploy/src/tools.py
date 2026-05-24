import pandas as pd
import boto3
import io
import os
from datetime import datetime
from typing import Optional, Dict, List, Any
import uuid
import re


ISO_DATE_PATTERN = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:[ T].*)?$")


def parse_date_value(value: Any, errors: str = "coerce") -> pd.Timestamp:
    text = str(value).strip()
    if ISO_DATE_PATTERN.match(text):
        return pd.to_datetime(value, format="mixed", yearfirst=True, errors=errors)
    return pd.to_datetime(value, format="mixed", dayfirst=True, errors=errors)


def parse_date_series(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, format="mixed", dayfirst=True, errors="coerce")
    iso_mask = series.astype("string").str.strip().str.match(ISO_DATE_PATTERN, na=False)
    if iso_mask.any():
        parsed.loc[iso_mask] = pd.to_datetime(series.loc[iso_mask], format="mixed", yearfirst=True, errors="coerce")
    return parsed

class FinanceTools:
    def __init__(self):
        # Read bucket name from env var or default
        self.bucket_name = os.environ.get('DATA_BUCKET')
        self.file_key = "pfm-gio.csv"
        self.balance_sheet_key = "balance-sheet.csv"
        self._df = None
        self._balance_df = None
        self.s3 = boto3.client('s3')
        self.id_column = "transaction_id"
        self.balance_id_column = "item_id"
        self.base_columns = [self.id_column, "Description", "Income/expensive", "Amount", "Category", "Date"]
        self.balance_columns = [
            self.balance_id_column,
            "snapshot_date",
            "name",
            "kind",
            "category",
            "amount",
            "currency",
            "institution",
            "notes",
        ]
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

        if not pd.api.types.is_numeric_dtype(df["Amount"]):
            df["Amount"] = df["Amount"].astype(str).str.replace(r"[$. ]", "", regex=True)
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
        df = df.dropna(subset=["Amount"])

        df["Date"] = parse_date_series(df["Date"])
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

    def _empty_balance_sheet(self) -> pd.DataFrame:
        return pd.DataFrame(columns=self.balance_columns)

    def _normalize_balance_sheet(self, df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
        changed = False

        if df.empty:
            return self._empty_balance_sheet(), changed

        df.columns = [c.strip() for c in df.columns]

        required = {"snapshot_date", "name", "kind", "category", "amount"}
        missing_required = required.difference(df.columns)
        if missing_required:
            raise ValueError(f"Missing required balance sheet columns: {sorted(missing_required)}")

        for column in ["currency", "institution", "notes"]:
            if column not in df.columns:
                df[column] = ""
                changed = True

        if self.balance_id_column not in df.columns:
            df[self.balance_id_column] = self._generate_transaction_ids(len(df))
            changed = True
        else:
            ids = df[self.balance_id_column].astype("string")
            missing_mask = ids.isna() | ids.str.strip().eq("")
            if missing_mask.any():
                df.loc[missing_mask, self.balance_id_column] = self._generate_transaction_ids(int(missing_mask.sum()))
                changed = True
            df[self.balance_id_column] = df[self.balance_id_column].astype(str).str.strip()

        df["snapshot_date"] = parse_date_series(df["snapshot_date"])
        df = df.dropna(subset=["snapshot_date"])

        if not pd.api.types.is_numeric_dtype(df["amount"]):
            df["amount"] = df["amount"].astype(str).str.replace(r"[$. ]", "", regex=True)
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df = df.dropna(subset=["amount"])
        df = df[df["amount"] > 0].copy()

        df["kind"] = df["kind"].astype(str).str.strip().str.lower()
        valid_kind_mask = df["kind"].isin({"asset", "liability"})
        df = df[valid_kind_mask].copy()

        for column in ["name", "category", "currency", "institution", "notes"]:
            df[column] = df[column].fillna("").astype(str).str.strip()

        df["currency"] = df["currency"].replace("", "COP").str.upper()

        ordered_cols = [c for c in self.balance_columns if c in df.columns]
        remaining_cols = [c for c in df.columns if c not in ordered_cols]
        return df[ordered_cols + remaining_cols], changed

    def _write_balance_sheet_to_s3(self, df: pd.DataFrame) -> None:
        output = df.copy()
        if "snapshot_date" in output.columns:
            output["snapshot_date"] = pd.to_datetime(output["snapshot_date"], errors="coerce").dt.strftime("%Y-%m-%d")

        ordered_cols = [c for c in self.balance_columns if c in output.columns]
        remaining_cols = [c for c in output.columns if c not in ordered_cols]
        output = output[ordered_cols + remaining_cols]

        buffer = io.StringIO()
        output.to_csv(buffer, sep=";", index=False)
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=self.balance_sheet_key,
            Body=buffer.getvalue().encode("utf-8")
        )

    def _save_balance_sheet(self, df: pd.DataFrame) -> None:
        self._write_balance_sheet_to_s3(df)
        self._balance_df = df.copy()

    def _serialize_balance_item(self, row: pd.Series) -> Dict[str, Any]:
        date_value = row["snapshot_date"]
        serialized_date = None if pd.isna(date_value) else pd.to_datetime(date_value).strftime("%Y-%m-%d")

        return {
            self.balance_id_column: str(row[self.balance_id_column]),
            "snapshot_date": serialized_date,
            "name": str(row["name"]),
            "kind": str(row["kind"]),
            "category": str(row["category"]),
            "amount": float(row["amount"]),
            "currency": str(row.get("currency", "COP")),
            "institution": str(row.get("institution", "")),
            "notes": str(row.get("notes", "")),
        }

    def _build_balance_item(
        self,
        name: str,
        kind: str,
        amount: float,
        category: str,
        snapshot_date: Optional[str] = None,
        currency: str = "COP",
        institution: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        if not name or not str(name).strip():
            raise ValueError("Name is required")
        if not category or not str(category).strip():
            raise ValueError("Category is required")
        if not kind or not str(kind).strip():
            raise ValueError("Kind is required")

        normalized_kind = str(kind).strip().lower()
        if normalized_kind not in {"asset", "liability"}:
            raise ValueError("Kind must be 'asset' or 'liability'")

        try:
            amount_value = float(amount)
        except (TypeError, ValueError):
            raise ValueError("Amount must be a number")

        if amount_value <= 0:
            raise ValueError("Amount must be greater than zero")

        if snapshot_date:
            try:
                parsed_date = parse_date_value(snapshot_date, errors="raise")
            except (TypeError, ValueError):
                raise ValueError("Snapshot date must be a valid date string")
        else:
            parsed_date = pd.to_datetime(datetime.now().date())

        normalized_currency = str(currency or "COP").strip().upper()

        return {
            self.balance_id_column: str(uuid.uuid4()),
            "snapshot_date": parsed_date,
            "name": str(name).strip(),
            "kind": normalized_kind,
            "category": str(category).strip(),
            "amount": amount_value,
            "currency": normalized_currency,
            "institution": str(institution or "").strip(),
            "notes": str(notes or "").strip(),
        }

    def load_balance_sheet(self) -> pd.DataFrame:
        """Loads balance sheet snapshots from S3, creating an empty frame if the file does not exist."""
        if self._balance_df is not None:
            return self._balance_df

        try:
            print(f"Loading balance sheet from S3: {self.bucket_name}/{self.balance_sheet_key}")
            obj = self.s3.get_object(Bucket=self.bucket_name, Key=self.balance_sheet_key)
            csv_content = obj['Body'].read()
            df = pd.read_csv(io.BytesIO(csv_content), sep=";", encoding="utf-8")
        except Exception as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code")
            if error_code in {"NoSuchKey", "404"} or "NoSuchKey" in str(e):
                df = self._empty_balance_sheet()
            else:
                print(f"Error loading balance sheet data: {e}")
                raise

        df, changed = self._normalize_balance_sheet(df)
        if changed and self.bucket_name:
            self._write_balance_sheet_to_s3(df)
        self._balance_df = df
        return df

    def _balance_snapshot(self, df: pd.DataFrame, snapshot_date: Optional[str] = None) -> pd.DataFrame:
        if df.empty:
            return df.copy()
        if snapshot_date:
            parsed_date = parse_date_value(snapshot_date, errors="raise")
            return df[df["snapshot_date"].dt.date == parsed_date.date()].copy()

        latest_date = df["snapshot_date"].max()
        return df[df["snapshot_date"] == latest_date].copy()

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
                parsed_date = parse_date_value(date, errors="raise")
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

    def list_balance_items(
        self,
        snapshot_date: Optional[str] = None,
        kind: Optional[str] = None,
        category: Optional[str] = None,
        limit: Optional[int] = 0
    ) -> List[Dict[str, Any]]:
        df = self._balance_snapshot(self.load_balance_sheet(), snapshot_date)

        if kind:
            normalized_kind = kind.strip().lower()
            if normalized_kind not in {"asset", "liability"}:
                raise ValueError("Kind must be 'asset' or 'liability'")
            df = df[df["kind"] == normalized_kind]

        if category and category.lower() != "all":
            df = df[df["category"].str.contains(category, case=False, na=False)]

        df = df.sort_values(by=["kind", "category", "name"], ascending=True)
        if limit and limit > 0:
            df = df.head(limit).copy()

        return [self._serialize_balance_item(row) for _, row in df.iterrows()]

    def calculate_net_worth(self, snapshot_date: Optional[str] = None) -> Dict[str, Any]:
        df = self._balance_snapshot(self.load_balance_sheet(), snapshot_date)

        assets = df[df["kind"] == "asset"]["amount"].sum()
        liabilities = df[df["kind"] == "liability"]["amount"].sum()
        net_worth = assets - liabilities
        resolved_date = None
        if not df.empty:
            resolved_date = pd.to_datetime(df["snapshot_date"].max()).strftime("%Y-%m-%d")

        return {
            "snapshot_date": resolved_date,
            "assets": float(assets),
            "liabilities": float(liabilities),
            "net_worth": float(net_worth),
            "item_count": int(len(df)),
        }

    def net_worth_history(self) -> List[Dict[str, Any]]:
        df = self.load_balance_sheet()
        if df.empty:
            return []

        rows = []
        for snapshot_date, group in df.groupby(df["snapshot_date"].dt.strftime("%Y-%m-%d"), sort=True):
            assets = group[group["kind"] == "asset"]["amount"].sum()
            liabilities = group[group["kind"] == "liability"]["amount"].sum()
            rows.append({
                "snapshot_date": snapshot_date,
                "assets": float(assets),
                "liabilities": float(liabilities),
                "net_worth": float(assets - liabilities),
                "item_count": int(len(group)),
            })
        return rows

    def add_balance_item(
        self,
        name: str,
        kind: str,
        amount: float,
        category: str,
        snapshot_date: Optional[str] = None,
        currency: str = "COP",
        institution: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self.bucket_name:
            raise RuntimeError("DATA_BUCKET is not configured")

        df = self.load_balance_sheet()
        new_row = self._build_balance_item(name, kind, amount, category, snapshot_date, currency, institution, notes)
        updated = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        self._save_balance_sheet(updated)

        return {
            "status": "ok",
            "item": self._serialize_balance_item(pd.Series(new_row)),
            "item_count": int(len(updated)),
        }

    def update_balance_item(
        self,
        item_id: str,
        name: Optional[str] = None,
        kind: Optional[str] = None,
        amount: Optional[float] = None,
        category: Optional[str] = None,
        snapshot_date: Optional[str] = None,
        currency: Optional[str] = None,
        institution: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        if not item_id or not item_id.strip():
            raise ValueError("item_id is required")

        if all(v is None for v in [name, kind, amount, category, snapshot_date, currency, institution, notes]):
            raise ValueError("At least one field must be provided to update")

        df = self.load_balance_sheet()
        row_mask = df[self.balance_id_column].astype(str) == item_id.strip()
        if not row_mask.any():
            raise ValueError(f"Balance item not found: {item_id}")

        idx = df[row_mask].index[0]

        if name is not None:
            if not name.strip():
                raise ValueError("Name cannot be empty")
            df.at[idx, "name"] = name.strip()

        if kind is not None:
            normalized_kind = kind.strip().lower()
            if normalized_kind not in {"asset", "liability"}:
                raise ValueError("Kind must be 'asset' or 'liability'")
            df.at[idx, "kind"] = normalized_kind

        if amount is not None:
            try:
                amount_value = float(amount)
            except (TypeError, ValueError):
                raise ValueError("Amount must be a number")
            if amount_value <= 0:
                raise ValueError("Amount must be greater than zero")
            df.at[idx, "amount"] = amount_value

        if category is not None:
            if not category.strip():
                raise ValueError("Category cannot be empty")
            df.at[idx, "category"] = category.strip()

        if snapshot_date is not None:
            try:
                parsed_date = parse_date_value(snapshot_date, errors="raise")
            except (TypeError, ValueError):
                raise ValueError("Snapshot date must be a valid date string")
            df.at[idx, "snapshot_date"] = parsed_date

        if currency is not None:
            df.at[idx, "currency"] = str(currency or "COP").strip().upper()

        if institution is not None:
            df.at[idx, "institution"] = institution.strip()

        if notes is not None:
            df.at[idx, "notes"] = notes.strip()

        self._save_balance_sheet(df)

        return {
            "status": "ok",
            "item": self._serialize_balance_item(df.loc[idx]),
            "item_count": int(len(df)),
        }

    def delete_balance_item(self, item_id: str) -> Dict[str, Any]:
        if not item_id or not item_id.strip():
            raise ValueError("item_id is required")

        df = self.load_balance_sheet()
        row_mask = df[self.balance_id_column].astype(str) == item_id.strip()
        if not row_mask.any():
            raise ValueError(f"Balance item not found: {item_id}")

        deleted_row = df[row_mask].iloc[0]
        updated = df[~row_mask].copy()
        self._save_balance_sheet(updated)

        return {
            "status": "ok",
            "deleted_item": self._serialize_balance_item(deleted_row),
            "item_count": int(len(updated)),
        }

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
                parsed_date = parse_date_value(date, errors="raise")
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
