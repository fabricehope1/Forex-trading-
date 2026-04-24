import requests
import pandas as pd
import time
import os

API_KEY = os.getenv("API_KEY")
TOKEN = os.getenv("TELEGRAM_TOKEN")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
last_update_id = None

user_pairs = {}
user_chat_id = None

last_signal_sent = ""
last_presignal_sent = ""

# =========================
def get_symbol(pair):
    mapping = {
        "XAUUSD": "XAU/USD",
        "EURUSD": "EUR/USD",
        "GBPUSD": "GBP/USD",
        "USDJPY": "USD/JPY",
        "AUDUSD": "AUD/USD",
        "USDCAD": "USD/CAD",
        "BTCUSD": "BTC/USD",
        "ETHUSD": "ETH/USD"
    }
    return mapping.get(pair, "XAU/USD")

# =========================
def get_data(pair):
    url = f"https://api.twelvedata.com/time_series?symbol={get_symbol(pair)}&interval=5min&outputsize=200&apikey={API_KEY}"
    data = requests.get(url).json()

    df = pd.DataFrame(data["values"])
    df = df.iloc[::-1]

    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)

    return df

# =========================
def indicators(df):
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma50"] = df["close"].rolling(50).mean()

    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    df["tr"] = df["high"] - df["low"]
    df["atr"] = df["tr"].rolling(14).mean()

    return df

# =========================
def analyze(pair):
    df = get_data(pair)
    df = indicators(df)

    support = df["low"].rolling(20).min().iloc[-1]
    resistance = df["high"].rolling(20).max().iloc[-1]

    last = df.iloc[-1]

    if pd.isna(last["atr"]):
        return "wait", "⏳ Loading..."

    price = last["close"]
    atr = last["atr"]
    rsi = last["rsi"]

    ma20 = last["ma20"]
    ma50 = last["ma50"]

    uptrend = ma20 > ma50
    downtrend = ma20 < ma50

    near_support = abs(price - support) < atr
    near_resistance = abs(price - resistance) < atr

    # SNIPER SIGNAL
    if uptrend and 40 < rsi < 55 and near_support:
        return "signal", f"""🎯 SNIPER SIGNAL ({pair})

🟢 BUY
Entry: {round(price,5)}
TP1: {round(price+atr,5)}
TP2: {round(price+atr*2,5)}
SL: {round(price-atr,5)}

🔥 HIGH ACCURACY"""

    if downtrend and 45 < rsi < 60 and near_resistance:
        return "signal", f"""🎯 SNIPER SIGNAL ({pair})

🔴 SELL
Entry: {round(price,5)}
TP1: {round(price-atr,5)}
TP2: {round(price-atr*2,5)}
SL: {round(price+atr,5)}

🔥 HIGH ACCURACY"""

    # PRE SIGNAL
    if uptrend and rsi < 50:
        return "pre", f"⚠️ PRE-SIGNAL BUY ({pair})"

    if downtrend and rsi > 50:
        return "pre", f"⚠️ PRE-SIGNAL SELL ({pair})"

    # AI PREDICTION
    prediction = "UP 📈" if uptrend else "DOWN 📉"
    return "wait", f"""🤖 AI UPDATE ({pair})

📊 Price: {round(price,5)}
📊 RSI: {round(rsi,1)}

📈 Market: {prediction}

⏳ Waiting for setup..."""

# =========================
def send(chat_id, text, keyboard=None):
    requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "reply_markup": keyboard
    })

# =========================
def main_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "📊 Get Signal", "callback_data": "signal"}],
            [{"text": "⚙️ Select Pair", "callback_data": "select_pair"}]
        ]
    }

# =========================
def pair_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🥇 XAUUSD", "callback_data": "XAUUSD"}],
            [{"text": "💶 EURUSD", "callback_data": "EURUSD"}],
            [{"text": "💷 GBPUSD", "callback_data": "GBPUSD"}],
            [{"text": "💴 USDJPY", "callback_data": "USDJPY"}],
            [{"text": "🇦🇺 AUDUSD", "callback_data": "AUDUSD"}],
            [{"text": "🇨🇦 USDCAD", "callback_data": "USDCAD"}],
            [{"text": "🪙 BTCUSD", "callback_data": "BTCUSD"}],
            [{"text": "💎 ETHUSD", "callback_data": "ETHUSD"}]
        ]
    }

# =========================
def handle_updates():
    global last_update_id, user_chat_id

    url = f"{BASE_URL}/getUpdates"
    if last_update_id:
        url += f"?offset={last_update_id}"

    res = requests.get(url).json()

    for update in res.get("result", []):
        last_update_id = update["update_id"] + 1

        if "message" in update:
            chat_id = update["message"]["chat"]["id"]
            user_chat_id = chat_id

            text = update["message"].get("text", "")

            if text == "/start":
                user_pairs[chat_id] = "XAUUSD"
                send(chat_id, "🤖 SNIPER BOT READY 🔥", main_keyboard())

            elif text == "/signal":
                pair = user_pairs.get(chat_id, "XAUUSD")
                status, msg = analyze(pair)
                send(chat_id, msg, main_keyboard())

        if "callback_query" in update:
            chat_id = update["callback_query"]["message"]["chat"]["id"]
            user_chat_id = chat_id

            data = update["callback_query"]["data"]

            if data == "signal":
                pair = user_pairs.get(chat_id, "XAUUSD")
                status, msg = analyze(pair)
                send(chat_id, msg, main_keyboard())

            elif data == "select_pair":
                send(chat_id, "Select Pair 👇", pair_keyboard())

            elif data in ["XAUUSD","EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","BTCUSD","ETHUSD"]:
                user_pairs[chat_id] = data
                send(chat_id, f"✅ Selected: {data}", main_keyboard())

# =========================
def auto_mode():
    global last_signal_sent, last_presignal_sent

    if not user_chat_id:
        return

    pair = user_pairs.get(user_chat_id, "XAUUSD")

    status, msg = analyze(pair)

    if status == "signal" and msg != last_signal_sent:
        send(user_chat_id, msg)
        last_signal_sent = msg

    elif status == "pre" and msg != last_presignal_sent:
        send(user_chat_id, msg)
        last_presignal_sent = msg

# =========================
def main():
    print("PRIVATE AUTO BOT RUNNING...")

    while True:
        try:
            handle_updates()
            auto_mode()
        except Exception as e:
            print("Error:", e)

        time.sleep(2)

# =========================
if __name__ == "__main__":
    main()
