import logging
from contextvars import ContextVar

request_id_contextvar: ContextVar[str] = ContextVar("request_id", default="-")

_configured = False


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_contextvar.get()
        return True


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt=(
                "%(asctime)s %(levelname)-8s %(name)s "
                "[req=%(request_id)s] %(message)s"
            ),
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(RequestIdFilter())
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
