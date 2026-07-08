import time
import logging
import threading
from datetime import datetime, date
from typing import Optional

import pandas as pd
import requests

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical.crypto import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from indicators import add_all_indicators, generate_signals

logger = logging.getLogger("TradingEngine")


class TradeRecord:
    def __init__(self, side: str, price: float, qty: float, reason: str, pnl: float = 0.0):
        self.timestamp = datetime.now()
        self.side = side
        self.price = price
        self.qty = qty
        self.reason = reason
        self.pnl = pnl

    def to_dict(self) -> dict:
        return {
            "time": self.timestamp.strftime("%H:%M:%S"),
            "side": self.side,
            "price": f"${self.price:,.2f}",
            "qty": self.qty,
            "reason": self.reason,
            "pnl": f"${self.pnl:+.2f}" if self.pnl != 0 else "-",
        }


class TradingEngine:
    def __init__(self, config):
        self.config = config
        self.trading_client: Optional[TradingClient] = None
        self.data_client: Optional[CryptoHistoricalDataClient] = None
        self._running = False
        self._paused = False
        self._lock = threading.Lock()

        self.in_position = False
        self.entry_price = 0.0
        self.position_qty = 0.0

        self.daily_start_balance = 0.0
        self.daily_trades = 0
        self.daily_losses = 0
        self.consecutive_losses = 0
        self.cooldown_until: Optional[datetime] = None
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0

        self.trade_log: list[TradeRecord] = []
        self.last_price: Optional[float] = None
        self.last_rsi: Optional[float] = None
        self.last_signal = "HOLD"
        self.last_error = ""
        self.current_balance = 0.0

    def initialize(self) -> bool:
        try:
            self.data_client = CryptoHistoricalDataClient(
                api_key=self.config.ALPACA_API_KEY,
                secret_key=self.config.ALPACA_SECRET_KEY,
            )
            self.trading_client = TradingClient(
                self.config.ALPACA_API_KEY,
                self.config.ALPACA_SECRET_KEY,
                paper=self.config.ALPACA_PAPER,
            )
            account = self.trading_client.get_account()
            self.current_balance = float(account.cash)
            self.daily_start_balance = self.current_balance
            self._running = True

            mode = "PAPER" if self.config.ALPACA_PAPER else "LIVE"
            logger.info(f"Alpaca API baglantisi basarili | Mod: {mode} | Bakiye: ${self.current_balance:,.2f}")
            self._send_telegram(f"🤖 BTC Botu baslatildi | Mod: {mode} | Bakiye: ${self.current_balance:,.2f}")
            return True
        except Exception as e:
            logger.error(f"Alpaca API baglantisi BASARISIZ: {e}")
            self.last_error = str(e)
            return False

    def _send_telegram(self, message: str):
        try:
            url = f"https://api.telegram.org/bot{self.config.TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": self.config.TELEGRAM_CHAT_ID, "text": message}, timeout=10)
        except Exception as e:
            logger.warning(f"Telegram mesaji gonderilemedi: {e}")

    def _check_cooldown(self) -> bool:
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            remaining = int((self.cooldown_until - datetime.now()).total_seconds() / 60)
            logger.info(f"Soğuma modunda: {remaining} dk kaldi")
            return True
        return False

    def _check_daily_loss_limit(self) -> bool:
        if self.daily_start_balance <= 0:
            return False
        loss_pct = ((self.daily_start_balance - self.current_balance) / self.daily_start_balance) * 100
        if loss_pct >= self.config.MAX_DAILY_LOSS_PCT:
            logger.warning(f"Gunluk kayip limiti asildi! Kayip: %{loss_pct:.2f}")
            self._send_telegram(f"🚨 Gunluk kayip limiti asildi (%{loss_pct:.2f}). Bot durduruldu.")
            return True
        return False

    def get_market_data(self) -> Optional[pd.DataFrame]:
        try:
            request = CryptoBarsRequest(
                symbol_or_symbols=self.config.TRADING_SYMBOL,
                timeframe=TimeFrame(amount=15, unit=TimeFrameUnit.Minute),
                limit=50,
            )
            bars = self.data_client.get_crypto_bars(request)
            if bars.df is None or bars.df.empty:
                raise ValueError("Veri gelmedi")
            df = bars.df.loc[self.config.TRADING_SYMBOL].copy()
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            return df
        except Exception as e:
            logger.error(f"Piyasa verisi cekilemedi: {e}")
            self.last_error = f"Veri: {e}"
            return None

    def execute_buy(self, price: float, reason: str, stop_loss: float, take_profit: float) -> bool:
        try:
            order = MarketOrderRequest(
                symbol=self.config.TRADING_SYMBOL,
                qty=self.config.TRADE_QTY,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC,
            )
            submitted = self.trading_client.submit_order(order)
            self.in_position = True
            self.entry_price = price
            self.position_qty = float(submitted.qty) if submitted.qty else self.config.TRADE_QTY

            record = TradeRecord("BUY", price, self.position_qty, reason)
            self.trade_log.append(record)
            self.total_trades += 1

            msg = (
                f"🚀 ALIM YAPILDI\n"
                f"Sembol: {self.config.TRADING_SYMBOL}\n"
                f"Fiyat: ${price:,.2f}\n"
                f"Miktar: {self.position_qty}\n"
                f"🛡️ Stop: ${stop_loss:,.2f}\n"
                f"🎯 Hedef: ${take_profit:,.2f}\n"
                f"Sebep: {reason}"
            )
            self._send_telegram(msg)
            logger.info(f"ALIM basarili: {price}")
            return True
        except Exception as e:
            logger.error(f"ALIM emri basarisiz: {e}")
            self.last_error = f"Alim: {e}"
            self._send_telegram(f"❌ ALIM EMRI BASARISIZ: {e}")
            return False

    def execute_sell(self, price: float, reason: str) -> bool:
        try:
            order = MarketOrderRequest(
                symbol=self.config.TRADING_SYMBOL,
                qty=self.position_qty if self.position_qty > 0 else self.config.TRADE_QTY,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
            )
            submitted = self.trading_client.submit_order(order)
            pnl = (price - self.entry_price) * (self.position_qty if self.position_qty > 0 else self.config.TRADE_QTY)
            self.total_pnl += pnl

            if pnl > 0:
                self.wins += 1
                self.consecutive_losses = 0
            else:
                self.losses += 1
                self.consecutive_losses += 1

            self.daily_trades += 1
            record = TradeRecord("SELL", price, self.position_qty, reason, pnl)
            self.trade_log.append(record)
            self.total_trades += 1

            self.in_position = False
            self.entry_price = 0.0
            self.position_qty = 0.0

            emoji = "💰" if pnl > 0 else "🚨"
            msg = (
                f"{emoji} SATIS YAPILDI\n"
                f"Fiyat: ${price:,.2f}\n"
                f"Kar/Zarar: ${pnl:+.2f}\n"
                f"Sebep: {reason}\n"
                f"Toplam P&L: ${self.total_pnl:+.2f}"
            )
            self._send_telegram(msg)
            logger.info(f"SATIS basarili: {price} | P&L: ${pnl:+.2f}")

            if self.consecutive_losses >= self.config.MAX_CONSECUTIVE_LOSSES:
                cooldown_min = self.config.COOLDOWN_MINUTES
                self.cooldown_until = datetime.now().replace(second=0) + pd.Timedelta(minutes=cooldown_min)
                self._send_telegram(f"🧊 {self.consecutive_losses} ard arda zarar. {cooldown_min} dk soguma basladi.")
                logger.warning(f"{self.consecutive_losses} ard arda zarar, {cooldown_min}dk soguma")

            return True
        except Exception as e:
            logger.error(f"SATIS emri basarisiz: {e}")
            self.last_error = f"Satis: {e}"
            self._send_telegram(f"❌ SATIS EMRI BASARISIZ: {e}")
            return False

    def run_iteration(self):
        if self._paused:
            return

        if self._check_cooldown():
            return

        if self._check_daily_loss_limit():
            self._paused = True
            return

        df = self.get_market_data()
        if df is None:
            return

        df = add_all_indicators(df, self.config)
        last_row = df.iloc[-1]

        self.last_price = last_row["close"]
        rsi_val = last_row.get("rsi")
        self.last_rsi = rsi_val if pd.notna(rsi_val) else None

        account = self.trading_client.get_account()
        self.current_balance = float(account.cash)
        equity = float(account.equity)

        signal = generate_signals(last_row, self.config)
        self.last_signal = signal.action

        if not self.in_position:
            if signal.action == "BUY":
                self.execute_buy(
                    price=signal.entry_price,
                    reason=" | ".join(signal.reasons),
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                )
        else:
            current_price = last_row["close"]
            upper_band = last_row.get("bollinger_upper", float("inf"))
            if not pd.isna(upper_band):
                upper_band = float(upper_band)
            else:
                upper_band = float("inf")

            if current_price >= signal.take_profit:
                self.execute_sell(current_price, "Kar hedefine ulasildi (Take Profit)")
            elif current_price <= signal.stop_loss:
                self.execute_sell(current_price, "Stop-loss tetiklendi")
            elif current_price >= upper_band and signal.action == "SELL":
                self.execute_sell(current_price, "Ust Bollinger bandi + satis sinyali")
            elif signal.action == "SELL":
                self.execute_sell(current_price, "Satis sinyali alindi")
            elif current_price >= self.entry_price * (1 + self.config.PROFIT_TARGET_PCT / 100):
                self.execute_sell(current_price, f"Kar hedefi %{self.config.PROFIT_TARGET_PCT}")
            elif current_price <= self.entry_price * (1 - self.config.STOP_LOSS_PCT / 100):
                self.execute_sell(current_price, f"Stop-loss %{self.config.STOP_LOSS_PCT}")

    def run(self):
        logger.info("Trading motoru 7/24 calismaya basladi (15sn aralik)")
        while self._running:
            try:
                self.run_iteration()
            except Exception as e:
                logger.error(f"Beklenmeyen hata: {e}")
                self.last_error = str(e)
            time.sleep(15)

    def stop(self):
        logger.info("Trading motoru durduruluyor...")
        self._running = False

    def get_status(self) -> dict:
        with self._lock:
            return {
                "balance": f"${self.current_balance:,.2f}",
                "equity": f"${self.current_balance:,.2f}",
                "btc_price": f"${self.last_price:,.2f}" if self.last_price is not None else "Bekleniyor...",
                "rsi": f"{self.last_rsi:.2f}" if self.last_rsi is not None else "Hesaplaniyor...",
                "status": "POZISYONDA" if self.in_position else "Sinyal Bekleniyor",
                "in_position": self.in_position,
                "entry_price": f"${self.entry_price:,.2f}" if self.in_position else "-",
                "total_trades": self.total_trades,
                "wins": self.wins,
                "losses": self.losses,
                "total_pnl": f"${self.total_pnl:+.2f}",
                "win_rate": f"{(self.wins / max(self.wins + self.losses, 1)) * 100:.1f}%",
                "consecutive_losses": self.consecutive_losses,
                "cooldown": self.cooldown_until.strftime("%H:%M") if self.cooldown_until else "-",
                "last_signal": self.last_signal,
                "last_error": self.last_error,
                "is_running": self._running,
                "is_paused": self._paused,
                "trade_log": [t.to_dict() for t in self.trade_log[-20:]],
                "last_trade": self.trade_log[-1].to_dict() if self.trade_log else {"side": "-", "price": "-", "reason": "Islem yok"},
            }

    def get_last_trade_str(self) -> str:
        if not self.trade_log:
            return "[SYS] Canli veri akisi bekleniyor..."
        last = self.trade_log[-1]
        return f"[ISLEM] {last.timestamp.strftime('%H:%M:%S')} - {last.side} Fiyat: ${last.price:,.2f} | {last.reason}"
