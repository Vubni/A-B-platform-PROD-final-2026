import asyncio
import json
import uuid
from datetime import date, datetime, time

from asyncpg import Connection, PostgresConnectionError, Record, connect
from asyncpg.exceptions import CannotConnectNowError

from config import DATE_BASE_CONNECT, logger


class Database:
    MAX_RETRIES = 30
    RETRY_DELAY = 1

    def __init__(self):
        self.connection: Connection | None = None
        self.transaction = None
        self._retry_count = 0

    async def __aenter__(self):
        self.connection = None
        self.transaction = None

        while self._retry_count < self.MAX_RETRIES:
            try:
                self.connection = await connect(**DATE_BASE_CONNECT)
                self.transaction = self.connection.transaction()
                await self.transaction.start()
                self._retry_count = 0
                return self
            except (PostgresConnectionError, CannotConnectNowError) as e:
                self._retry_count += 1
                logger.error(
                    f"Попытка подключения {self._retry_count}/{self.MAX_RETRIES} failed: {e}"
                )
                await asyncio.sleep(self.RETRY_DELAY)
            except Exception as e:
                logger.error(f"Неожиданная ошибка подключения: {e}")
                break

        logger.error("Превышено максимальное количество попыток подключения")
        return None

    async def __aexit__(self, exc_type, exc_value, traceback):
        try:
            if self.transaction:
                if exc_type is None:
                    try:
                        await self.transaction.commit()
                    except Exception as e:
                        logger.error(f"Ошибка при коммите транзакции: {e}")
                        await self.transaction.rollback()
                else:
                    try:
                        await self.transaction.rollback()
                    except Exception as e:
                        logger.error(f"Ошибка при откате транзакции: {e}")
        finally:
            if self.connection:
                try:
                    await self.connection.close()
                except Exception as e:
                    logger.error(f"Ошибка при закрытии соединения: {e}")
                finally:
                    self.connection = None
                    self.transaction = None

    async def close_connection(self) -> None:
        if self.transaction:
            try:
                await self.transaction.commit()
            except Exception as e:
                logger.error(f"Ошибка при коммите при закрытии: {e}")
        if self.connection and not self.connection.is_closed():
            try:
                await self.connection.close()
            except Exception as e:
                logger.error(f"Ошибка при закрытии соединения: {e}")
            finally:
                self.connection = None
                self.transaction = None

    def serialize(self, data) -> int | str | float | list | dict | None:
        try:
            if data is None:
                return None

            if isinstance(data, bytes):
                data = data.decode("utf-8")

            if isinstance(data, str):
                s = data.strip()
                if (s.startswith("{") or s.startswith("[")) and s.endswith(("}", "]")):
                    try:
                        return self.serialize(json.loads(data))
                    except (json.JSONDecodeError, TypeError):
                        pass
                return data

            if isinstance(data, list):
                return [self.serialize(item) for item in data]

            if isinstance(data, dict):
                return {key: self.serialize(value) for key, value in data.items()}

            if isinstance(data, Record):
                return {key: self.serialize(data[key]) for key in data.keys()}

            if isinstance(data, uuid.UUID):
                return str(data)

            if isinstance(data, datetime):
                return data.isoformat() if data.tzinfo else data.strftime("%Y-%m-%dT%H:%M:%SZ")
            if isinstance(data, date) and not isinstance(data, datetime):
                return data.isoformat()
            if isinstance(data, time):
                return data.strftime("%H:%M:%S")

            return data
        except (TypeError, json.JSONDecodeError) as e:
            logger.error(f"Ошибка сериализации данных: {e}")
            return None

    async def execute_all(self, sql: str, params: tuple = ()) -> list[dict] | None:
        if not await self._check_connection():
            return None

        try:
            if sql.strip().lower().startswith("select"):
                result = await self.connection.fetch(sql, *params)
                return self.serialize(result)
            else:
                await self.connection.execute(sql, *params)
                return []
        except Exception as e:
            self._handle_exception(e, sql)
            return None

    async def execute(self, sql: str, params: tuple = ()) -> dict | None:
        if not await self._check_connection():
            return None

        try:
            if sql.strip().lower().startswith("select"):
                result = await self.connection.fetchrow(sql, *params)
                return self.serialize(result)
            else:
                await self.connection.execute(sql, *params)
                return {}
        except Exception as e:
            self._handle_exception(e, sql)
            raise

    async def fetchval(self, sql: str, params: tuple = ()) -> int | str | None:
        if not await self._check_connection():
            return None

        try:
            if "RETURNING" not in sql.upper():
                sql = f"{sql} RETURNING id"

            result = await self.connection.fetchval(sql, *params)
            if result is not None and hasattr(result, "__str__"):
                return str(result)
            return result
        except Exception as e:
            self._handle_exception(e, sql)
            raise

    async def executemany(self, sql: str, params: list[tuple] | None = None) -> bool | None:
        if not await self._check_connection():
            return None
        if params is None:
            params = []
        try:
            if sql.strip().lower().startswith("select"):
                logger.error("Используйте execute() для SELECT-запросов")
                return None
            await self.connection.executemany(sql, params)
            return True
        except Exception as e:
            self._handle_exception(e, sql)
            return None

    async def _check_connection(self) -> bool:
        if not self.connection or self.connection.is_closed():
            logger.error("Соединение с БД не установлено")
            return False
        return True

    def _handle_exception(self, exception: Exception, sql: str) -> None:
        error_msg = f"{exception.__class__.__name__}: {exception}\nSQL: {sql}"
        if isinstance(exception, PostgresConnectionError):
            logger.error(f"Ошибка подключения к БД: {error_msg}")
        else:
            logger.error(f"Ошибка выполнения запроса: {error_msg}")
