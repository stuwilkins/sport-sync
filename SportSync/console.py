import logging
import sys
from .sync import withings_sync


def sync():
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    withings_sync()
