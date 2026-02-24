import json
import logging
import os
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

load_dotenv()

LOG_DIR = "logs"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 3

os.makedirs(LOG_DIR, exist_ok=True)

DATE_BASE_CONNECT = {
    "host": os.getenv("DB_HOST", "postgres"),
    "user": os.getenv("DB_USER", "user"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME", "prod"),
}

SECRET = os.getenv("RANDOM_SECRET", "AJd27GqoS#gvxp@V")

AUTH_TOKEN_EXPIRATION = 24 * 3600

MAX_ACTIVE_EXPERIMENTS_PER_SUBJECT = int(os.getenv("MAX_ACTIVE_EXPERIMENTS_PER_SUBJECT", 2))
EXPERIMENT_COOLDOWN_SECONDS = int(os.getenv("EXPERIMENT_COOLDOWN_SECONDS", 7 * 24 * 3600))

EVENTS_DEPENDENCY_MAX_DELAY_DAYS = int(os.getenv("EVENTS_DEPENDENCY_MAX_DELAY_DAYS", 7))
LEARNINGS_REQUIRED_ON_COMPLETE = (
    os.getenv("LEARNINGS_REQUIRED_ON_COMPLETE", "true").lower() == "true"
)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "").strip()
KAFKA_EVENTS_TOPIC = os.getenv("KAFKA_EVENTS_TOPIC", "lotty-events")
EVENTS_USE_KAFKA = os.getenv("EVENTS_USE_KAFKA", "false").lower() == "true"

FALLBACK_APPROVAL_PERCENT = float(os.getenv("FALLBACK_APPROVAL_PERCENT", "0.6"))


def _utc_iso_timestamp(record: logging.LogRecord) -> str:
    from time import gmtime

    t = gmtime(record.created)
    ms = int((record.created % 1) * 1000)
    return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}T{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}.{ms:03d}Z"


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": _utc_iso_timestamp(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, ensure_ascii=False)


logger = logging.getLogger("backend")
logger.setLevel(logging.INFO)
logger.propagate = False

_formatter = StructuredJsonFormatter()


def _file_handler(path: str, level: int = logging.NOTSET) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    handler.setLevel(level)
    handler.setFormatter(_formatter)
    return handler


logger.addHandler(_file_handler(f"{LOG_DIR}/all_logs.log"))
logger.addHandler(_file_handler(f"{LOG_DIR}/errors.log", level=logging.ERROR))

_console = logging.StreamHandler()
_console.setFormatter(_formatter)
logger.addHandler(_console)
