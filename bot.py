import requests
import pandas as pd
import time
import os

API_KEY = os.getenv("API_KEY")

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

SYMBOL = "XAU/USD"
INTERVAL = "5min"

last_update_id = None
last_signal = ""

# =========================
def get_data():
    url = f"https://api.twelvedata.com/time_series?symbol={SYMBOL}&interval={INTERVAL}&outputsize=200&apikey={API_KEY}"
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
def analyze():
    df = get_data()
    df = indicators(df)

    last = df.iloc[-1]

    if pd.isna(last["atr"]):
        return "No data yet..."

    price = last["close"]
    atr = last["atr"]

    uptrend = last["ma20"] > last["ma50"]
    downtrend = last["ma20"] < last["ma50"]

    if uptrend and last["rsi"] < 55:
        return f"""🔥 BUY GOLD (XAUUSD)
Entry: {round(price,2)}
TP: {round(price + atr*2,2)}
SL: {round(price - atr,2)}"""

    if downtrend and last["rsi"] > 45:
        return f"""🔥 SELL GOLD (XAUUSD)
Entry: {round(price,2)}
TP: {round(price - atr*2,2)}
SL: {round(price + atr,2)}"""

    return "❌ No clear signal now"

# =========================
def send(chat_id, text):
    requests.get(f"{BASE_URL}/sendMessage", params={
        "chat_id": chat_id,
        "text": text
    })

# =========================
def check_messages():
    global last_update_id

    url = f"{BASE_URL}/getUpdates"
    params = {"timeout": 100, "offset": last_update_id}

    res = requests.get(url, params=params).json()

    for update in res["result"]:
        last_update_id = update["update_id"] + 1

        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")

        # ===== COMMANDS =====
        if text == "/start":
            send(chat_id, "🤖 GOLD BOT READY\n\nType /signal to get trade signal")

        elif text == "/signal":
            result = analyze()
            send(chat_id, result)

        elif text == "/help":
            send(chat_id, "/start\n/signal\n/help")

# =========================
def auto_signal():
    global last_signal

    try:
        signal = analyze()

        if "BUY" in signal or "SELL" in signal:
            if signal != last_signal:
                send(CHAT_ID, signal)
                print(signal)
                last_signal = signal
    except Exception as e:
        print("Error:", e)

# =========================
while True:
    check_messages()   # reply to user
    auto_signal()      # send auto signals
    time.sleep(30)
