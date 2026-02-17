from logging.handlers import RotatingFileHandler
import logging
from dotenv import load_dotenv
import os

load_dotenv()

LOG_DIR = "logs"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 3

os.makedirs(LOG_DIR, exist_ok=True)

DATE_BASE_CONNECT = {"host": os.getenv("DB_HOST", "0.0.0.0"),
                     "user": os.getenv("DB_USER", "user"),
                     "password": os.getenv("DB_PASSWORD"),
                     "database": os.getenv("DB_NAME", "prod")}

SECRET = os.getenv("RANDOM_SECRET", "AJd27GqoS#gvxp@V")

AUTH_TOKEN_EXPIRATION = 24 * 3600

MAX_ACTIVE_EXPERIMENTS_PER_SUBJECT = int(os.getenv("MAX_ACTIVE_EXPERIMENTS_PER_SUBJECT", 2))
EXPERIMENT_COOLDOWN_SECONDS = int(os.getenv("EXPERIMENT_COOLDOWN_SECONDS", 7 * 24 * 3600))



LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"

logger = logging.getLogger("backend")
logger.setLevel(logging.INFO)
logger.propagate = False

_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT)


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
