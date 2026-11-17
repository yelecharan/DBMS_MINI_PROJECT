import logging
import time

from app.core.config import settings
from app.database.session import SessionLocal
from app.services.outbox_service import process_pending_outbox

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gatesentry.outbox.worker")


def main() -> None:
    logger.info("Starting incident-vector outbox worker.")
    while True:
        try:
            completed = process_pending_outbox(SessionLocal)
            if completed:
                logger.info("Outbox worker reached %s terminal event(s).", completed)
        except Exception:
            logger.exception("Outbox worker poll failed; it will retry after the poll interval.")
        time.sleep(settings.OUTBOX_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
