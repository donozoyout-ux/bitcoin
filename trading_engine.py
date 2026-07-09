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
from alpaca.data.requests import CryptoBarsRequest, CryptoLatestTradeRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from indicators import add_all_indicators
from strategy_engine import CMSlingShotStrategy

logger = logging.getLogger("TradingEngine")


class DailyReport:
    def __init__(self, date_str: str, start_balance: float):
        self.date = date_str
        self.start_balance = start_balance
        self.end_balance = start_balance
        self.trades = 0
        self.wins = 0
        self.losses = 0
        self.pnl = 0.0
        self.trade_details: list[dict] = []

    def close(self, end_balance: float):
        self.end_balance = end_balance

    def add_trade(self, trade: dict):
        self.trade_details.append(trade)

    @property
    def pnl_pct(self) -> float:
        if self.start_balance <= 0:
            return 0.0
        return (self.pnl / self.start_balance) * 100

    @property
    def win_rate(self) -> float:
        total = self.wins + self.losses
        return (self.wins / max(total, 1)) * 100

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "start_balance": f"${self.start_balance:,.2f}",
            "end_balance": f"${self.end_balance:,.2f}",
            "trades": self.trades,
            "wins": self.wins,
            "losses": self.losses,
            "pnl": f"${self.pnl:+.2f}",
            "pnl_pct": f"%{self.pnl_pct:+.2f}",
            "win_rate": f"%{self.win_rate:.1f}",
            "trade_details": self.trade_details[-20:],
        }

    def telegram_message(self) -> str:
        emoji = "+" if self.pnl >= 0 else "-"
        return (
            f"GUN SONU RAPORU ({self.date})\n"
            f"{'=' * 20}\n"
            f"Baslangic: ${self.start_balance:,.2f}\n"
            f"Bitis:     ${self.end_balance:,.2f}\n"
            f"Kar/Zarar: {emoji} ${self.pnl:+.2f} (%{self.pnl_pct:+.2f})\n"
            f"Islem:     {self.trades} ({self.wins}W / {self.losses}L)\n"
            f"Win Rate:  %{self.win_rate:.1f}\n"
            f"{'=' * 20}"
        )


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

        self.strategy = CMSlingShotStrategy(config)

        self.in_position = False
        self.entry_price = 0.0
        self.position_qty = 0.0

        self.daily_start_balance = 0.0
        self.daily_trades = 0
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
        self.last_strategy_metrics = {}
        self.last_analysis = None
        self.df_last: Optional[pd.DataFrame] = None

        self.daily_pnl = 0.0
        self._current_day = ""
        self._current_report: Optional[DailyReport] = None
        self.daily_reports: list[DailyReport] = []

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
            logger.info(f"Alpaca API baglantisi basarali | Mod: {mode} | Bakiye: ${self.current_balance:,.2f}")
            self._send_telegram(f"Bot baslatildi | Mod: {mode} | Bakiye: ${self.current_balance:,.2f}")
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
            logger.info(f"Soguma modunda: {remaining} dk kaldi")
            return True
        return False

    def _check_daily_loss_limit(self) -> bool:
        if self.daily_start_balance <= 0:
            return False
        loss_pct = ((self.daily_start_balance - self.current_balance) / self.daily_start_balance) * 100
        if loss_pct >= self.config.MAX_DAILY_LOSS_PCT:
            logger.warning(f"Gunluk kayip limiti asildi! Kayip: %{loss_pct:.2f}")
            self._send_telegram(f"Gunluk kayip limiti asildi (%{loss_pct:.2f}). Bot durduruldu.")
            return True
        return False

    def _check_day_rollover(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._current_day:
            if self._current_report:
                self._current_report.close(self.current_balance)
                self.daily_reports.append(self._current_report)
                logger.info(f"Gun raporu: {self._current_report.date} | {self._current_report.pnl_pct:+.2f}%")
                self._send_telegram(self._current_report.telegram_message())
            self._current_day = today
            self.daily_start_balance = self.current_balance
            self.daily_trades = 0
            self.daily_pnl = 0.0
            self._current_report = DailyReport(today, self.current_balance)
            logger.info(f"Yeni gun basladi: {today} | Bakiye: ${self.current_balance:,.2f}")

    def get_market_data(self) -> Optional[pd.DataFrame]:
        try:
            request = CryptoBarsRequest(
                symbol_or_symbols=self.config.TRADING_SYMBOL,
                timeframe=TimeFrame(amount=15, unit=TimeFrameUnit.Minute),
                limit=250,
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

    def get_coingecko_price(self) -> Optional[float]:
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()
            return float(data["bitcoin"]["usd"])
        except Exception as e:
            logger.warning(f"CoinGecko fiyat alinamadi: {e}")
            return None

    def get_live_price(self) -> Optional[float]:
        price = self.get_coingecko_price()
        if price is not None:
            return price
        try:
            request = CryptoLatestTradeRequest(symbol_or_symbols=self.config.TRADING_SYMBOL)
            result = self.data_client.get_crypto_latest_trade(request)
            trade = result.get(self.config.TRADING_SYMBOL)
            if trade is None:
                return None
            return float(trade.price)
        except Exception as e:
            logger.warning(f"Alpaca canli fiyat alinamadi: {e}")
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
            self.strategy.set_position_state(True, price)

            record = TradeRecord("BUY", price, self.position_qty, reason)
            self.trade_log.append(record)
            self.total_trades += 1

            msg = (
                f"ALIM YAPILDI\n"
                f"Sembol: {self.config.TRADING_SYMBOL}\n"
                f"Fiyat: ${price:,.2f}\n"
                f"Miktar: {self.position_qty}\n"
                f"Stop: ${stop_loss:,.2f}\n"
                f"Hedef: ${take_profit:,.2f}\n"
                f"Sebep: {reason}"
            )
            self._send_telegram(msg)
            logger.info(f"ALIM basarili: {price}")
            return True
        except Exception as e:
            logger.error(f"ALIM emri basarisiz: {e}")
            self.last_error = f"Alim: {e}"
            self._send_telegram(f"ALIM EMRI BASARISIZ: {e}")
            return False

    def execute_sell(self, price: float, reason: str) -> bool:
        try:
            qty = self.position_qty if self.position_qty > 0 else self.config.TRADE_QTY
            order = MarketOrderRequest(
                symbol=self.config.TRADING_SYMBOL,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
            )
            submitted = self.trading_client.submit_order(order)
            pnl = (price - self.entry_price) * qty
            self.total_pnl += pnl

            if pnl > 0:
                self.wins += 1
                self.consecutive_losses = 0
            else:
                self.losses += 1
                self.consecutive_losses += 1

            self.daily_trades += 1
            self.daily_pnl += pnl
            record = TradeRecord("SELL", price, qty, reason, pnl)
            self.trade_log.append(record)
            self.total_trades += 1
            if self._current_report:
                self._current_report.trades += 1
                self._current_report.pnl += pnl
                if pnl > 0:
                    self._current_report.wins += 1
                else:
                    self._current_report.losses += 1
                self._current_report.add_trade({
                    "time": record.timestamp.strftime("%H:%M:%S"),
                    "side": "SELL",
                    "price": f"${price:,.2f}",
                    "reason": reason,
                    "pnl": f"${pnl:+.2f}",
                })

            self.in_position = False
            self.entry_price = 0.0
            self.position_qty = 0.0
            self.strategy.reset_position_state()

            emoji = "+" if pnl > 0 else "-"
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
                self._send_telegram(f"{self.consecutive_losses} ard arda zarar. {cooldown_min} dk soguma basladi.")

            return True
        except Exception as e:
            logger.error(f"SATIS emri basarisiz: {e}")
            self.last_error = f"Satis: {e}"
            self._send_telegram(f"SATIS EMRI BASARISIZ: {e}")
            return False

    def run_iteration(self):
        if self._paused:
            return
        self._check_day_rollover()
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
        self.df_last = df

        live_price = self.get_live_price()
        self.last_price = live_price if live_price is not None else last_row["close"]
        rsi_val = last_row.get("rsi")
        self.last_rsi = rsi_val if pd.notna(rsi_val) else None

        account = self.trading_client.get_account()
        self.current_balance = float(account.cash)

        signal = self.strategy.analyze(df, current_position=self.in_position)
        self.last_signal = signal.action
        self.last_strategy_metrics = signal.metrics
        self.last_analysis = signal.analysis.to_dict() if signal.analysis else None

        if not self.in_position:
            if signal.action == "BUY":
                self.execute_buy(
                    price=self.last_price,
                    reason=signal.reason,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                )
        else:
            if signal.exit_signal:
                self.execute_sell(self.last_price, signal.exit_reason)

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

    def _get_metric(self, key: str, fmt: str = ".2f") -> str:
        v = self.last_strategy_metrics.get(key)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "-"
        if isinstance(v, str):
            return v
        return f"{v:{fmt}}"

    def _daily_pnl_pct(self) -> str:
        if self.daily_start_balance <= 0:
            return "%0.00"
        pct = (self.daily_pnl / self.daily_start_balance) * 100
        return f"%{pct:+.2f}"

    def get_status(self) -> dict:
        with self._lock:
            return {
                "balance": f"${self.current_balance:,.2f}",
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
                "cm_trend": self._get_metric("cm_trend", ""),
                "stoch_k": self._get_metric("stoch_k"),
                "stoch_d": self._get_metric("stoch_d"),
                "macd": self._get_metric("macd"),
                "macd_signal": self._get_metric("macd_signal"),
                "macd_hist": self._get_metric("macd_hist"),
                "wt1": self._get_metric("wt1"),
                "wt2": self._get_metric("wt2"),
                "analysis": self.last_analysis,
                "daily_report": self._current_report.to_dict() if self._current_report else None,
                "daily_reports": [r.to_dict() for r in self.daily_reports[-7:]],
                "daily_pnl": f"${self.daily_pnl:+.2f}",
                "daily_pnl_pct": self._daily_pnl_pct(),
                "daily_trades": self.daily_trades,
                "daily_start_balance": f"${self.daily_start_balance:,.2f}",
            }

    def get_last_trade_str(self) -> str:
        if not self.trade_log:
            return "[SYS] Canli veri akisi bekleniyor..."
        last = self.trade_log[-1]
        return f"[ISLEM] {last.timestamp.strftime('%H:%M:%S')} - {last.side} Fiyat: ${last.price:,.2f} | {last.reason}"
