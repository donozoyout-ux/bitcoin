import pandas as pd
import numpy as np


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta.where(delta < 0, 0.0))
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    for i in range(period, len(avg_gain)):
        avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_bollinger(df: pd.DataFrame, period: int = 20, std_mult: float = 2.0) -> dict:
    sma = df["close"].rolling(window=period).mean()
    std = df["close"].rolling(window=period).std()
    return {
        "sma": sma,
        "upper": sma + (std_mult * std),
        "lower": sma - (std_mult * std),
    }


def calculate_ema(df: pd.DataFrame, period: int = 200) -> pd.Series:
    return df["close"].ewm(span=period, adjust=False).mean()


def calculate_macd(df: pd.DataFrame) -> dict:
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal
    return {"macd": macd_line, "signal": signal, "histogram": histogram}


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=period, min_periods=period).mean()
    return atr


def add_all_indicators(df: pd.DataFrame, config) -> pd.DataFrame:
    df = df.copy()
    df["rsi"] = calculate_rsi(df, period=14)
    bollinger = calculate_bollinger(df)
    df["bollinger_sma"] = bollinger["sma"]
    df["bollinger_upper"] = bollinger["upper"]
    df["bollinger_lower"] = bollinger["lower"]
    df["ema_50"] = calculate_ema(df, period=50)
    df["ema_200"] = calculate_ema(df, period=200)
    macd = calculate_macd(df)
    df["macd"] = macd["macd"]
    df["macd_signal"] = macd["signal"]
    df["macd_histogram"] = macd["histogram"]
    df["atr"] = calculate_atr(df)
    return df


class SignalResult:
    def __init__(self):
        self.action = "HOLD"
        self.strength = 0
        self.reasons = []
        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0

    def __repr__(self):
        return f"Signal(action={self.action}, strength={self.strength}, reasons={self.reasons})"


def generate_signals(row: pd.Series, config) -> SignalResult:
    result = SignalResult()
    score = 0

    if pd.isna(row.get("rsi")) or pd.isna(row.get("bollinger_lower")):
        return result

    current_price = row["close"]

    # --- LONG SIGNALS ---
    if row["rsi"] < config.RSI_OVERSOLD:
        score += 2
        result.reasons.append(f"RSI asiri satim ({row['rsi']:.1f} < {config.RSI_OVERSOLD})")

    if current_price <= row["bollinger_lower"]:
        score += 2
        result.reasons.append(f"Fiyat alt Bollinger bandinda")

    if not pd.isna(row.get("ema_200")) and current_price > row["ema_200"]:
        score += 1
        result.reasons.append("EMA200 trendinin uzerinde (yukselene trend)")

    if not pd.isna(row.get("macd")) and not pd.isna(row.get("macd_signal")):
        if row["macd"] > row["macd_signal"] and row["macd_histogram"] > 0:
            score += 1
            result.reasons.append("MACD bullish crossover")

    # --- SHORT SIGNALS ---
    if row["rsi"] > config.RSI_OVERBOUGHT:
        score -= 2
        result.reasons.append(f"RSI asiri alim ({row['rsi']:.1f} > {config.RSI_OVERBOUGHT})")

    if current_price >= row["bollinger_upper"]:
        score -= 2
        result.reasons.append("Fiyat ust Bollinger bandinda")

    if not pd.isna(row.get("macd")) and not pd.isna(row.get("macd_signal")):
        if row["macd"] < row["macd_signal"] and row["macd_histogram"] < 0:
            score -= 1
            result.reasons.append("MACD bearish crossover")

    atr_val = row.get("atr", 0)
    if atr_val and atr_val > 0:
        result.stop_loss = current_price - (atr_val * 1.5)
        result.take_profit = current_price + (atr_val * 2.5)
    else:
        result.stop_loss = current_price * (1 - config.STOP_LOSS_PCT / 100)
        result.take_profit = current_price * (1 + config.PROFIT_TARGET_PCT / 100)

    result.entry_price = current_price
    result.strength = score
    result.action = "HOLD"
    if score >= 3:
        result.action = "BUY"
    elif score <= -3:
        result.action = "SELL"

    return result
