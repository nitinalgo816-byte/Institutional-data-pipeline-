import os
import io
import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta, timezone
import urllib.parse
import py_vollib_vectorized

# --- CONFIGURATION & ENVIRONMENT VARIABLES ---
ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")

HEADERS = {
    'Accept': 'application/json',
    'Authorization': f'Bearer {ACCESS_TOKEN}'
}
RISK_FREE_RATE = 0.07

def get_latest_trading_date():
    """Uses UTC time to guarantee it matches the Indian trading day that just closed."""
    today = datetime.now(timezone.utc).date()
    if today.weekday() == 5:  # Saturday
        target = today - timedelta(days=1)
    elif today.weekday() == 6:  # Sunday
        target = today - timedelta(days=2)
    else:
        target = today
    return target.strftime('%Y-%m-%d')

TODAY_STR = get_latest_trading_date()
print(f"📅 Target Data Date set to: {TODAY_STR}")

# Dynamically create a dated subfolder for daily historical archiving
FOLDER_PATH = f"output_data/{TODAY_STR}/"
os.makedirs(FOLDER_PATH, exist_ok=True)

# ==========================================
# 2. DOWNLOAD COMPLETE MASTER INSTRUMENT DATABASE
# ==========================================
print("\n📥 Downloading Universal Master Exchange Database...")
try:
    BROWSER_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'
    }
    res = requests.get("https://assets.upstox.com/market-quote/instruments/exchange/complete.csv.gz", headers=BROWSER_HEADERS)
    res.raise_for_status()
    MASTER_DB = pd.read_csv(io.BytesIO(res.content), compression='gzip')
    
    MASTER_DB.rename(columns={'strike': 'strike_price'}, inplace=True)
    if 'expiry' in MASTER_DB.columns:
        MASTER_DB['expiry'] = pd.to_datetime(MASTER_DB['expiry']).dt.strftime('%Y-%m-%d')
        
    print("   ✅ Complete Master Database Loaded Successfully.")
except Exception as e:
    print(f"   🚨 Failed to load master database: {e}")
    MASTER_DB = pd.DataFrame()

# ==========================================
# 3. EXPANDED INSTITUTIONAL ASSET UNIVERSE 
# ==========================================
# ---> SENSEX & BANKEX ADDED HERE <---
INDICES = {
    'NIFTY_50': {'key': 'NSE_INDEX|Nifty 50', 'segment': 'NSE', 'gap': 50},
    'BANKNIFTY': {'key': 'NSE_INDEX|Nifty Bank', 'segment': 'NSE', 'gap': 100},
    'FINNIFTY': {'key': 'NSE_INDEX|Nifty Fin Service', 'segment': 'NSE', 'gap': 50},
    'SENSEX': {'key': 'BSE_INDEX|SENSEX', 'segment': 'BSE', 'gap': 100},
    'BANKEX': {'key': 'BSE_INDEX|BANKEX', 'segment': 'BSE', 'gap': 100}
}

MACRO_INDICATORS = {
    'INDIA_VIX': {'key': 'NSE_INDEX|India VIX', 'segment': 'NSE'},
    'NIFTY_IT': {'key': 'NSE_INDEX|Nifty IT', 'segment': 'NSE'},
    'NIFTY_AUTO': {'key': 'NSE_INDEX|Nifty Auto', 'segment': 'NSE'},
    'NIFTY_FMCG': {'key': 'NSE_INDEX|Nifty FMCG', 'segment': 'NSE'},
    'NIFTY_METAL': {'key': 'NSE_INDEX|Nifty Metal', 'segment': 'NSE'}
}

CURRENCIES = {
    'USDINR': {'key': 'USDINR', 'segment': 'CDS'},
    'EURINR': {'key': 'EURINR', 'segment': 'CDS'},
    'GBPINR': {'key': 'GBPINR', 'segment': 'CDS'},
    'JPYINR': {'key': 'JPYINR', 'segment': 'CDS'}
}

