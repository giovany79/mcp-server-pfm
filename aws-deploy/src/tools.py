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

    def save_data(self, df: pd.DataFrame):
        """Saves the DataFrame back to S3."""
        try:
            print(f"Saving data to S3: {self.bucket_name}/{self.file_key}")
            csv_buffer = io.StringIO()
            # Use same separator and encoding as load_data
            df.to_csv(csv_buffer, sep=";", index=False, encoding="utf-8")
            
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=self.file_key,
                Body=csv_buffer.getvalue()
            )
            self._df = df # Update cache
        except Exception as e:
            print(f"Error saving S3 data: {e}")
            raise

    def add_movement(self, date: str, amount: float, category: str, income_expensive: str, description: str) -> Dict[str, Any]:
        """Adds a new movement to the financial records."""
        # Ensure data is loaded
        df = self.load_data()
        
        # Create new record
        new_row = {
            'Date': pd.to_datetime(date),
            'Category': category,
            'Amount': amount,
            'Income/expensive': income_expensive,
            'Description': description
        }
        
        # Append to dataframe
        new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
        # Save back to S3
        self.save_data(new_df)
        
        # Format date for return
        new_row['Date'] = new_row['Date'].strftime('%Y-%m-%d')
        return {
            "status": "success",
            "message": "Movement added successfully",
            "data": new_row
        }

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
