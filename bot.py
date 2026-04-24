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
bot_active = False

last_signal_sent = ""
last_presignal_sent = ""

current_trade = None

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

    support = df["low"].rolling(20).min().iloc[-1]
    resistance = df["high"].rolling(20).max().iloc[-1]

    last = df.iloc[-1]

    if pd.isna(last["atr"]):
        return "wait", "Loading...", None

    price = last["close"]
    atr = last["atr"]
    rsi = last["rsi"]

    ma20 = last["ma20"]
    ma50 = last["ma50"]

    uptrend = ma20 > ma50
    downtrend = ma20 < ma50

    near_support = abs(price - support) < atr
    near_resistance = abs(price - resistance) < atr

    # BUY SIGNAL
    if uptrend and 40 < rsi < 55 and near_support:
        entry = round(price,5)
        tp1 = round(price+atr,5)
        sl = round(price-atr,5)

        trade = {
            "type": "BUY",
            "entry": entry,
            "tp1": tp1,
            "sl": sl,
            "pair": pair
        }

        return "signal", f"""🎯 SNIPER SIGNAL ({pair})

🟢 BUY
Entry: {entry}
TP1: {tp1}
SL: {sl}""", trade

    # SELL SIGNAL
    if downtrend and 45 < rsi < 60 and near_resistance:
        entry = round(price,5)
        tp1 = round(price-atr,5)
        sl = round(price+atr,5)

        trade = {
            "type": "SELL",
            "entry": entry,
            "tp1": tp1,
            "sl": sl,
            "pair": pair
        }

        return "signal", f"""🎯 SNIPER SIGNAL ({pair})

🔴 SELL
Entry: {entry}
TP1: {tp1}
SL: {sl}""", trade

    # PRE SIGNAL
    if uptrend and rsi < 50:
        return "pre", f"🚨 Signal coming soon ({pair})", None

    if downtrend and rsi > 50:
        return "pre", f"🚨 Signal coming soon ({pair})", None

    return "wait", "Wait for signal...", None

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
        "inline_keyboard": [
            [{"text": "🥇 XAUUSD", "callback_data": "XAUUSD"}],
            [{"text": "💶 EURUSD", "callback_data": "EURUSD"}],
            [{"text": "💷 GBPUSD", "callback_data": "GBPUSD"}],
            [{"text": "💴 USDJPY", "callback_data": "USDJPY"}],
            [{"text": "🪙 BTCUSD", "callback_data": "BTCUSD"}]
        ]
    }

# =========================
def main_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "📊 Get Signal", "callback_data": "signal"}],
            [{"text": "🔙 Back", "callback_data": "back"}],
            [{"text": "🛑 Stop Bot", "callback_data": "stop"}]
        ]
    }

# =========================
def handle_updates():
    global last_update_id, user_chat_id, bot_active, current_trade

    url = f"{BASE_URL}/getUpdates"
    if last_update_id:
        url += f"?offset={last_update_id}"

    res = requests.get(url).json()

    for update in res.get("result", []):
        last_update_id = update["update_id"] + 1

        if "message" in update:
            chat_id = update["message"]["chat"]["id"]
            user_chat_id = chat_id

            if update["message"].get("text") == "/start":
                bot_active = False
                send(chat_id, "Select Pair 👇", pair_keyboard())

        if "callback_query" in update:
            chat_id = update["callback_query"]["message"]["chat"]["id"]
            user_chat_id = chat_id

            data = update["callback_query"]["data"]

            if data in ["XAUUSD","EURUSD","GBPUSD","USDJPY","BTCUSD"]:
                user_pairs[chat_id] = data
                bot_active = True
                send(chat_id, f"✅ Selected: {data}", main_keyboard())

            elif data == "signal":
                pair = user_pairs.get(chat_id)
                status, msg, trade = analyze(pair)

                if status == "signal":
                    current_trade = trade

                send(chat_id, msg, main_keyboard())

            elif data == "back":
                bot_active = False
                send(chat_id, "Select another pair 👇", pair_keyboard())

            elif data == "stop":
                bot_active = False
                send(chat_id, "🛑 Bot stopped", pair_keyboard())

# =========================
def auto_mode():
    global last_signal_sent, last_presignal_sent, current_trade

    if not user_chat_id or not bot_active:
        return

    pair = user_pairs.get(user_chat_id)

    status, msg, trade = analyze(pair)

    if status == "signal" and msg != last_signal_sent:
        send(user_chat_id, msg)
        last_signal_sent = msg
        current_trade = trade

    elif status == "pre" and msg != last_presignal_sent:
        send(user_chat_id, msg)
        last_presignal_sent = msg

# =========================
def track_trade():
    global current_trade

    if not current_trade or not user_chat_id:
        return

    df = get_data(current_trade["pair"])
    price = df.iloc[-1]["close"]

    if current_trade["type"] == "BUY":
        if price >= current_trade["tp1"]:
            send(user_chat_id, f"✅ TP1 HIT ({current_trade['pair']}) 💰")
            current_trade = None

        elif price <= current_trade["sl"]:
            send(user_chat_id, f"❌ SL HIT ({current_trade['pair']})")
            current_trade = None

    elif current_trade["type"] == "SELL":
        if price <= current_trade["tp1"]:
            send(user_chat_id, f"✅ TP1 HIT ({current_trade['pair']}) 💰")
            current_trade = None

        elif price >= current_trade["sl"]:
            send(user_chat_id, f"❌ SL HIT ({current_trade['pair']})")
            current_trade = None

# =========================
def main():
    print("FINAL BOT RUNNING...")

    while True:
        try:
            handle_updates()
            auto_mode()
            track_trade()
        except Exception as e:
            print("Error:", e)

        time.sleep(2)

# =========================
if __name__ == "__main__":
    main()