MCX_COMMODITIES = {
    'GOLD_Standard': {'key': 'GOLD', 'segment': 'MCX', 'lot_size': 1000},
    'GOLD_Ten': {'key': ['GOLD10G', 'GOLD10'], 'segment': 'MCX', 'lot_size': 10},
    'GOLD_Mini': {'key': 'GOLDM', 'segment': 'MCX', 'lot_size': 100},
    'GOLD_Guinea': {'key': 'GOLDGUINEA', 'segment': 'MCX', 'lot_size': 8},
    'GOLD_Petal': {'key': 'GOLDPETAL', 'segment': 'MCX', 'lot_size': 1},
    'SILVER_Standard': {'key': 'SILVER', 'segment': 'MCX', 'lot_size': 30000},
    'SILVER_100': {'key': ['SILVER100', 'SILVER100G'], 'segment': 'MCX', 'lot_size': 100},
    'SILVER_Mini': {'key': 'SILVERM', 'segment': 'MCX', 'lot_size': 5000},
    'SILVER_Micro': {'key': 'SILVERMIC', 'segment': 'MCX', 'lot_size': 1000},
    'CRUDEOIL': {'key': 'CRUDEOIL', 'segment': 'MCX', 'lot_size': 100},
    'NATURALGAS': {'key': 'NATURALGAS', 'segment': 'MCX', 'lot_size': 1250},
    'ALUMINIUM_Standard': {'key': 'ALUMINIUM', 'segment': 'MCX', 'lot_size': 5000},
    'ALUMINIUM_Mini': {'key': 'ALUMINI', 'segment': 'MCX', 'lot_size': 1000},
    'COPPER_Standard': {'key': 'COPPER', 'segment': 'MCX', 'lot_size': 2500},
    'COPPER_Mini': {'key': ['COPMINI', 'COPPERMINI', 'COPPERM'], 'segment': 'MCX', 'lot_size': 250},
    'LEAD_Standard': {'key': 'LEAD', 'segment': 'MCX', 'lot_size': 5000},
    'LEAD_Mini': {'key': 'LEADMINI', 'segment': 'MCX', 'lot_size': 1000},
    'ZINC_Standard': {'key': 'ZINC', 'segment': 'MCX', 'lot_size': 5000},
    'ZINC_Mini': {'key': 'ZINCMINI', 'segment': 'MCX', 'lot_size': 1000},
    'NICKEL_Standard': {'key': 'NICKEL', 'segment': 'MCX', 'lot_size': 1500},
    'NICKEL_Mini': {'key': ['NICKELM', 'NICKELMINI'], 'segment': 'MCX', 'lot_size': 250}
}

