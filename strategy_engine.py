import logging
from typing import Optional

import pandas as pd
import numpy as np

from indicators import calculate_macd, calculate_wave_trend

logger = logging.getLogger("Strategy")


class Signal:
    def __init__(self):
        self.action = "HOLD"
        self.reason = ""
        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.exit_signal = False
        self.exit_reason = ""
        self.metrics = {}

    def __repr__(self):
        return f"Signal({self.action}, sl={self.stop_loss:.1f}, tp={self.take_profit:.1f})"


class CMSlingShotStrategy:
    """CM Sling Shot + StochRSI(3,3,8,10) + MACD + WaveTrend"""

    def __init__(self, config):
        self.config = config
        self._last_macd_hist = 0.0
        self._prev_stoch_k = 0.0
        self._in_position = False
        self._entry_price = 0.0
        self._highest_since_entry = 0.0
        self._lowest_since_entry = float("inf")

    def reset_position_state(self):
        self._in_position = False
        self._entry_price = 0.0
        self._highest_since_entry = 0.0
        self._lowest_since_entry = float("inf")

    def set_position_state(self, in_position: bool, entry_price: float = 0.0):
        self._in_position = in_position
        self._entry_price = entry_price
        self._highest_since_entry = entry_price
        self._lowest_since_entry = entry_price

    def analyze(self, df: pd.DataFrame, current_position: bool = False) -> Signal:
        signal = Signal()
        if df is None or len(df) < 62:
            signal.action = "HOLD"
            signal.reason = "Yetersiz veri"
            return signal

        last = df.iloc[-1]
        prev = df.iloc[-2]
        current_price = last["close"]

        if pd.isna(last.get("cm_trend")):
            signal.action = "HOLD"
            signal.reason = "Indikator hesaplaniyor"
            return signal

        # ---- Extract indicator values ----
        cm_trend = last["cm_trend"]
        stoch_k = last.get("stoch_rsi_k")
        stoch_d = last.get("stoch_rsi_d")
        macd_line = last.get("macd")
        macd_signal = last.get("macd_signal")
        macd_hist = last.get("macd_histogram")
        prev_macd = prev.get("macd")
        prev_macd_signal = prev.get("macd_signal")
        wt1 = last.get("wt1")
        wt2 = last.get("wt2")
        prev_wt1 = prev.get("wt1")
        prev_wt2 = prev.get("wt2")
        atr_val = last.get("atr")
        sling_upper = last.get("sling_upper")
        sling_lower = last.get("sling_lower")

        signal.metrics = {
            "cm_trend": cm_trend,
            "stoch_k": stoch_k,
            "stoch_d": stoch_d,
            "macd": macd_line,
            "macd_signal": macd_signal,
            "macd_hist": macd_hist,
            "wt1": wt1,
            "wt2": wt2,
        }

        # ---- Risk-Managed Stop Loss / Take Profit ----
        if atr_val and atr_val > 0 and not pd.isna(atr_val):
            signal.stop_loss = current_price - (atr_val * self.config.STOP_LOSS_ATR_MULT)
            signal.take_profit = current_price + (atr_val * self.config.TAKE_PROFIT_ATR_MULT)
        else:
            signal.stop_loss = current_price * 0.98
            signal.take_profit = current_price * 1.04
        signal.entry_price = current_price

        # ---- ENTRY LOGIC ----
        if not current_position:
            long_conditions = []
            short_conditions = []

            # --- LONG ---
            if cm_trend == "UP":
                long_conditions.append("CM Sling Shot YESIL trend")
            if not pd.isna(stoch_k) and stoch_k <= self.config.STOCH_RSI_OVERSOLD:
                long_conditions.append(f"StochRSI reset ({stoch_k:.1f})")
            if (
                not pd.isna(macd_line)
                and not pd.isna(macd_signal)
                and not pd.isna(prev_macd)
                and not pd.isna(prev_macd_signal)
            ):
                macd_cross_up = prev_macd <= prev_macd_signal and macd_line > macd_signal
                macd_below_zero = macd_line < 0
                if macd_cross_up and macd_below_zero:
                    long_conditions.append(f"MACD bullish cross (altinda: {macd_line:.1f})")

            if len(long_conditions) >= 2:
                signal.action = "BUY"
                signal.reason = " | ".join(long_conditions)
                if sling_lower is not None and not pd.isna(sling_lower):
                    signal.stop_loss = sling_lower - (atr_val * 0.5) if atr_val else sling_lower * 0.98
                return signal

            # --- SHORT ---
            if cm_trend == "DOWN":
                short_conditions.append("CM Sling Shot KIRMIZI trend")
            if not pd.isna(stoch_k) and stoch_k >= self.config.STOCH_RSI_OVERBOUGHT:
                short_conditions.append(f"StochRSI tepe ({stoch_k:.1f})")
            if (
                not pd.isna(macd_line)
                and not pd.isna(macd_signal)
                and not pd.isna(prev_macd)
                and not pd.isna(prev_macd_signal)
            ):
                macd_cross_dn = prev_macd >= prev_macd_signal and macd_line < macd_signal
                macd_above_zero = macd_line > 0
                if macd_cross_dn and macd_above_zero:
                    short_conditions.append(f"MACD bearish cross (ustunde: {macd_line:.1f})")

            if len(short_conditions) >= 2:
                signal.action = "SELL"
                signal.reason = " | ".join(short_conditions)
                if sling_upper is not None and not pd.isna(sling_upper):
                    signal.stop_loss = sling_upper + (atr_val * 0.5) if atr_val else sling_upper * 1.02
                return signal

        # ---- EXIT LOGIC (when in position) ----
        if current_position:
            entry_price = self._entry_price
            self._highest_since_entry = max(self._highest_since_entry, current_price)
            self._lowest_since_entry = min(self._lowest_since_entry, current_price)

            # Take Profit via ATR target
            if current_price >= signal.take_profit:
                signal.exit_signal = True
                signal.exit_reason = "ATR kar hedefine ulasildi"
                signal.action = "SELL"
                return signal

            # Stop Loss via ATR
            if current_price <= signal.stop_loss:
                signal.exit_signal = True
                signal.exit_reason = "ATR stop-loss tetiklendi"
                signal.action = "SELL"
                return signal

            # WaveTrend cross exit
            if (
                not pd.isna(prev_wt1)
                and not pd.isna(prev_wt2)
                and not pd.isna(wt1)
                and not pd.isna(wt2)
            ):
                wt_bearish_cross = prev_wt1 >= prev_wt2 and wt1 < wt2
                wt_bullish_cross = prev_wt1 <= prev_wt2 and wt1 > wt2

                if current_price > entry_price and wt_bearish_cross:
                    signal.exit_signal = True
                    signal.exit_reason = "WaveTrend bearish cross (kar al)"
                    signal.action = "SELL"
                    return signal

                if current_price < entry_price and wt_bullish_cross:
                    signal.exit_signal = True
                    signal.exit_reason = "WaveTrend bullish cross (zarar kes)"
                    signal.action = "SELL"
                    return signal

            # Trailing stop
            if self.config.TRAILING_STOP_ACTIVATE and current_price > entry_price:
                trail_distance = atr_val * 1.5 if atr_val else entry_price * 0.015
                trail_stop = self._highest_since_entry - trail_distance
                if current_price <= trail_stop:
                    signal.exit_signal = True
                    signal.exit_reason = "Trailing stop tetiklendi"
                    signal.action = "SELL"
                    return signal

            # CM trend reversal exit
            if cm_trend == "DOWN" and current_price < entry_price:
                signal.exit_signal = True
                signal.exit_reason = "CM trend tersine dondu (KIRMIZI)"
                signal.action = "SELL"
                return signal

        return signal
