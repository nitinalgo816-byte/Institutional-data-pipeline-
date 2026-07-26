import os
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
import urllib.parse
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- CONFIGURATION & ENVIRONMENT VARIABLES ---
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
SERVICE_ACCOUNT_KEY_JSON = os.getenv("GCP_SERVICE_ACCOUNT_KEY")
FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")

HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Bearer {ACCESS_TOKEN}"
}

def get_latest_trading_date():
    """Automatically rolls back to Friday if run on a weekend."""
    today = datetime.now().date()
    if today.weekday() == 5:  # Saturday
        target = today - timedelta(days=1)
    elif today.weekday() == 6:  # Sunday
        target = today - timedelta(days=2)
    else:
        target = today
    return target.strftime('%Y-%m-%d')

def fetch_1min_candles(instrument_key, date_str):
    encoded_key = urllib.parse.quote(instrument_key)
    url = f"https://api.upstox.com/v3/historical-candle/{encoded_key}/minutes/1/{date_str}/{date_str}"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            res_data = response.json()
            if 'data' in res_data and res_data['data'] and res_data['data']['candles']:
                df = pd.DataFrame(res_data['data']['candles'], 
                                  columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'OpenInterest'])
                df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
                return df.sort_values('Date').reset_index(drop=True)
            else:
                print(f"   ⚠️ No candle data returned for {instrument_key} on {date_str}: {res_data}")
        else:
            print(f"   🚨 API Error {response.status_code} for {instrument_key}: {response.text}")
    except Exception as e:
        print(f"   🚨 Exception for {instrument_key}: {e}")
    return pd.DataFrame()

def upload_to_gdrive(file_path, file_name, folder_id):
    if not SERVICE_ACCOUNT_KEY_JSON:
        print("🚨 GCP_SERVICE_ACCOUNT_KEY environment variable is missing.")
        return
    if not folder_id:
        print("🚨 GDRIVE_FOLDER_ID environment variable is missing.")
        return
    try:
        key_dict = json.loads(SERVICE_ACCOUNT_KEY_JSON)
        creds = service_account.Credentials.from_service_account_info(
            key_dict, scopes=['https://www.googleapis.com/auth/drive.file']
        )
        service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(
            body=file_metadata, media_body=media, fields='id'
        ).execute()
        print(f"✅ Successfully uploaded {file_name} to Google Drive (ID: {file.get('id')})")
    except Exception as e:
        print(f"🚨 Google Drive Upload Error for {file_name}: {e}")

def main():
    print("Starting Institutional Data Pipeline...")
    
    if not ACCESS_TOKEN:
        print("🚨 Error: UPSTOX_ACCESS_TOKEN is missing from GitHub secrets!")
        return
    
    target_date = get_latest_trading_date()
    print(f"Target trading date for data extraction: {target_date}")
    
    # Asset watchlist (Indices & Core Equities)
    instruments = {
        "NIFTY_50": "NSE_INDEX|Nifty 50",
        "BANK_NIFTY": "NSE_INDEX|Nifty Bank",
        "RELIANCE": "NSE_EQ|INE002A01018",
        "TCS": "NSE_EQ|INE467B01029",
        "HDFCBANK": "NSE_EQ|INE040A01034"
    }
    
    os.makedirs("output_data", exist_ok=True)
    
    for name, key in instruments.items():
        print(f"Fetching 1-min candles for {name} ({key})...")
        df = fetch_1min_candles(key, target_date)
        
        if not df.empty:
            filename = f"{name}_{target_date}_1min.csv"
            filepath = os.path.join("output_data", filename)
            df.to_csv(filepath, index=False)
            print(f"   Saved {filename} locally ({len(df)} rows). Uploading to Drive...")
            
            # Upload processed CSV to Google Drive folder
            upload_to_gdrive(filepath, filename, FOLDER_ID)
        else:
            print(f"   Skipping upload for {name} due to empty data.")

    print("Pipeline execution completed successfully.")

if __name__ == "__main__":
    main()
