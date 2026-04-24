import requests
import pandas as pd
import time
import os

API_KEY = os.getenv("API_KEY")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOL = "XAU/USD"
INTERVAL = "5min"
OUTPUT = 200

# =========================
def get_data():
    url = f"https://api.twelvedata.com/time_series?symbol={SYMBOL}&interval={INTERVAL}&outputsize={OUTPUT}&apikey={API_KEY}"
    data = requests.get(url).json()

    df = pd.DataFrame(data["values"])
    df = df.iloc[::-1]  # reverse

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
def analyze(df):
    df = indicators(df)
    last = df.iloc[-1]

    if pd.isna(last["atr"]):
        return None

    price = last["close"]
    atr = last["atr"]

    uptrend = last["ma20"] > last["ma50"]
    downtrend = last["ma20"] < last["ma50"]

    # BUY
    if uptrend and last["rsi"] < 55:
        return f"""🔥 BUY GOLD (XAUUSD)
Entry: {round(price,2)}
TP: {round(price + atr*2,2)}
SL: {round(price - atr,2)}"""

    # SELL
    if downtrend and last["rsi"] > 45:
        return f"""🔥 SELL GOLD (XAUUSD)
Entry: {round(price,2)}
TP: {round(price - atr*2,2)}
SL: {round(price + atr,2)}"""

    return None

# =========================
def send(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.get(url, params={"chat_id": CHAT_ID, "text": msg})

# =========================
def main():
    last_signal = ""

    while True:
        try:
            df = get_data()
            signal = analyze(df)

            if signal and signal != last_signal:
                send(signal)
                print(signal)
                last_signal = signal
            else:
                print("No signal")

        except Exception as e:
            print("Error:", e)

        time.sleep(300)

# =========================
if __name__ == "__main__":
    main()
