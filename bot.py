import requests
import pandas as pd
import time
import os
import random

API_KEY = os.getenv("API_KEY")
TOKEN = os.getenv("TELEGRAM_TOKEN")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
last_update_id = None

user_pair = None
user_chat_id = None

current_trade = None

wins = 0
losses = 0

# =========================
def get_symbol(pair):
    return {
        "XAUUSD": "XAU/USD",
        "EURUSD": "EUR/USD",
        "GBPUSD": "GBP/USD",
        "USDJPY": "USD/JPY",
        "BTCUSD": "BTC/USD"
    }.get(pair, "XAU/USD")

# =========================
def get_data(pair):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={get_symbol(pair)}&interval=5min&outputsize=200&apikey={API_KEY}"
        res = requests.get(url, timeout=10).json()

        if "values" not in res:
            print("API ERROR:", res)
            return None

        df = pd.DataFrame(res["values"])
        df = df.iloc[::-1]

        df["close"] = df["close"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)

        return df

    except Exception as e:
        print("DATA ERROR:", e)
        return None

# =========================
def indicators(df):
    df["tr"] = df["high"] - df["low"]
    df["atr"] = df["tr"].rolling(14).mean()
    return df

# =========================
def analyze(pair):
    df = get_data(pair)

    if df is None or len(df) < 50:
        return "❌ Market data error. Try again", None

    df = indicators(df)

    last = df.iloc[-1]

    price = last["close"]
    atr = last["atr"]

    if pd.isna(atr):
        return "❌ Waiting for market data...", None

    entry = round(price, 5)

    # 🔥 ALWAYS SIGNAL (random direction but realistic TP/SL)
    trade_type = random.choice(["BUY", "SELL"])

    if trade_type == "BUY":
        tp1 = round(price + atr, 5)
        sl = round(price - atr, 5)
    else:
        tp1 = round(price - atr, 5)
        sl = round(price + atr, 5)

    trade = {
        "type": trade_type,
        "tp1": tp1,
        "sl": sl,
        "pair": pair
    }

    msg = f"""🎯 SIGNAL ({pair})

{'🟢 BUY' if trade_type=='BUY' else '🔴 SELL'}
Entry: {entry}
TP: {tp1}
SL: {sl}

⚡ Instant signal mode"""

    return msg, trade

# =========================
def send(chat_id, text, keyboard=None):
    try:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "reply_markup": keyboard
        })
    except Exception as e:
        print("SEND ERROR:", e)

# =========================
def pair_keyboard():
    return {
        "keyboard": [
            ["XAUUSD","EURUSD"],
            ["GBPUSD","USDJPY"],
            ["BTCUSD"]
        ],
        "resize_keyboard": True
    }

# =========================
def main_keyboard():
    return {
        "keyboard": [
            ["📊 Get Signal"],
            ["📈 Stats"],
            ["🔙 Back","🛑 Stop"]
        ],
        "resize_keyboard": True
    }

# =========================
def handle_updates():
    global last_update_id, user_chat_id, user_pair, current_trade

    try:
        url = f"{BASE_URL}/getUpdates"
        if last_update_id:
            url += f"?offset={last_update_id}"

        res = requests.get(url, timeout=10).json()

        for update in res.get("result", []):
            last_update_id = update["update_id"] + 1

            if "message" in update:
                chat_id = update["message"]["chat"]["id"]
                user_chat_id = chat_id
                text = update["message"].get("text","")

                if text == "/start":
                    current_trade = None
                    send(chat_id,"Select Pair 👇",pair_keyboard())

                elif text in ["XAUUSD","EURUSD","GBPUSD","USDJPY","BTCUSD"]:
                    user_pair = text
                    send(chat_id,f"✅ Selected: {text}",main_keyboard())

                elif text == "📊 Get Signal":

                    if not user_pair:
                        send(chat_id,"❗ Select pair first")
                        return

                    if current_trade:
                        send(chat_id,"⏳ Wait current trade to finish")
                        return

                    msg, trade = analyze(user_pair)

                    if trade is None:
                        send(chat_id,msg)
                        return

                    current_trade = trade
                    send(chat_id,msg,main_keyboard())

                elif text == "📈 Stats":
                    total = wins + losses
                    winrate = (wins/total*100) if total>0 else 0

                    send(chat_id,f"""📊 PERFORMANCE

Wins: {wins}
Losses: {losses}
Win Rate: {round(winrate,2)}%""",main_keyboard())

                elif text == "🔙 Back":
                    current_trade = None
                    send(chat_id,"Select Pair 👇",pair_keyboard())

                elif text == "🛑 Stop":
                    current_trade = None
                    send(chat_id,"🛑 Bot stopped",pair_keyboard())

    except Exception as e:
        print("UPDATE ERROR:", e)

# =========================
def track_trade():
    global current_trade, wins, losses

    if not current_trade:
        return

    df = get_data(current_trade["pair"])
    if df is None:
        return

    price = df.iloc[-1]["close"]

    tp = current_trade["tp1"]
    sl = current_trade["sl"]

    buffer = abs(tp - sl) * 0.05

    if current_trade["type"] == "BUY":
        if price >= tp - buffer:
            wins += 1
            send(user_chat_id,f"✅ TP HIT 💰\nWins: {wins}\nLosses: {losses}")
            current_trade = None

        elif price <= sl + buffer:
            losses += 1
            send(user_chat_id,f"❌ SL HIT\nWins: {wins}\nLosses: {losses}")
            current_trade = None

    elif current_trade["type"] == "SELL":
        if price <= tp + buffer:
            wins += 1
            send(user_chat_id,f"✅ TP HIT 💰\nWins: {wins}\nLosses: {losses}")
            current_trade = None

        elif price >= sl - buffer:
            losses += 1
            send(user_chat_id,f"❌ SL HIT\nWins: {wins}\nLosses: {losses}")
            current_trade = None

# =========================
def main():
    print("BOT RUNNING FINAL (NO FAIL VERSION)...")

    while True:
        try:
            handle_updates()
            track_trade()
        except Exception as e:
            print("MAIN ERROR:", e)

        time.sleep(10)

# =========================
if __name__ == "__main__":
    main()
