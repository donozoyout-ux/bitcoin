import pandas as pd
import numpy as np


# ============================================================
#  RSI
# ============================================================
def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
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


# ============================================================
#  Bollinger Bands
# ============================================================
def calculate_bollinger(df: pd.DataFrame, period: int = 20, std_mult: float = 2.0) -> dict:
    sma = df["close"].rolling(window=period).mean()
    std = df["close"].rolling(window=period).std()
    return {"sma": sma, "upper": sma + (std_mult * std), "lower": sma - (std_mult * std)}


# ============================================================
#  EMA
# ============================================================
def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


# ============================================================
#  MACD
# ============================================================
def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


# ============================================================
#  ATR
# ============================================================
def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=period, min_periods=period).mean()
    return atr


# ============================================================
#  CM Sling Shot System
#  Original Pine Script by ChrisMoody
#  emaFast = ta.ema(close, 38)
#  emaSlow = ta.ema(close, 62)
#  Trend UP (green):  emaFast > emaSlow
#  Trend DOWN (red):  emaFast < emaSlow
# ============================================================
def calculate_cm_sling_shot(df: pd.DataFrame, fast_period: int = 38, slow_period: int = 62) -> dict:
    ema_fast = calculate_ema(df["close"], fast_period)
    ema_slow = calculate_ema(df["close"], slow_period)

    trend = pd.Series("NEUTRAL", index=df.index)
    trend[ema_fast > ema_slow] = "UP"
    trend[ema_fast < ema_slow] = "DOWN"

    pullback_up = (ema_fast > ema_slow) & (df["close"] < ema_fast)
    pullback_dn = (ema_fast < ema_slow) & (df["close"] > ema_fast)

    cons_up = (ema_fast > ema_slow) & (df["close"].shift(1) < ema_fast) & (df["close"] > ema_fast)
    cons_dn = (ema_fast < ema_slow) & (df["close"].shift(1) > ema_fast) & (df["close"] < ema_fast)

    return {
        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
        "trend": trend,
        "pullback_up": pullback_up,
        "pullback_dn": pullback_dn,
        "cons_up": cons_up,
        "cons_dn": cons_dn,
    }


# ============================================================
#  Stochastic RSI (3, 3, 8, 10)
#  1. RSI(8)
#  2. StochRSI = (RSI - min(RSI,10)) / (max(RSI,10) - min(RSI,10)) * 100
#  3. %K = SMA(StochRSI, 3)
#  4. %D = SMA(%K, 3)
# ============================================================
def calculate_stoch_rsi(
    df: pd.DataFrame,
    k_period: int = 3,
    d_period: int = 3,
    rsi_period: int = 8,
    stoch_period: int = 10,
) -> dict:
    rsi = calculate_rsi(df["close"], period=rsi_period)
    rsi_min = rsi.rolling(window=stoch_period, min_periods=stoch_period).min()
    rsi_max = rsi.rolling(window=stoch_period, min_periods=stoch_period).max()
    range_rsi = rsi_max - rsi_min
    stoch_rsi = pd.Series(np.nan, index=df.index)
    valid = range_rsi > 0
    stoch_rsi[valid] = (rsi[valid] - rsi_min[valid]) / range_rsi[valid] * 100
    k = stoch_rsi.rolling(window=k_period, min_periods=k_period).mean()
    d = k.rolling(window=d_period, min_periods=d_period).mean()
    return {"stoch_rsi": stoch_rsi, "k": k, "d": d}


# ============================================================
#  WaveTrend (VT) Crosses — LazyBear WaveTrend
#  src = hlc3
#  esa = ema(src, n1)
#  d   = ema(abs(src - esa), n1)
#  ci  = (src - esa) / (0.015 * d)
#  wt1 = ema(ci, n2)
#  wt2 = sma(wt1, 4)
# ============================================================
def calculate_wave_trend(
    df: pd.DataFrame,
    channel_len: int = 10,
    avg_len: int = 21,
    signal_len: int = 4,
    k: float = 0.5,
) -> dict:
    src = (df["high"] + df["low"] + df["close"]) / 3
    esa = calculate_ema(src, channel_len)
    d_series = (src - esa).abs().ewm(span=channel_len, adjust=False).mean()
    ci = (src - esa) / (0.015 * d_series.replace(0, np.nan))
    wt1 = calculate_ema(ci, avg_len)
    wt2 = wt1.rolling(window=signal_len, min_periods=signal_len).mean()
    overbought = wt1 > 53
    oversold = wt1 < -53
    return {
        "wt1": wt1,
        "wt2": wt2,
        "ci": ci,
        "overbought": overbought,
        "oversold": oversold,
    }