NIFTY_200_SYMBOLS = [
    '360ONE', 'ABB', 'APLAPOLLO', 'AUBANK', 'ADANIENSOL', 'ADANIENT', 'ADANIGREEN', 
    'ADANIPORTS', 'ADANIPOWER', 'ATGL', 'ABCAPITAL', 'ABFRL', 'ALKEM', 'AMBUJACEM', 
    'APOLLOHOSP', 'APOLLOTYRE', 'ASHOKLEY', 'ASIANPAINT', 'ASTRAL', 'AUROPHARMA', 
    'DMART', 'AXISBANK', 'BSE', 'BAJAJ-AUTO', 'BAJFINANCE', 'BAJAJFINSV', 'BAJAJHIND', 
    'BALKRISIND', 'BANKBARODA', 'BANKINDIA', 'BATAINDIA', 'BEL', 'BHARATFORG', 
    'BHEL', 'BPCL', 'BHARTIARTL', 'BIOCON', 'BOSCHLTD', 'BRITANNIA', 'CESC', 
    'CGPOWER', 'CANBK', 'CHOLAFIN', 'CIPLA', 'COALINDIA', 'COFORGE', 'COLPAL', 
    'CONCOR', 'COROMANDEL', 'CROMPTON', 'CUB', 'CUMMINSIND', 'DLF', 'DABUR', 
    'DALBHARAT', 'DEEPAKFERT', 'DIVISLAB', 'DIXON', 'LALPATHLAB', 'DRREDDY', 
    'EICHERMOT', 'ESCORTS', 'EXIDEIND', 'NYKAA', 'FederalBNK', 'GAIL', 'GMRAIRPORT', 
    'GLENMARK', 'GODREJCP', 'GODREJPROP', 'GRASIM', 'GUJGASLTD', 'HCLTECH', 
    'HDFCBANK', 'HDFCLIFE', 'HAVELLS', 'HEROMOTOCO', 'HINDALCO', 'HAL', 'HINDCOPPER', 
    'HINDPETRO', 'HINDUNILVR', 'ICICIBANK', 'ICICIGI', 'ICICIPRULI', 'IDBI', 'IDFCFIRSTB', 
    'ITC', 'IEX', 'IOC', 'IRCTC', 'IRFC', 'IGL', 'INDUSTOWER', 
    'INDUSINDBK', 'NAUKRI', 'INFY', 'IPCALAB', 'JSWENERGY', 'JSWSTEEL', 'JINDALSTEL', 
    'JIOFIN', 'JUBLFOOD', 'KOTAKBANK', 'LTIM', 'LT', 'LUPIN', 'MRF', 'M&MFIN', 
    'M&M', 'MANKIND', 'MARICO', 'MARUTI', 'MAXHEALTH', 'MPHASIS', 'MUTHOOTFIN', 
    'NHPC', 'NMDC', 'NTPC', 'NATIONALUM', 'NESTLEIND', 'OBEROIRLTY', 'ONGC', 'PIIND', 
    'PAGEIND', 'PATANJALI', 'PERSISTENT', 'PETRONET', 'PFIZER', 'PIDILITIND', 
    'POWERCGRID', 'PNB', 'PVRINOX', 'RECLTD', 'RELIANCE', 'SBICARD', 'SBILIFE', 
    'SBIN', 'SHREECEM', 'SHRIRAMFIN', 'SIEMENS', 'SONACOMS', 'SBFC', 'SRF', 
    'SUNPHARMA', 'SUNTV', 'SYNGENE', 'TVSMOTOR', 'TCS', 'TATACHEM', 'TATACOMM', 
    'TATACONSUM', 'TATAELXSI', 'TATAMOTORS', 'TATAPOWER', 'TATASTEEL', 'TECHM', 
    'TITAN', 'TORNTPHARM', 'TORNTPOWER', 'TRENT', 'TIINDIA', 'UCL', 'ULTRACEMCO', 
    'UNIONBANK', 'UPL', 'VEDL', 'IDEA', 'VOLTAS', 'WHIRLPOOL', 'WIPRO', 'YESBANK', 
    'ZOMATO', 'ZYDUSLIFE'
]

EQUITY_ASSETS = {}
if not MASTER_DB.empty:
    eq_df = MASTER_DB[MASTER_DB['instrument_key'].str.startswith('NSE_EQ|', na=False)]
    for sym in NIFTY_200_SYMBOLS:
        match = eq_df[eq_df['tradingsymbol'] == sym]
        if not match.empty:
            EQUITY_ASSETS[sym] = {'key': match.iloc[0]['instrument_key'], 'segment': 'NSE'}
    print(f"   ✅ Successfully mapped {len(EQUITY_ASSETS)} Equities from the master database.")

MASTER_SPOT_LIST = {**MACRO_INDICATORS, **CURRENCIES, **MCX_COMMODITIES, **EQUITY_ASSETS}

# ==========================================
# 4. CORE API & MASTER SCANNING FUNCTIONS 
# ==========================================
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
    except Exception:
        pass
    return pd.DataFrame()

