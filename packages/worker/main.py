import time
import logging

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("worker")


def main() -> None:
    logger.info("Worker started.")

    while True:
        logger.info("Worker heartbeat...")
        time.sleep(30)


if __name__ == "__main__":
    main()