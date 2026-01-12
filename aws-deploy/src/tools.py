import pandas as pd
import boto3
import io
import os
from typing import Optional, Dict, List, Any

class FinanceTools:
    def __init__(self):
        # Read bucket name from env var or default
        self.bucket_name = os.environ.get('DATA_BUCKET')
        self.file_key = "pfm-gio.csv"
        self._df = None
        self.s3 = boto3.client('s3')

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
            
            # --- CLEANING LOGIC (Same as server.py) ---
            df.columns = [c.strip() for c in df.columns]
            
            # Clean Amount
            if df['Amount'].dtype == 'object':
                df['Amount'] = df['Amount'].astype(str).str.replace(r'[$. ]', '', regex=True)
                df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
                
            df = df.dropna(subset=['Amount'])
            
            # Clean Dates (handling mixed formats)
            df['Date'] = pd.to_datetime(df['Date'], format='mixed', dayfirst=True, errors='coerce')
            df = df.dropna(subset=['Date'])
            # ------------------------------------------
            
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

    def list_transactions(self, limit: int = 10, category: Optional[str] = None, start_date: Optional[str] = None, year: Optional[int] = None, month: Optional[int] = None) -> List[Dict[str, Any]]:
        df = self.load_data()
        
        if year:
            df = df[df['Date'].dt.year == year]
        if month:
            df = df[df['Date'].dt.month == month]
        if start_date:
            start_dt = pd.to_datetime(start_date)
            df = df[df['Date'] >= start_dt]
        if category and category.lower() != 'all':
            df = df[df['Category'].str.contains(category, case=False, na=False)]
            
        df = df.sort_values(by='Date', ascending=False)
        result = df.head(limit).copy()
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
