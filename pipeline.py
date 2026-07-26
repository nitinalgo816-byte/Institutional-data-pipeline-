import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
import urllib.parse
import os
import sys
import py_vollib_vectorized
import io

# ==========================================
# 1. SETUP & CONFIGURATION (TOKEN FROM ENV)
# ==========================================
# GitHub Actions will pass the daily token securely via environment variables
ACCESS_TOKEN = os.environ.get('UPSTOX_ACCESS_TOKEN')

if not ACCESS_TOKEN:
    print("🚨 Error: UPSTOX_ACCESS_TOKEN is missing!")
    sys.exit(1)

HEADERS = {
    'Accept': 'application/json',
    'Authorization': f'Bearer {ACCESS_TOKEN}'
}

RISK_FREE_RATE = 0.07

# Target Date: Today (or Friday if run on weekends)
now = datetime.today()
if now.weekday() == 5:    # Saturday -> Friday
    target_date = now - timedelta(days=1)
elif now.weekday() == 6:  # Sunday -> Friday
    target_date = now - timedelta(days=2)
else:
    target_date = now

TODAY_STR = target_date.strftime('%Y-%m-%d')
print(f"📅 Target Data Date set to: {TODAY_STR} ({target_date.strftime('%A')})")

FOLDER_PATH = f'Institutional_Master_Archive_{TODAY_STR}/'
if not os.path.exists(FOLDER_PATH):
    os.makedirs(FOLDER_PATH)

# ==========================================
# 2. DOWNLOAD MASTER INSTRUMENT DATABASE
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
# 3. ASSET UNIVERSE DICTIONARIES
# ==========================================
INDICES = {
    'NIFTY_50': {'key': 'NSE_INDEX|Nifty 50', 'segment': 'NSE', 'gap': 50},
    'BANKNIFTY': {'key': 'NSE_INDEX|Nifty Bank', 'segment': 'NSE', 'gap': 100},
    'FINNIFTY': {'key': 'NSE_INDEX|Nifty Fin Service', 'segment': 'NSE', 'gap': 50}
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
    'GOLD_Standard': {'key': 'GOLD', 'segment': 'MCX'},
    'GOLD_Ten': {'key': ['GOLD10G', 'GOLD10'], 'segment': 'MCX'},
    'GOLD_Mini': {'key': 'GOLDM', 'segment': 'MCX'},
    'GOLD_Guinea': {'key': 'GOLDGUINEA', 'segment': 'MCX'},
    'GOLD_Petal': {'key': 'GOLDPETAL', 'segment': 'MCX'},
    'SILVER_Standard': {'key': 'SILVER', 'segment': 'MCX'},
    'SILVER_100': {'key': ['SILVER100', 'SILVER100G'], 'segment': 'MCX'},
    'SILVER_Mini': {'key': 'SILVERM', 'segment': 'MCX'},
    'SILVER_Micro': {'key': 'SILVERMIC', 'segment': 'MCX'},
    'CRUDEOIL': {'key': 'CRUDEOIL', 'segment': 'MCX'},
    'NATURALGAS': {'key': 'NATURALGAS', 'segment': 'MCX'},
    'ALUMINIUM_Standard': {'key': 'ALUMINIUM', 'segment': 'MCX'},
    'ALUMINIUM_Mini': {'key': 'ALUMINI', 'segment': 'MCX'},
    'COPPER_Standard': {'key': 'COPPER', 'segment': 'MCX'},
    'COPPER_Mini': {'key': ['COPMINI', 'COPPERMINI', 'COPPERM'], 'segment': 'MCX'},
    'LEAD_Standard': {'key': 'LEAD', 'segment': 'MCX'},
    'LEAD_Mini': {'key': 'LEADMINI', 'segment': 'MCX'},
    'ZINC_Standard': {'key': 'ZINC', 'segment': 'MCX'},
    'ZINC_Mini': {'key': 'ZINCMINI', 'segment': 'MCX'},
    'NICKEL_Standard': {'key': 'NICKEL', 'segment': 'MCX'},
    'NICKEL_Mini': {'key': ['NICKELM', 'NICKELMINI'], 'segment': 'MCX'}
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
    for sym in NIFTS if 'NIFTS' in locals() else NIFTY_200_SYMBOLS:
        match = eq_df[eq_df['tradingsymbol'] == sym]
        if not match.empty:
            EQUITY_ASSETS[sym] = {'key': match.iloc[0]['instrument_key'], 'segment': 'NSE'}

MASTER_SPOT_LIST = {**MACRO_INDICATORS, **CURRENCIES, **MCX_COMMODITIES, **EQUITY_ASSETS}

# ==========================================
# 4. FUNCTIONS
# ==========================================
def fetch_1min_candles(instrument_key, date_str):
    encoded_key = urllib.parse.quote(instrument_key)
    url = f"https://api.upstox.com/v3/historical-candle/{encoded_key}/minutes/1/{date_str}/{date_str}"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            res_data = response.json()
            if 'data' in res_data and res_data['data']['candles']:
                df = pd.DataFrame(res_data['data']['candles'], 
                                  columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'OpenInterest'])
                df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
                return df.sort_values('Date').reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame()

