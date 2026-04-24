import requests
import pandas as pd
import time
import os

API_KEY = os.getenv("API_KEY")
TOKEN = os.getenv("TELEGRAM_TOKEN")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

last_update_id = None

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
def analyze():
    df = get_data()
    df = indicators(df)

    last = df.iloc[-1]

    if pd.isna(last["atr"]):
        return "⏳ Loading market data..."

    price = last["close"]
    atr = last["atr"]
    rsi = round(last["rsi"], 1)

    ma20 = last["ma20"]
    ma50 = last["ma50"]

    # DETERMINE TREND (ALWAYS GIVE SIGNAL)
    if ma20 > ma50:
        return f"""📊 GOLD SIGNAL (XAUUSD)

🟢 BUY SETUP

📍 Entry: {round(price,2)}
🎯 TP1: {round(price+atr,2)}
🎯 TP2: {round(price+atr*2,2)}
🎯 TP3: {round(price+atr*3,2)}
🛑 SL: {round(price-atr,2)}

📊 RSI: {rsi}
📈 Trend: UP

⚡ Mode: ALWAYS SIGNAL"""

    else:
        return f"""📊 GOLD SIGNAL (XAUUSD)

🔴 SELL SETUP

📍 Entry: {round(price,2)}
🎯 TP1: {round(price-atr,2)}
🎯 TP2: {round(price-atr*2,2)}
🎯 TP3: {round(price-atr*3,2)}
🛑 SL: {round(price+atr,2)}

📊 RSI: {rsi}
📉 Trend: DOWN

⚡ Mode: ALWAYS SIGNAL"""

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

    url = f"{BASE_URL}/getUpdates"
    if last_update_id:
        url += f"?offset={last_update_id}"

    res = requests.get(url).json()

    for update in res.get("result", []):
        last_update_id = update["update_id"] + 1

        # MESSAGE
        if "message" in update:
            chat_id = update["message"]["chat"]["id"]
            text = update["message"].get("text", "")

            if text == "/start":
                send_message(chat_id, "🤖 GOLD BOT READY 🔥\nClick button 👇")

            elif text == "/signal":
                send_message(chat_id, analyze())

        # BUTTON CLICK
        if "callback_query" in update:
            chat_id = update["callback_query"]["message"]["chat"]["id"]
            send_message(chat_id, analyze())

# =========================
def main():
    print("Bot is running...")

    while True:
        try:
            handle_updates()
        except Exception as e:
            print("Error:", e)

        time.sleep(2)

# =========================
if __name__ == "__main__":
    main()
