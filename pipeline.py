import upstox_client
from upstox_client.rest import ApiException
import asyncio
import websockets
import json
import pandas as pd
import xgboost as xgb

# --- 1. CREDENTIALS & INITIALIZATION ---
API_KEY = "your_upstox_api_key"
API_SECRET = "your_upstox_secret"
REDIRECT_URI = "https://localhost"
ACCESS_TOKEN = "your_generated_access_token" # Usually generated via OAuth flow daily

configuration = upstox_client.Configuration()
configuration.access_token = ACCESS_TOKEN

# Load the trained Meta-Brain
ai_model = xgb.XGBClassifier()
ai_model.load_model("nifty_meta_brain_v16.json")

# In-memory buffer for the current 5-minute candle
live_candle_buffer = []

# --- 2. THE WEBSOCKET TICK STREAM ---
async def market_data_listener():
    # Upstox v2 WebSocket URL requires auth query parameters (simplified here)
    ws_url = f"wss://api.upstox.com/v2/feed/market-data-feed?token={ACCESS_TOKEN}"
    
    async with websockets.connect(ws_url) as websocket:
        print("🟢 Connected to Upstox Live Feed...")
        
        # Subscribe to NIFTY SPOT and INDIA VIX
        sub_payload = {
            "guid": "nifty_sniper_bot",
            "method": "sub",
            "data": {
                "instrumentKeys": ["NSE_INDEX|Nifty 50", "NSE_INDEX|India VIX"]
            }
        }
        await websocket.send(json.dumps(sub_payload))
        
        while True:
            response = await websocket.recv()
            tick_data = json.loads(response)
            
            # Route tick to the feature buffer
            process_live_tick(tick_data)

# --- 3. THE BUFFER & EXECUTION ROUTER ---
def process_live_tick(tick):
    global live_candle_buffer
    
    # Example parsing (depends on exact Upstox protobuf/json schema)
    price = tick.get('ltp') 
    timestamp = tick.get('exchange_timestamp')
    
    live_candle_buffer.append({'time': timestamp, 'price': price})
    
    # Check if a 5-minute boundary is crossed (e.g., 09:19:59 -> 09:20:00)
    if is_candle_closed(timestamp):
        df_state = build_live_features(live_candle_buffer)
        
        # AI Inference
        p = ai_model.predict_proba(df_state[['atr', 'z_score', 'trend_align', 'vix', 'is_opening_chaos', 'is_midday_chop']])
        
        if p[0][1] > 0.60:
            execute_order("CE", price)
        elif (1 - p[0][1]) > 0.60:
            execute_order("PE", price)
            
        # Flush buffer for the next candle
        live_candle_buffer.clear()

def execute_order(opt_type, spot_price):
    print(f"🚀 AI Confidence Threshold Breached. Firing {opt_type} Order at Spot: {spot_price}")
    # Initialize Upstox Order API instance
    api_instance = upstox_client.OrderApi(upstox_client.ApiClient(configuration))
    
    # Dynamically select the strike price (Round to nearest 50)
    strike = round(spot_price / 50) * 50
    instrument_key = get_option_instrument_key(strike, opt_type) # Helper function needed to map to Upstox key
    
    order_details = upstox_client.PlaceOrderRequest(
        quantity=65,  # 1 Nifty Lot
        product="D",  # Intraday
        validity="DAY",
        price=0.0,    # Market Order
        instrument_token=instrument_key,
        order_type="MARKET",
        transaction_type="BUY",
        disclosed_quantity=0,
        trigger_price=0.0,
        is_amo=False
    )
    
    try:
        api_response = api_instance.place_order(order_details, api_version="2.0")
        print(f"✅ Order Executed: {api_response}")
    except ApiException as e:
        print(f"❌ Order Failed: {e}")

# Run the async loop
if __name__ == "__main__":
    # asyncio.run(market_data_listener())
    pass