def get_live_contracts(key, contract_type="future", segment="NSE"):
    if segment == "NSE":
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
            regex_pattern = f"^{k}\\d{{2}}[A-Z]{{3}}FUT" if contract_type == "future" else f"^{k}\\d{{2}}"
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

def process_asset(name, config):
    key = config['key']
    segment = config['segment']
    strike_gap = config.get('gap', None)
    is_index = True if 'INDEX' in str(key) else False
    
    print(f"\n--- Analyzing: {name} ({segment}) ---")
    spot_df = pd.DataFrame()
    if segment == "NSE":
        spot_df = fetch_1min_candles(key, TODAY_STR)
    
    if spot_df.empty:
        fut_contracts = get_live_contracts(key, "future", segment)
        if not fut_contracts.empty and 'expiry' in fut_contracts.columns:
            for exp in sorted(fut_contracts['expiry'].unique()):
                f_match = fut_contracts[fut_contracts['expiry'] == exp].iloc[0]
                spot_df = fetch_1min_candles(f_match['instrument_key'], TODAY_STR)
                if not spot_df.empty:
                    break

    if spot_df.empty:
        return
        
    spot_df.to_csv(f"{FOLDER_PATH}{name}_Base_1min.csv", index=False)
    latest_spot = spot_df['Close'].iloc[-1]
    if name in MACRO_INDICATORS:
        return

    fut_contracts = get_live_contracts(key, "future", segment)
    if not fut_contracts.empty and 'expiry' in fut_contracts.columns:
        for f_exp in sorted(fut_contracts['expiry'].unique())[:3]:
            f_match = fut_contracts[fut_contracts['expiry'] == f_exp].iloc[0]
            fut_df = fetch_1min_candles(f_match['instrument_key'], TODAY_STR)
            if not fut_df.empty:
                sym = f_match.get('tradingsymbol', f'FUT_{f_exp}')
                fut_df.to_csv(f"{FOLDER_PATH}{name}_{sym}_Future.csv", index=False)
            time.sleep(0.2)

    opt_contracts = get_live_contracts(key, "option", segment)
    if not opt_contracts.empty and 'expiry' in opt_contracts.columns:
        nearest_expiry = sorted(opt_contracts['expiry'].unique())[0]
        expiry_chain = opt_contracts[opt_contracts['expiry'] == nearest_expiry]
        available_strikes = sorted(pd.to_numeric(expiry_chain['strike_price']).unique())
        if available_strikes:
            atm_strike = min(available_strikes, key=lambda x: abs(x - latest_spot))
            atm_idx = available_strikes.index(atm_strike)
            strike_below = atm_strike - strike_gap if (is_index and strike_gap) else available_strikes[max(0, atm_idx - 1)]
            strike_above = atm_strike + strike_gap if (is_index and strike_gap) else available_strikes[min(len(available_strikes)-1, atm_idx + 1)]
            
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
                if match.empty: continue
                opt_df = fetch_1min_candles(match.iloc[0]['instrument_key'], TODAY_STR)
                if opt_df.empty: continue
                master_df = pd.merge(opt_df, spot_df[['Date', 'Close']], on='Date', how='inner', suffixes=('', '_Spot'))
                master_df['T_Annual'] = (7.0 if is_index else 30.0) / 365.0
                try:
                    greeks = py_vollib_vectorized.get_all_greeks(
                        flag=t['type'].lower(), S=master_df['Close_Spot'], K=t['strike'],
                        t=master_df['T_Annual'], r=RISK_FREE_RATE, price=master_df['Close'], return_as='dataframe'
                    )
                    master_df['IV'] = greeks['iv']
                    master_df['Delta'] = greeks['delta']
                    master_df['Gamma'] = greeks['gamma']
                    master_df['Theta'] = greeks['theta']
                    master_df['Vega'] = greeks['vega']
                    master_df.to_csv(f"{FOLDER_PATH}{name}_{nearest_expiry}_{t['strike']}_{t['type']}_{t['tag']}_Enriched.csv", index=False)
                except Exception:
                    pass
                time.sleep(0.2)

# ==========================================
# 5. EXECUTION
# ==========================================
print(f"\n🚀 STARTING PIPELINE FOR {TODAY_STR}")
for name, config in INDICES.items():
    process_asset(name, config)
for name, config in MASTER_SPOT_LIST.items():
    process_asset(name, config)
print("\n🎉 PIPELINE FINISHED SUCCESSFULLY.")