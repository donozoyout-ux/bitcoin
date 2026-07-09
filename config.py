import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        self.ALPACA_API_KEY = self._require("ALPACA_API_KEY")
        self.ALPACA_SECRET_KEY = self._require("ALPACA_SECRET_KEY")
        self.ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        self.ALPACA_PAPER = os.getenv("ALPACA_PAPER", "true").lower() == "true"

        self.TELEGRAM_TOKEN = self._require("TELEGRAM_TOKEN")
        self.TELEGRAM_CHAT_ID = self._require("TELEGRAM_CHAT_ID")

        self.TRADING_SYMBOL = os.getenv("TRADING_SYMBOL", "BTC/USD")
        self.TRADE_QTY = float(os.getenv("TRADE_QTY", "0.001"))
        self.MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "5.0"))
        self.MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "3"))
        self.COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "30"))

        self.FLASK_PORT = int(os.getenv("FLASK_PORT", "10000"))
        self.FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
        self.FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

        # --- CM Sling Shot System ---
        self.CM_FAST_EMA = int(os.getenv("CM_FAST_EMA", "38"))
        self.CM_SLOW_EMA = int(os.getenv("CM_SLOW_EMA", "62"))

        # --- StochRSI (3, 3, 8, 10) ---
        self.STOCH_RSI_K = int(os.getenv("STOCH_RSI_K", "3"))
        self.STOCH_RSI_D = int(os.getenv("STOCH_RSI_D", "3"))
        self.STOCH_RSI_RSI_PERIOD = int(os.getenv("STOCH_RSI_RSI_PERIOD", "8"))
        self.STOCH_RSI_STOCH_PERIOD = int(os.getenv("STOCH_RSI_STOCH_PERIOD", "10"))
        self.STOCH_RSI_OVERSOLD = float(os.getenv("STOCH_RSI_OVERSOLD", "15"))
        self.STOCH_RSI_OVERBOUGHT = float(os.getenv("STOCH_RSI_OVERBOUGHT", "85"))

        # --- WaveTrend ---
        self.WT_CHANNEL_LEN = int(os.getenv("WT_CHANNEL_LEN", "10"))
        self.WT_AVG_LEN = int(os.getenv("WT_AVG_LEN", "21"))
        self.WT_SIGNAL_LEN = int(os.getenv("WT_SIGNAL_LEN", "4"))
        self.WT_OVERSOLD = float(os.getenv("WT_OVERSOLD", "-53"))
        self.WT_OVERBOUGHT = float(os.getenv("WT_OVERBOUGHT", "53"))

        # --- MACD ---
        self.MACD_FAST = int(os.getenv("MACD_FAST", "12"))
        self.MACD_SLOW = int(os.getenv("MACD_SLOW", "26"))
        self.MACD_SIGNAL = int(os.getenv("MACD_SIGNAL", "9"))

        # --- Risk Management ---
        self.STOP_LOSS_ATR_MULT = float(os.getenv("STOP_LOSS_ATR_MULT", "1.5"))
        self.TAKE_PROFIT_ATR_MULT = float(os.getenv("TAKE_PROFIT_ATR_MULT", "3.0"))
        self.TRAILING_STOP_ACTIVATE = os.getenv("TRAILING_STOP_ACTIVATE", "false").lower() == "true"

    def _require(self, key: str) -> str:
        val = os.getenv(key)
        if not val:
            raise ValueError(f"[CONFIG] EKSIK: {key} environment variable'ı .env dosyasında bulunamadi!")
        return val

    def validate(self):
        if self.TRADE_QTY <= 0:
            raise ValueError("[CONFIG] TRADE_QTY sifirdan buyuk olmali")
        if not self.TRADING_SYMBOL or "/" not in self.TRADING_SYMBOL:
            raise ValueError("[CONFIG] TRADING_SYMBOL gecersiz (ornek: BTC/USD)")
        if self.CM_FAST_EMA >= self.CM_SLOW_EMA:
            raise ValueError("[CONFIG] CM_FAST_EMA, CM_SLOW_EMA'dan kucuk olmali")
        if self.MACD_FAST >= self.MACD_SLOW:
            raise ValueError("[CONFIG] MACD_FAST, MACD_SLOW'dan kucuk olmali")
        return True

    def is_live(self) -> bool:
        return not self.ALPACA_PAPER and "paper-api" not in self.ALPACA_BASE_URL

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
