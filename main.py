import sys
import os
import signal
import logging
from threading import Thread

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from trading_engine import TradingEngine
from app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Main")

config = Config()
try:
    config.validate()
    logger.info("Config basariyla yuklendi ve dogrulandi")
except ValueError as e:
    logger.critical(f"Config hatasi: {e}")
    sys.exit(1)

engine = TradingEngine(config)

if not engine.initialize():
    logger.critical("Trading motoru baslatilamadi. Gidiyorum.")
    sys.exit(1)

app = create_app(engine)


def start_trading():
    engine.run()


def signal_handler(sig, frame):
    logger.info(f"Sinyal alindi ({sig}), bot kapatiliyor...")
    engine.stop()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

trading_thread = Thread(target=start_trading, daemon=True, name="TradingEngine")
trading_thread.start()
logger.info("Trading thread'i baslatildi")

if __name__ == "__main__":
    try:
        host = config.FLASK_HOST
        port = config.FLASK_PORT
        debug = config.FLASK_DEBUG
        logger.info(f"Flask dashboard baslatiliyor: http://{host}:{port}")
        app.run(host=host, port=port, debug=debug, use_reloader=False)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
