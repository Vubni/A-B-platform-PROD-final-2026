from __future__ import annotations

import asyncio
import json
from typing import Any

from config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_EVENTS_TOPIC,
    logger,
)
from functions.events_submit import process_events_batch

_producer = None
_consumer_tasks: list[asyncio.Task[None]] = []


def _get_bootstrap() -> str:
    if not KAFKA_BOOTSTRAP_SERVERS:
        return "localhost:9092"
    return KAFKA_BOOTSTRAP_SERVERS


async def ensure_topic() -> bool:
    try:
        from aiokafka import AIOKafkaAdminClient
        from aiokafka.admin import NewTopic

        admin = AIOKafkaAdminClient(bootstrap_servers=_get_bootstrap())
        await admin.start()
        try:
            existing = await admin.list_topics()
            if KAFKA_EVENTS_TOPIC in existing:
                return True
            await admin.create_topics(
                [NewTopic(KAFKA_EVENTS_TOPIC, num_partitions=2, replication_factor=1)],
                validate_only=False,
            )
            logger.info("Kafka: топик %s создан.", KAFKA_EVENTS_TOPIC)
            return True
        finally:
            await admin.close()
    except Exception as e:
        logger.warning("Kafka: не удалось создать топик %s: %s", KAFKA_EVENTS_TOPIC, e)
        return False


async def produce_events_batch(events: list[dict[str, Any]]) -> None:
    global _producer
    try:
        from aiokafka import AIOKafkaProducer
    except ImportError:
        logger.error("aiokafka не установлен")
        return

    if not events:
        return

    try:
        if _producer is None:
            _producer = AIOKafkaProducer(bootstrap_servers=_get_bootstrap())
            await _producer.start()
        payload = json.dumps(events, default=str).encode("utf-8")
        await _producer.send_and_wait(KAFKA_EVENTS_TOPIC, payload)
    except Exception as e:
        logger.exception("Kafka: ошибка отправки событий: %s", e)
        raise


async def stop_producer() -> None:
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None
        logger.info("Kafka producer остановлен.")


_CONCURRENT_BATCHES = 8
_GETMANY_TIMEOUT_MS = 300
_MAX_PARTITION_FETCH_BYTES = 2 * 1024 * 1024


async def _process_one_batch(events: list[Any], sem: asyncio.Semaphore) -> None:
    async with sem:
        try:
            await process_events_batch(events)
        except Exception as e:
            logger.exception("Kafka: ошибка обработки батча: %s", e)


async def _consume_loop() -> None:
    from aiokafka import AIOKafkaConsumer

    consumer = AIOKafkaConsumer(
        KAFKA_EVENTS_TOPIC,
        bootstrap_servers=_get_bootstrap(),
        group_id="lotty-events-consumer",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")) if m else None,
        auto_offset_reset="earliest",
        fetch_min_bytes=1,
        fetch_max_wait_ms=300,
        max_partition_fetch_bytes=_MAX_PARTITION_FETCH_BYTES,
    )
    await consumer.start()
    logger.info(
        "Kafka consumer запущен, топик: %s, до %s батчей параллельно",
        KAFKA_EVENTS_TOPIC,
        _CONCURRENT_BATCHES,
    )
    sem = asyncio.Semaphore(_CONCURRENT_BATCHES)
    try:
        while True:
            result = await consumer.getmany(timeout_ms=_GETMANY_TIMEOUT_MS)
            batches: list[list[Any]] = []
            for _tp, messages in result.items():
                for msg in messages:
                    if not msg.value:
                        continue
                    events = msg.value if isinstance(msg.value, list) else [msg.value]
                    if events:
                        batches.append(events)
            if batches:
                await asyncio.gather(*(_process_one_batch(b, sem) for b in batches))
    except asyncio.CancelledError:
        raise
    finally:
        await consumer.stop()
        logger.info("Kafka consumer остановлен.")


_NUM_CONSUMER_TASKS = 2


async def start_consumer() -> asyncio.Task[None] | None:
    global _consumer_tasks
    try:
        _consumer_tasks = [
            asyncio.create_task(_consume_loop()) for _ in range(_NUM_CONSUMER_TASKS)
        ]

        async def _wait_all() -> None:
            await asyncio.gather(*_consumer_tasks)

        wrapper = asyncio.create_task(_wait_all())
        logger.info("Kafka: запущено %s consumer-задач (по партициям)", _NUM_CONSUMER_TASKS)
        return wrapper
    except Exception as e:
        logger.warning("Kafka: не удалось запустить consumer: %s", e)
        return None


async def stop_consumer() -> None:
    global _consumer_tasks
    if not _consumer_tasks:
        return
    for t in _consumer_tasks:
        if not t.done():
            t.cancel()
    try:
        await asyncio.gather(*_consumer_tasks, return_exceptions=True)
    except Exception:
        pass
    _consumer_tasks = []
    logger.info("Kafka consumer tasks отменены.")
