import requests
import pandas as pd
import time
import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOL = "XAUUSDT"
INTERVAL = "5m"
LIMIT = 300

# =========================
def get_data():
    url = f"https://api.binance.com/api/v3/klines?symbol={SYMBOL}&interval={INTERVAL}&limit={LIMIT}"
    data = requests.get(url, timeout=10).json()

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "close_time","qav","trades","tbbav","tbqav","ignore"
    ])
    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    return df

# =========================
def calculate_indicators(df):
    df["ma50"] = df["close"].rolling(50).mean()
    df["ma200"] = df["close"].rolling(200).mean()

    # RSI
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    # ATR (volatility)
    df["tr"] = df["high"] - df["low"]
    df["atr"] = df["tr"].rolling(14).mean()

    return df

# =========================
def support_resistance(df):
    support = df["low"].rolling(20).min().iloc[-1]
    resistance = df["high"].rolling(20).max().iloc[-1]
    return support, resistance

# =========================
def analyze(df):
    df = calculate_indicators(df)
    support, resistance = support_resistance(df)

    last = df.iloc[-1]
    price = round(last["close"], 2)
    atr = last["atr"]

    # Trend
    uptrend = last["ma50"] > last["ma200"]
    downtrend = last["ma50"] < last["ma200"]

    # ================= BUY =================
    if uptrend and last["rsi"] < 40 and price > support:
        tp = round(price + (atr * 2), 2)
        sl = round(price - (atr * 1.2), 2)

        return f"""🔥 BUY GOLD (PRO)
Entry: {price}
TP: {tp}
SL: {sl}
RSI: {round(last['rsi'],1)}
Trend: UP"""

    # ================= SELL =================
    if downtrend and last["rsi"] > 60 and price < resistance:
        tp = round(price - (atr * 2), 2)
        sl = round(price + (atr * 1.2), 2)

        return f"""🔥 SELL GOLD (PRO)
Entry: {price}
TP: {tp}
SL: {sl}
RSI: {round(last['rsi'],1)}
Trend: DOWN"""

    return None

# =========================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.get(url, params={"chat_id": CHAT_ID, "text": message})

# =========================
last_signal = ""

while True:
    try:
        df = get_data()
        signal = analyze(df)

        if signal and signal != last_signal:
            send_telegram(signal)
            print(signal)
            last_signal = signal
        else:
            print("No signal")

    except Exception as e:
        print("Error:", e)

    time.sleep(300)
