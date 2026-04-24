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

    support = df["low"].rolling(20).min().iloc[-1]
    resistance = df["high"].rolling(20).max().iloc[-1]

    last = df.iloc[-1]

    if pd.isna(last["atr"]):
        return "⏳ Loading market data..."

    price = last["close"]
    atr = last["atr"]
    rsi = round(last["rsi"], 1)

    ma20 = last["ma20"]
    ma50 = last["ma50"]

    # Trend
    if ma20 > ma50:
        trend = "UP"
    else:
        trend = "DOWN"

    # Strength
    strength_val = abs(ma20 - ma50)
    if strength_val > 1:
        strength = "STRONG"
        confidence = "VERY HIGH"
    else:
        strength = "WEAK"
        confidence = "MEDIUM"

    # Breakout
    breakout_up = price > resistance * 0.995
    breakout_down = price < support * 1.005

    # ================= BUY =================
    if trend == "UP":
        return f"""📊 GOLD VIP SIGNAL (XAUUSD)

🟢 BUY SETUP

📍 Entry Zone: {round(price-atr*0.3,2)} - {round(price+atr*0.3,2)}
🎯 TP1: {round(price+atr,2)}
🎯 TP2: {round(price+atr*2,2)}
🎯 TP3: {round(price+atr*3,2)}
🛑 SL: {round(price-atr,2)}

📊 RSI: {rsi}
📈 Trend: {strength} UP
📌 Support: {round(support,2)}
📌 Resistance: {round(resistance,2)}

🔥 Breakout: {"CONFIRMED" if breakout_up else "WAIT"}
✅ Confidence: {confidence}"""

    # ================= SELL =================
    else:
        return f"""📊 GOLD VIP SIGNAL (XAUUSD)

🔴 SELL SETUP

📍 Entry Zone: {round(price-atr*0.3,2)} - {round(price+atr*0.3,2)}
🎯 TP1: {round(price-atr,2)}
🎯 TP2: {round(price-atr*2,2)}
🎯 TP3: {round(price-atr*3,2)}
🛑 SL: {round(price+atr,2)}

📊 RSI: {rsi}
📉 Trend: {strength} DOWN
📌 Support: {round(support,2)}
📌 Resistance: {round(resistance,2)}

🔥 Breakout: {"CONFIRMED" if breakout_down else "WAIT"}
✅ Confidence: {confidence}"""

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
                send_message(chat_id, "🤖 GOLD VIP BOT READY 🔥\nClick below 👇")

            elif text == "/signal":
                send_message(chat_id, analyze())

            elif text == "/help":
                send_message(chat_id, "/start\n/signal\n/help")

        # BUTTON
        if "callback_query" in update:
            chat_id = update["callback_query"]["message"]["chat"]["id"]
            send_message(chat_id, analyze())

# =========================
def main():
    print("VIP BOT RUNNING...")

    while True:
        try:
            handle_updates()
        except Exception as e:
            print("Error:", e)

        time.sleep(2)

# =========================
if __name__ == "__main__":
    main()
