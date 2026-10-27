"""Small optional diagnostics kept separate from every progress filename."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def diagnostic_path(profile):
    profile = Path(profile)
    return profile.with_name(profile.name + ".diagnostic.log")


def attach_log(profile):
    try:
        handler = RotatingFileHandler(
            diagnostic_path(profile), maxBytes=128 * 1024, backupCount=2, encoding="utf-8"
        )
    except OSError:
        # Diagnostics must never turn a recoverable progress problem into an
        # application failure, especially when the disk itself is full.
        return None
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger("game").addHandler(handler)
    return handler


def detach_log(handler):
    if handler is not None:
        logging.getLogger("game").removeHandler(handler)
        handler.close()
