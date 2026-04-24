import requests
import pandas as pd
import time
import os

API_KEY = os.getenv("API_KEY")
TOKEN = os.getenv("TELEGRAM_TOKEN")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
last_update_id = None

user_pair = None
user_chat_id = None
bot_active = False

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

    last = df.iloc[-1]

    price = last["close"]
    atr = last["atr"]
    rsi = last["rsi"]

    ma20 = last["ma20"]
    ma50 = last["ma50"]

    uptrend = ma20 > ma50

    # ===== CONFIDENCE =====
    score = 0

    if ma20 > ma50 or ma20 < ma50:
        score += 25

    if 40 < rsi < 60:
        score += 25

    if atr < price * 0.01:
        score += 25

    if abs(df["close"].iloc[-1] - df["close"].iloc[-2]) > atr * 0.2:
        score += 25

    confidence = score

    if confidence >= 80:
        strength = "🔥 STRONG"
    elif confidence >= 65:
        strength = "⚡ MEDIUM"
    else:
        strength = "⚠️ WEAK"

    # ===== SIGNAL =====
    entry = round(price,5)

    if uptrend:
        tp1 = round(price + atr,5)
        sl = round(price - atr,5)
        trade_type = "BUY"
    else:
        tp1 = round(price - atr,5)
        sl = round(price + atr,5)
        trade_type = "SELL"

    trade = {
        "type": trade_type,
        "tp1": tp1,
        "sl": sl,
        "pair": pair
    }

    return f"""🎯 SNIPER SIGNAL ({pair})

{'🟢 BUY' if trade_type=='BUY' else '🔴 SELL'}
Entry: {entry}
TP1: {tp1}
SL: {sl}

📊 Confidence: {confidence}%
⚡ Strength: {strength}""", trade

# =========================
def send(chat_id, text, keyboard=None):
    requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "reply_markup": keyboard
    })

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
    global last_update_id, user_chat_id, bot_active, user_pair, current_trade

    url = f"{BASE_URL}/getUpdates"
    if last_update_id:
        url += f"?offset={last_update_id}"

    res = requests.get(url).json()

    for update in res.get("result", []):
        last_update_id = update["update_id"] + 1

        if "message" in update:
            chat_id = update["message"]["chat"]["id"]
            user_chat_id = chat_id
            text = update["message"].get("text","")

            if text == "/start":
                bot_active = False
                current_trade = None
                send(chat_id,"Select Pair 👇",pair_keyboard())

            elif text in ["XAUUSD","EURUSD","GBPUSD","USDJPY","BTCUSD"]:
                user_pair = text
                bot_active = True
                send(chat_id,f"✅ Selected: {text}",main_keyboard())

            elif text == "📊 Get Signal":
                if current_trade:
                    send(chat_id,"⏳ Wait current trade to finish")
                else:
                    msg,trade = analyze(user_pair)
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
                bot_active = False
                current_trade = None
                send(chat_id,"Select Pair 👇",pair_keyboard())

            elif text == "🛑 Stop":
                bot_active = False
                current_trade = None
                send(chat_id,"🛑 Bot stopped",pair_keyboard())

# =========================
def track_trade():
    global current_trade, wins, losses

    if not current_trade:
        return

    df = get_data(current_trade["pair"])
    price = df.iloc[-1]["close"]

    tp = current_trade["tp1"]
    sl = current_trade["sl"]

    buffer = abs(tp - sl) * 0.05  # small tolerance

    # BUY
    if current_trade["type"] == "BUY":
        if price >= tp - buffer:
            wins += 1
            send(user_chat_id,f"""✅ TP HIT 💰

Pair: {current_trade['pair']}
Result: WIN

Wins: {wins}
Losses: {losses}""")
            current_trade = None

        elif price <= sl + buffer:
            losses += 1
            send(user_chat_id,f"""❌ SL HIT

Pair: {current_trade['pair']}
Result: LOSS

Wins: {wins}
Losses: {losses}""")
            current_trade = None

    # SELL
    elif current_trade["type"] == "SELL":
        if price <= tp + buffer:
            wins += 1
            send(user_chat_id,f"""✅ TP HIT 💰

Pair: {current_trade['pair']}
Result: WIN

Wins: {wins}
Losses: {losses}""")
            current_trade = None

        elif price >= sl - buffer:
            losses += 1
            send(user_chat_id,f"""❌ SL HIT

Pair: {current_trade['pair']}
Result: LOSS

Wins: {wins}
Losses: {losses}""")
            current_trade = None

# =========================
def main():
    print("BOT RUNNING FINAL VERSION...")

    while True:
        try:
            handle_updates()
            track_trade()
        except Exception as e:
            print("Error:",e)

        time.sleep(1)

# =========================
if __name__ == "__main__":
    main()
