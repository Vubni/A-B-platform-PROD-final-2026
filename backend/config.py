from logging.handlers import RotatingFileHandler
import logging
from dotenv import load_dotenv
import os

load_dotenv()

DATE_BASE_CONNECT = {"host": os.getenv("DB_HOST", "0.0.0.0"),
                     "user": os.getenv("DB_USER", "user"),
                     "password": os.getenv("DB_PASSWORD"),
                     "database": os.getenv("DB_NAME", "prod")}




logger = logging.getLogger()
logger.setLevel(logging.INFO)


formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

all_logs_handler = RotatingFileHandler(
    'logs/all_logs.log',
    maxBytes=10*1024*1024,
    backupCount=3,
    encoding='utf-8'
)
all_logs_handler.setFormatter(formatter)

error_handler = RotatingFileHandler(
    'logs/errors.log',
    maxBytes=10*1024*1024,
    backupCount=3,
    encoding='utf-8'
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logger.addHandler(all_logs_handler)
logger.addHandler(error_handler)
logger.addHandler(console_handler)
