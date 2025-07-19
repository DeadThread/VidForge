import os
import logging
from logging.handlers import TimedRotatingFileHandler
from constants import LOG_DIR
from datetime import datetime, timedelta

os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("vidforge")
appflow = logging.getLogger("vidforge.app")

def setup_loggers():
    # Only add handlers if no handlers present yet
    if not logger.hasHandlers():
        logger.setLevel(logging.DEBUG)
        # Console
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(ch)

        # File debug
        fh = TimedRotatingFileHandler(
            os.path.join(LOG_DIR, "vidforge.log"),
            when="midnight", interval=1, backupCount=30,
            encoding="utf-8"
        )
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)

    if not appflow.hasHandlers():
        appflow.setLevel(logging.INFO)
        afh = TimedRotatingFileHandler(
            os.path.join(LOG_DIR, "appflow.log"),
            when="midnight", interval=1, backupCount=30,
            encoding="utf-8"
        )
        afh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        afh.setLevel(logging.INFO)
        appflow.addHandler(afh)

    # Cleanup old logs
    cut = datetime.now() - timedelta(days=30)
    for f in os.listdir(LOG_DIR):
        p = os.path.join(LOG_DIR, f)
        if os.path.isfile(p) and os.path.getmtime(p) < cut.timestamp():
            try:
                os.remove(p)
                logger.debug(f"Deleted old log file {f}")
            except Exception as e:
                logger.error(f"Cannot delete log {f}: {e}")

setup_loggers()