def get_live_contracts(key, contract_type="future", segment="NSE"):
    # ---> UPDATED TO SUPPORT BSE CONTRACT FETCHING <---
    if segment in ["NSE", "BSE"]:
        url = f"https://api.upstox.com/v2/{contract_type}/contract"
        params = {'instrument_key': key}
        try:
            response = requests.get(url, headers=HEADERS, params=params)
            if response.status_code == 200:
                df = pd.DataFrame(response.json().get('data', []))
                if not df.empty and 'expiry' in df.columns:
                    df = df[df['expiry'] >= TODAY_STR]
                return df
        except Exception:
            pass
        return pd.DataFrame()
    else:
        if MASTER_DB.empty: return pd.DataFrame()
        
        type_str = 'FUT' if contract_type == "future" else 'OPT'
        keys_to_try = key if isinstance(key, list) else [key]
        
        filtered_df = pd.DataFrame()
        for k in keys_to_try:
            if contract_type == "future":
                regex_pattern = f"^{k}\\d{{2}}[A-Z]{{3}}FUT" 
            else:
                regex_pattern = f"^{k}\\d{{2}}"
                
            filtered_df = MASTER_DB[
                (MASTER_DB['tradingsymbol'].astype(str).str.contains(regex_pattern, na=False, regex=True)) & 
                (MASTER_DB['instrument_type'].astype(str).str.contains(type_str))
            ]
            if not filtered_df.empty:
                break
        
        if not filtered_df.empty:
            filtered_df = filtered_df.copy()
            if contract_type == "option":
                filtered_df['instrument_type'] = filtered_df['option_type']
            if 'expiry' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['expiry'] >= TODAY_STR]
            return filtered_df
        return pd.DataFrame()

