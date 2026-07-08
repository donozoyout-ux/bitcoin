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
        self.RSI_OVERSOLD = int(os.getenv("RSI_OVERSOLD", "35"))
        self.RSI_OVERBOUGHT = int(os.getenv("RSI_OVERBOUGHT", "70"))
        self.PROFIT_TARGET_PCT = float(os.getenv("PROFIT_TARGET_PCT", "1.5"))
        self.STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "1.0"))
        self.MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "5.0"))
        self.MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "3"))
        self.COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "30"))

        self.FLASK_PORT = int(os.getenv("FLASK_PORT", "10000"))
        self.FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
        self.FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    def _require(self, key: str) -> str:
        val = os.getenv(key)
        if not val:
            raise ValueError(f"[CONFIG] EKSIK: {key} environment variable'ı .env dosyasında bulunamadi!")
        return val

    def validate(self):
        if self.TRADE_QTY <= 0:
            raise ValueError("[CONFIG] TRADE_QTY sifirdan buyuk olmali")
        if self.RSI_OVERSOLD >= self.RSI_OVERBOUGHT:
            raise ValueError("[CONFIG] RSI_OVERSOLD, RSI_OVERBOUGHT'tan kucuk olmali")
        if not self.TRADING_SYMBOL or "/" not in self.TRADING_SYMBOL:
            raise ValueError("[CONFIG] TRADING_SYMBOL gecersiz (ornek: BTC/USD)")
        return True

    def is_live(self) -> bool:
        return not self.ALPACA_PAPER and "paper-api" not in self.ALPACA_BASE_URL

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
