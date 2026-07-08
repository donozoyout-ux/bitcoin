import logging
from typing import Optional

import pandas as pd

from indicators import calculate_macd, calculate_wave_trend

logger = logging.getLogger("Strategy")


class Condition:
    def __init__(self, name: str, passed: bool, current: str, required: str):
        self.name = name
        self.passed = passed
        self.current = current
        self.required = required

    def to_dict(self):
        return {"name": self.name, "passed": self.passed, "current": self.current, "required": self.required}


class Analysis:
    def __init__(self):
        self.market_regime = "Bekleniyor"
        self.summary = ""
        self.long_conditions: list[Condition] = []
        self.short_conditions: list[Condition] = []
        self.long_readiness = 0
        self.short_readiness = 0
        self.support_resistance: list[str] = []
        self.notes: list[str] = []

    def to_dict(self):
        return {
            "market_regime": self.market_regime,
            "summary": self.summary,
            "long_conditions": [c.to_dict() for c in self.long_conditions],
            "short_conditions": [c.to_dict() for c in self.short_conditions],
            "long_readiness": self.long_readiness,
            "short_readiness": self.short_readiness,
            "notes": self.notes,
        }


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
        self.analysis = Analysis()

    def __repr__(self):
        return f"Signal({self.action})"


class CMSlingShotStrategy:
    """CM Sling Shot + StochRSI(3,3,8,10) + MACD + WaveTrend"""

    def __init__(self, config):
        self.config = config
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
        analysis = Analysis()

        if df is None or len(df) < 62:
            signal.action = "HOLD"
            signal.reason = "Yetersiz veri"
            analysis.summary = f"En az 62 mum gerekli (su an {len(df)})"
            signal.analysis = analysis
            return signal

        last = df.iloc[-1]
        prev = df.iloc[-2]
        current_price = last["close"]

        if pd.isna(last.get("cm_trend")):
            signal.action = "HOLD"
            signal.reason = "Indikator hesaplaniyor"
            analysis.summary = "CM Sling Shot indikatoru henuz hazir degil"
            signal.analysis = analysis
            return signal

        cm_trend = last["cm_trend"]
        stoch_k = last.get("stoch_rsi_k")
        stoch_d = last.get("stoch_rsi_d")
        macd_line = last.get("macd")
        macd_signal_line = last.get("macd_signal")
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
        rsi = last.get("rsi")

        signal.metrics = {
            "cm_trend": cm_trend,
            "stoch_k": stoch_k,
            "stoch_d": stoch_d,
            "macd": macd_line,
            "macd_signal": macd_signal_line,
            "macd_hist": macd_hist,
            "wt1": wt1,
            "wt2": wt2,
            "atr": atr_val,
        }

        # Market regime
        if cm_trend == "UP":
            regime_emoji = "yesil"
            if rsi is not None and not pd.isna(rsi) and rsi > 60:
                analysis.market_regime = f"YUKSELIS TREND ({regime_emoji}) - RSI {rsi:.1f}"
            else:
                analysis.market_regime = f"YUKSELIS TREND ({regime_emoji})"
        elif cm_trend == "DOWN":
            regime_emoji = "kirmizi"
            if rsi is not None and not pd.isna(rsi) and rsi < 40:
                analysis.market_regime = f"DUSUS TRENDI ({regime_emoji}) - RSI {rsi:.1f}"
            else:
                analysis.market_regime = f"DUSUS TRENDI ({regime_emoji})"
        else:
            analysis.market_regime = "YATAY PIYASA (nÖtr)"

        # ---- LONG Conditions ----
        l1 = Condition(
            name="CM Sling Shot Trend = YESIL",
            passed=cm_trend == "UP",
            current=f"Trend: {self._trend_label_tr(cm_trend)} ({cm_trend})",
            required="YESIL (UP)",
        )
        stoch_ok_l = not pd.isna(stoch_k) and stoch_k <= self.config.STOCH_RSI_OVERSOLD
        l2 = Condition(
            name=f"StochRSI %K <= {self.config.STOCH_RSI_OVERSOLD} (reset)",
            passed=bool(stoch_ok_l),
            current=f"%K = {stoch_k:.1f}" if not pd.isna(stoch_k) else "Hesaplaniyor",
            required=f"%K <= {self.config.STOCH_RSI_OVERSOLD}",
        )
        macd_cross_up = False
        macd_below_zero = False
        if all(not pd.isna(x) for x in [macd_line, macd_signal_line, prev_macd, prev_macd_signal]):
            macd_cross_up = prev_macd <= prev_macd_signal and macd_line > macd_signal_line
            macd_below_zero = macd_line < 0
        l3 = Condition(
            name="MACD < 0 + bullish cross",
            passed=bool(macd_cross_up and macd_below_zero),
            current=f"MACD = {macd_line:.1f} | Sinyal = {macd_signal_line:.1f}{' (Kesisim var)' if macd_cross_up else ''}",
            required="MACD < 0 ve yukari kesisim",
        )
        analysis.long_conditions = [l1, l2, l3]

        long_met = sum(1 for c in [l1, l2, l3] if c.passed)
        analysis.long_readiness = int((long_met / 3) * 100)

        # ---- SHORT Conditions ----
        s1 = Condition(
            name="CM Sling Shot Trend = KIRMIZI",
            passed=cm_trend == "DOWN",
            current=f"Trend: {self._trend_label_tr(cm_trend)} ({cm_trend})",
            required="KIRMIZI (DOWN)",
        )
        stoch_ok_s = not pd.isna(stoch_k) and stoch_k >= self.config.STOCH_RSI_OVERBOUGHT
        s2 = Condition(
            name=f"StochRSI %K >= {self.config.STOCH_RSI_OVERBOUGHT} (tepe)",
            passed=bool(stoch_ok_s),
            current=f"%K = {stoch_k:.1f}" if not pd.isna(stoch_k) else "Hesaplaniyor",
            required=f"%K >= {self.config.STOCH_RSI_OVERBOUGHT}",
        )
        macd_cross_dn = False
        macd_above_zero = False
        if all(not pd.isna(x) for x in [macd_line, macd_signal_line, prev_macd, prev_macd_signal]):
            macd_cross_dn = prev_macd >= prev_macd_signal and macd_line < macd_signal_line
            macd_above_zero = macd_line > 0
        s3 = Condition(
            name="MACD > 0 + bearish cross",
            passed=bool(macd_cross_dn and macd_above_zero),
            current=f"MACD = {macd_line:.1f} | Sinyal = {macd_signal_line:.1f}{' (Kesisim var)' if macd_cross_dn else ''}",
            required="MACD > 0 ve asagi kesisim",
        )
        analysis.short_conditions = [s1, s2, s3]

        short_met = sum(1 for c in [s1, s2, s3] if c.passed)
        analysis.short_readiness = int((short_met / 3) * 100)

        # Summary
        if not current_position:
            if long_met >= 2:
                analysis.summary = "LONG kosullari karsilaniyor! Alim dusunulebilir."
            elif short_met >= 2:
                analysis.summary = "SHORT kosullari karsilaniyor! Satis dusunulebilir."
            else:
                analysis.summary = (
                    f"Sinyal yok (BEKLE). LONG: {long_met}/3 | SHORT: {short_met}/3 kosul saglaniyor."
                )

        # Notes
        if not pd.isna(wt1) and not pd.isna(self.config.WT_OVERSOLD) and wt1 < self.config.WT_OVERSOLD:
            analysis.notes.append(f"WaveTrend asiri satim bolgesinde ({wt1:.1f} < {self.config.WT_OVERSOLD})")
        if not pd.isna(wt1) and not pd.isna(self.config.WT_OVERBOUGHT) and wt1 > self.config.WT_OVERBOUGHT:
            analysis.notes.append(f"WaveTrend asiri alim bolgesinde ({wt1:.1f} > {self.config.WT_OVERBOUGHT})")
        if not pd.isna(rsi) and rsi < 30:
            analysis.notes.append(f"RSI asiri satim: {rsi:.1f}")
        if not pd.isna(rsi) and rsi > 70:
            analysis.notes.append(f"RSI asiri alim: {rsi:.1f}")
        if atr_val is not None and not pd.isna(atr_val):
            atr_pct = (atr_val / current_price) * 100
            analysis.notes.append(f"Volatilite (ATR): ${atr_val:.1f} (%{atr_pct:.2f})")

        signal.analysis = analysis

        # ---- ENTRY LOGIC ----
        if not current_position:
            if long_met >= 2:
                signal.action = "BUY"
                signal.reason = " | ".join(c.name for c in [l1, l2, l3] if c.passed)
                if sling_lower is not None and not pd.isna(sling_lower) and atr_val is not None and not pd.isna(atr_val):
                    signal.stop_loss = sling_lower - (atr_val * 0.5)
                elif atr_val is not None and not pd.isna(atr_val):
                    signal.stop_loss = current_price - (atr_val * self.config.STOP_LOSS_ATR_MULT)
                    signal.take_profit = current_price + (atr_val * self.config.TAKE_PROFIT_ATR_MULT)
                signal.entry_price = current_price
                return signal

            if short_met >= 2:
                signal.action = "SELL"
                signal.reason = " | ".join(c.name for c in [s1, s2, s3] if c.passed)
                if sling_upper is not None and not pd.isna(sling_upper) and atr_val is not None and not pd.isna(atr_val):
                    signal.stop_loss = sling_upper + (atr_val * 0.5)
                elif atr_val is not None and not pd.isna(atr_val):
                    signal.stop_loss = current_price + (atr_val * self.config.STOP_LOSS_ATR_MULT)
                    signal.take_profit = current_price - (atr_val * self.config.TAKE_PROFIT_ATR_MULT)
                signal.entry_price = current_price
                return signal

        # ---- EXIT LOGIC ----
        if current_position:
            entry_price = self._entry_price
            self._highest_since_entry = max(self._highest_since_entry, current_price)
            self._lowest_since_entry = min(self._lowest_since_entry, current_price)

            if atr_val is not None and not pd.isna(atr_val):
                sl = current_price - (atr_val * self.config.STOP_LOSS_ATR_MULT) if current_price > entry_price else entry_price * 0.99
                tp = current_price + (atr_val * self.config.TAKE_PROFIT_ATR_MULT)
                signal.stop_loss = sl
                signal.take_profit = tp

            if current_price >= signal.take_profit > 0:
                signal.exit_signal = True
                signal.exit_reason = "ATR kar hedefine ulasildi"
                signal.action = "SELL"
                analysis.summary = f"KAR AL: ${current_price:,.2f} (hedef: ${signal.take_profit:,.2f})"
                return signal

            if current_price <= signal.stop_loss > 0:
                signal.exit_signal = True
                signal.exit_reason = "ATR stop-loss tetiklendi"
                signal.action = "SELL"
                analysis.summary = f"STOP LOSS: ${current_price:,.2f} (stop: ${signal.stop_loss:,.2f})"
                return signal

            if all(not pd.isna(x) for x in [prev_wt1, prev_wt2, wt1, wt2]):
                wt_bearish = prev_wt1 >= prev_wt2 and wt1 < wt2
                wt_bullish = prev_wt1 <= prev_wt2 and wt1 > wt2
                if current_price > entry_price and wt_bearish:
                    signal.exit_signal = True
                    signal.exit_reason = "WaveTrend bearish cross"
                    signal.action = "SELL"
                    analysis.summary = f"WT bearish cross: Kar al ({current_price:.2f})"
                    return signal
                if current_price < entry_price and wt_bullish:
                    signal.exit_signal = True
                    signal.exit_reason = "WaveTrend bullish cross"
                    signal.action = "SELL"
                    analysis.summary = f"WT bullish cross: Zarar kes ({current_price:.2f})"
                    return signal

            if self.config.TRAILING_STOP_ACTIVATE and current_price > entry_price:
                atr_d = atr_val if not pd.isna(atr_val) else entry_price * 0.015
                trail = self._highest_since_entry - (atr_d * 1.5)
                if current_price <= trail:
                    signal.exit_signal = True
                    signal.exit_reason = "Trailing stop"
                    signal.action = "SELL"
                    analysis.summary = f"Trailing stop: ${current_price:,.2f}"
                    return signal

            if cm_trend == "DOWN" and current_price < entry_price:
                signal.exit_signal = True
                signal.exit_reason = "CM trend tersine dondu"
                signal.action = "SELL"
                analysis.summary = "Trend reverse: CM KIRMIZI'ya dondu"
                return signal

            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            analysis.summary = f"Pozisyonda (%{pnl_pct:+.2f}) | Stop: ${signal.stop_loss:.1f} | Hedef: ${signal.take_profit:.1f}"

        if analysis.summary == "":
            analysis.summary = f"Beklemede. LONG: %{analysis.long_readiness} | SHORT: %{analysis.short_readiness} hazir"

        signal.analysis = analysis
        return signal

    def _trend_label_tr(self, trend: str) -> str:
        return {"UP": "Yesil", "DOWN": "Kirmizi", "NEUTRAL": "Nötr"}.get(trend, trend)
