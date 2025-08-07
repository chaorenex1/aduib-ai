import logging
import sys

from ...configs import config

def init_logging():
    log_handlers: list[logging.Handler] = []
    sh = logging.StreamHandler(sys.stdout)
    log_handlers.append(sh)
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format=config.LOG_FORMAT,
        handlers=log_handlers
    )
    logging.root.setLevel(config.LOG_LEVEL)
    logging.root.addHandler(sh)
    log_tz = config.LOG_TZ
    if log_tz:
        from datetime import datetime

        import pytz

        timezone = pytz.timezone(log_tz)

        def time_converter(seconds):
            return datetime.fromtimestamp(seconds, tz=timezone).timetuple()

        for handler in logging.root.handlers:
            if handler.formatter:
                handler.formatter.converter = time_converter
    logging.info("Logging initialized")
