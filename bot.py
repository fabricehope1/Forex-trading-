import requests
import pandas as pd
import time
import os

API_KEY = os.getenv("API_KEY")
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

last_update_id = None
last_signal = ""

# =========================
def get_data():
    url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=5min&outputsize=200&apikey={API_KEY}"
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
def market_status(df):
    last = df.iloc[-1]

    if last["ma20"] > last["ma50"]:
        return "📈 TRENDING UP"
    elif last["ma20"] < last["ma50"]:
        return "📉 TRENDING DOWN"
    else:
        return "⚖️ RANGING"

# =========================
def analyze():
    df = get_data()
    df = indicators(df)

    last = df.iloc[-1]

    if pd.isna(last["atr"]):
        return None

    price = last["close"]
    atr = last["atr"]
    rsi = round(last["rsi"], 1)

    ma20 = last["ma20"]
    ma50 = last["ma50"]

    status = market_status(df)

    # BUY
    if ma20 > ma50 and rsi < 55:
        return f"""📊 GOLD SIGNAL (XAUUSD)

🟢 BUY SETUP

📍 Entry Zone: {round(price-atr*0.3,2)} - {round(price+atr*0.3,2)}
🎯 TP1: {round(price+atr,2)}
🎯 TP2: {round(price+atr*2,2)}
🎯 TP3: {round(price+atr*3,2)}
🛑 SL: {round(price-atr,2)}

📊 RSI: {rsi}
{status}

✅ Confidence: HIGH"""

    # SELL
    if ma20 < ma50 and rsi > 45:
        return f"""📊 GOLD SIGNAL (XAUUSD)

🔴 SELL SETUP

📍 Entry Zone: {round(price-atr*0.3,2)} - {round(price+atr*0.3,2)}
🎯 TP1: {round(price-atr,2)}
🎯 TP2: {round(price-atr*2,2)}
🎯 TP3: {round(price-atr*3,2)}
🛑 SL: {round(price+atr,2)}

📊 RSI: {rsi}
{status}

✅ Confidence: HIGH"""

    return "❌ No clear signal now"

# =========================
def send_message(chat_id, text):
    keyboard = {
        "inline_keyboard": [
            [{"text": "📊 Get Signal", "callback_data": "signal"}]
        ]
    }

    requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "reply_markup": keyboard
    })

# =========================
def handle_updates():
    global last_update_id

    res = requests.get(f"{BASE_URL}/getUpdates", params={
        "offset": last_update_id,
        "timeout": 100
    }).json()

    for update in res["result"]:
        last_update_id = update["update_id"] + 1

        if "message" in update:
            chat_id = update["message"]["chat"]["id"]
            text = update["message"].get("text", "")

            if text == "/start":
                send_message(chat_id, "🤖 GOLD BOT ULTIMATE READY 🔥")

            elif text == "/signal":
                send_message(chat_id, analyze())

            elif text == "/status":
                df = indicators(get_data())
                send_message(chat_id, market_status(df))

            elif text == "/help":
                send_message(chat_id, "/start\n/signal\n/status\n/help")

        if "callback_query" in update:
            chat_id = update["callback_query"]["message"]["chat"]["id"]
            send_message(chat_id, analyze())

# =========================
def auto_signals():
    global last_signal

    try:
        signal = analyze()

        if signal and "❌" not in signal and signal != last_signal:
            send_message(CHAT_ID, signal)
            last_signal = signal
            print("Sent new signal")
        else:
            print("No new signal")

    except Exception as e:
        print("Error:", e)

# =========================
def main():
    while True:
        handle_updates()
        auto_signals()
        time.sleep(300)

# =========================
if __name__ == "__main__":
    main()