# ============================================================
#  SuperTrend-like Sling Shot Trend Cloud
# ============================================================
def calculate_sling_bands(df: pd.DataFrame, fast_period: int = 38, slow_period: int = 62) -> dict:
    ema_fast = calculate_ema(df["close"], fast_period)
    ema_slow = calculate_ema(df["close"], slow_period)
    upper_band = pd.DataFrame({"a": ema_fast, "b": ema_slow}).max(axis=1)
    lower_band = pd.DataFrame({"a": ema_fast, "b": ema_slow}).min(axis=1)
    return {"upper": upper_band, "lower": lower_band, "mid": (upper_band + lower_band) / 2}


# ============================================================
#  Master function: Calculate ALL indicators
# ============================================================
def add_all_indicators(df: pd.DataFrame, config) -> pd.DataFrame:
    df = df.copy()
    # RSI
    df["rsi"] = calculate_rsi(df["close"], period=14)
    # Bollinger
    bb = calculate_bollinger(df)
    df["bollinger_sma"] = bb["sma"]
    df["bollinger_upper"] = bb["upper"]
    df["bollinger_lower"] = bb["lower"]
    # EMAs
    df["ema_50"] = calculate_ema(df["close"], 50)
    df["ema_200"] = calculate_ema(df["close"], 200)
    # MACD
    macd = calculate_macd(df, config.MACD_FAST, config.MACD_SLOW, config.MACD_SIGNAL)
    df["macd"] = macd["macd"]
    df["macd_signal"] = macd["signal"]
    df["macd_histogram"] = macd["histogram"]
    # ATR
    df["atr"] = calculate_atr(df)
    # CM Sling Shot
    cm = calculate_cm_sling_shot(df, config.CM_FAST_EMA, config.CM_SLOW_EMA)
    df["cm_ema_fast"] = cm["ema_fast"]
    df["cm_ema_slow"] = cm["ema_slow"]
    df["cm_trend"] = cm["trend"]
    df["cm_pullback_up"] = cm["pullback_up"]
    df["cm_pullback_dn"] = cm["pullback_dn"]
    df["cm_cons_up"] = cm["cons_up"]
    df["cm_cons_dn"] = cm["cons_dn"]
    # Sling Bands (for stop loss reference)
    sling = calculate_sling_bands(df, config.CM_FAST_EMA, config.CM_SLOW_EMA)
    df["sling_upper"] = sling["upper"]
    df["sling_lower"] = sling["lower"]
    # StochRSI (3,3,8,10)
    stoch = calculate_stoch_rsi(
        df,
        k_period=config.STOCH_RSI_K,
        d_period=config.STOCH_RSI_D,
        rsi_period=config.STOCH_RSI_RSI_PERIOD,
        stoch_period=config.STOCH_RSI_STOCH_PERIOD,
    )
    df["stoch_rsi_raw"] = stoch["stoch_rsi"]
    df["stoch_rsi_k"] = stoch["k"]
    df["stoch_rsi_d"] = stoch["d"]
    # WaveTrend
    wt = calculate_wave_trend(
        df,
        channel_len=config.WT_CHANNEL_LEN,
        avg_len=config.WT_AVG_LEN,
        signal_len=config.WT_SIGNAL_LEN,
    )
    df["wt1"] = wt["wt1"]
    df["wt2"] = wt["wt2"]
    df["wt_ci"] = wt["ci"]
    df["wt_overbought"] = wt["overbought"]
    df["wt_oversold"] = wt["oversold"]
    return df


# ============================================================
#  Signal Generator (Legacy — kept as fallback)
# ============================================================
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
    if row["rsi"] < config.RSI_OVERSOLD:
        score += 2
        result.reasons.append(f"RSI asiri satim ({row['rsi']:.1f} < {config.RSI_OVERSOLD})")
    if current_price <= row["bollinger_lower"]:
        score += 2
        result.reasons.append("Fiyat alt Bollinger bandinda")
    if not pd.isna(row.get("ema_200")) and current_price > row["ema_200"]:
        score += 1
        result.reasons.append("EMA200 trendinin uzerinde (yukselene trend)")
    if not pd.isna(row.get("macd")) and not pd.isna(row.get("macd_signal")):
        if row["macd"] > row["macd_signal"] and row["macd_histogram"] > 0:
            score += 1
            result.reasons.append("MACD bullish crossover")
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
