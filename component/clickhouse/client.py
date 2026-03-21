import logging
from typing import Optional

import clickhouse_connect
from clickhouse_connect.driver import Client

logger = logging.getLogger(__name__)

_client: Optional[Client] = None

# DDL for conversation_message:
# ReplacingMergeTree(updated_at) deduplicates by message_id (String PK),
# keeping the row with the latest updated_at — supports state updates.
_CREATE_CONVERSATION_MESSAGE = """
CREATE TABLE IF NOT EXISTS conversation_message (
    message_id       String,
    agent_id         Int32,
    agent_session_id Int32,
    model_name       String,
    provider_name    String,
    role             String,
    content          String,
    state            String,
    user_id          String,
    created_at       DateTime,
    updated_at       DateTime
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY message_id
PARTITION BY toYYYYMM(created_at)
"""

# DDL for message_token_usage:
# Keyed by message_id (1-to-1 with conversation_message).
_CREATE_MESSAGE_TOKEN_USAGE = """
CREATE TABLE IF NOT EXISTS message_token_usage (
    message_id        String,
    agent_id          Int32,
    agent_session_id  Int32,
    model_name        String,
    provider_name     String,
    prompt_tokens         Int32,
    cached_prompt_tokens  Int32,
    completion_tokens     Int32,
    thinking_tokens       Int32,
    total_tokens          Int32,
    total_price           Decimal(10, 7),
    cache_price           Decimal(10, 7),
    thinking_price        Decimal(10, 7),
    created_at            DateTime,
    updated_at            DateTime
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY message_id
"""


def get_ch_client() -> Client:
    if _client is None:
        raise RuntimeError("ClickHouse client is not initialized. Call init_clickhouse first.")
    return _client


def init_clickhouse(app) -> None:
    """
    Initialize the ClickHouse client and ensure required tables exist.
    Called from app_factory during startup. Failures are logged but do not
    prevent the application from starting.
    """
    global _client
    from configs import config

    if not config.CLICKHOUSE_ENABLED:
        logger.info("ClickHouse integration is disabled (CLICKHOUSE_ENABLED=false)")
        return

    try:
        _client = clickhouse_connect.get_client(
            host=config.CLICKHOUSE_HOST,
            port=config.CLICKHOUSE_PORT,
            username=config.CLICKHOUSE_USER,
            password=config.CLICKHOUSE_PASSWORD,
            database=config.CLICKHOUSE_DATABASE,
        )
        _client.command(_CREATE_CONVERSATION_MESSAGE)
        _client.command(_CREATE_MESSAGE_TOKEN_USAGE)
        logger.info(
            "ClickHouse initialized: %s:%s/%s",
            config.CLICKHOUSE_HOST,
            config.CLICKHOUSE_PORT,
            config.CLICKHOUSE_DATABASE,
        )
    except Exception:
        logger.exception("Failed to initialize ClickHouse — analytics sync will be skipped")
        _client = None