# ==========================================
# 5. UNIVERSAL PROCESSING ENGINE
# ==========================================
def process_asset(name, config):
    key = config['key']
    segment = config['segment']
    strike_gap = config.get('gap', None)
    is_index = True if 'INDEX' in str(key) else False
    
    print(f"\n--- Analyzing: {name} ({segment}) ---")
    
    spot_df = pd.DataFrame()
    # ---> UPDATED TO FETCH SPOT PRICES FOR BOTH NSE & BSE <---
    if segment in ["NSE", "BSE"]:
        spot_df = fetch_1min_candles(key, TODAY_STR)
    
    if spot_df.empty:
        fut_contracts = get_live_contracts(key, "future", segment)
        if not fut_contracts.empty and 'expiry' in fut_contracts.columns:
            valid_expiries = sorted(fut_contracts['expiry'].unique())
            for exp in valid_expiries:
                f_match = fut_contracts[fut_contracts['expiry'] == exp].iloc[0]
                spot_df = fetch_1min_candles(f_match['instrument_key'], TODAY_STR)
                if not spot_df.empty:
                    sym_name = f_match.get('tradingsymbol', exp)
                    print(f"   🔄 Extracted Active Future ({sym_name}) as Base Spot")
                    break

    if spot_df.empty:
        print(f"   ⚠️ No Base data found for {name} on {TODAY_STR}. Skipping derivatives.")
        return
        
    base_file_name = f"{name}_Base_1min.csv"
    base_file_path = os.path.join(FOLDER_PATH, base_file_name)
    spot_df.to_csv(base_file_path, index=False)
    print(f"   ✅ Saved Base Data ({len(spot_df)} rows)")
    
    latest_spot = spot_df['Close'].iloc[-1]
    
    if name in MACRO_INDICATORS:
        return

    # Fetch Futures Data
    fut_contracts = get_live_contracts(key, "future", segment)
    if not fut_contracts.empty and 'expiry' in fut_contracts.columns:
        future_expiries = sorted(fut_contracts['expiry'].unique())[:3]
        for f_exp in future_expiries:
            f_match = fut_contracts[fut_contracts['expiry'] == f_exp].iloc[0]
            fut_df = fetch_1min_candles(f_match['instrument_key'], TODAY_STR)
            if not fut_df.empty:
                sym = f_match.get('tradingsymbol', f'FUT_{f_exp}')
                fut_file_name = f"{name}_{sym}_Future.csv"
                fut_file_path = os.path.join(FOLDER_PATH, fut_file_name)
                fut_df.to_csv(fut_file_path, index=False)
                print(f"   ✅ Saved Future: {sym}")
            time.sleep(0.3)

    # Fetch Options Chain & Compute Greeks
    opt_contracts = get_live_contracts(key, "option", segment)
    if not opt_contracts.empty and 'expiry' in opt_contracts.columns:
        nearest_expiry = sorted(opt_contracts['expiry'].unique())[0]
        expiry_chain = opt_contracts[opt_contracts['expiry'] == nearest_expiry]
        
        available_strikes = sorted(pd.to_numeric(expiry_chain['strike_price']).unique())
        if available_strikes:
            atm_strike = min(available_strikes, key=lambda x: abs(x - latest_spot))
            atm_idx = available_strikes.index(atm_strike)
            
            if is_index and strike_gap:
                strike_below = atm_strike - strike_gap
                strike_above = atm_strike + strike_gap
            else:
                strike_below = available_strikes[max(0, atm_idx - 1)]
                strike_above = available_strikes[min(len(available_strikes)-1, atm_idx + 1)]
            
            targets = [
                {'strike': strike_below, 'type': 'CE', 'tag': 'ITM'},
                {'strike': atm_strike,   'type': 'CE', 'tag': 'ATM'},
                {'strike': strike_above, 'type': 'CE', 'tag': 'OTM'},
                {'strike': strike_above, 'type': 'PE', 'tag': 'ITM'},
                {'strike': atm_strike,   'type': 'PE', 'tag': 'ATM'},
                {'strike': strike_below, 'type': 'PE', 'tag': 'OTM'}
            ]
            
            for t in targets:
                match = expiry_chain[(pd.to_numeric(expiry_chain['strike_price']) == t['strike']) & 
                                     (expiry_chain['instrument_type'].astype(str).str.contains(t['type']))]
                if match.empty:
                    continue
                    
                opt_df = fetch_1min_candles(match.iloc[0]['instrument_key'], TODAY_STR)
                if opt_df.empty:
                    continue
                    
                master_df = pd.merge(opt_df, spot_df[['Date', 'Close']], on='Date', how='inner', suffixes=('', '_Spot'))
                
                t_days = 7.0 if is_index else 30.0 
                master_df['T_Annual'] = t_days / 365.0
                
                try:
                    greeks = py_vollib_vectorized.get_all_greeks(
                        flag=t['type'].lower(),
                        S=master_df['Close_Spot'],
                        K=t['strike'],
                        t=master_df['T_Annual'],
                        r=RISK_FREE_RATE,
                        price=master_df['Close'],
                        return_as='dataframe'
                    )
                    master_df['IV'] = greeks['iv']
                    master_df['Delta'] = greeks['delta']
                    master_df['Gamma'] = greeks['gamma']
                    master_df['Theta'] = greeks['theta']
                    master_df['Vega'] = greeks['vega']
                    
                    opt_file_name = f"{name}_{nearest_expiry}_{t['strike']}_{t['type']}_{t['tag']}_Enriched.csv"
                    opt_file_path = os.path.join(FOLDER_PATH, opt_file_name)
                    master_df.to_csv(opt_file_path, index=False)
                except Exception:
                    pass
                time.sleep(0.3) 
                
        print(f"   ✅ Processed Options Chain & Greeks for {name}")

# ==========================================
# 6. MAIN EXECUTION
# ==========================================
def main():
    print(f"\n🚀 INITIALIZING DATA CAPTURE FOR {TODAY_STR}")

    for name, config in INDICES.items():
        process_asset(name, config)
        time.sleep(0.5)

    for name, config in MASTER_SPOT_LIST.items():
        process_asset(name, config)
        time.sleep(0.5)

    print(f"\n🎉 EXCELLENT! Master Database Updated Successfully.")

if __name__ == "__main__":
    main()
