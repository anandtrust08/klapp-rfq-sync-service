# =============================================================================
# FILE: src/config.py
# Configuration for RFQ Sync Service
# =============================================================================

from typing import Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Sync service configuration."""

    # Service Info
    SERVICE_NAME: str = "rfq-sync-service"
    SERVICE_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=True)

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:29092"
    KAFKA_CONSUMER_GROUP: str = "rfq-sync-service"
    KAFKA_AUTO_OFFSET_RESET: str = "latest"
    KAFKA_ENABLE_AUTO_COMMIT: bool = True
    KAFKA_SESSION_TIMEOUT_MS: int = 30000
    KAFKA_MAX_POLL_RECORDS: int = 100

    # Topics
    TOPIC_RFQ_CREATED: str = "rfq.created"
    TOPIC_RFQ_UPDATED: str = "rfq.updated"
    TOPIC_RFQ_STATUS_CHANGED: str = "rfq.status.changed"
    TOPIC_RFQ_SYNC_TO_MEDUSA: str = "rfq.sync.to_medusa"
    TOPIC_RFQ_SYNC_TO_EMAIL: str = "rfq.sync.to_email_service"
    TOPIC_RFQ_SYNC_COMPLETED: str = "rfq.sync.completed"
    TOPIC_RFQ_DLQ: str = "rfq.dlq"

    # Email Service Database (source)
    EMAIL_DB_HOST: str = "postgres-ai"
    EMAIL_DB_PORT: int = 5432
    EMAIL_DB_NAME: str = "klapp_ai_procurement"
    EMAIL_DB_USER: str = "postgres"
    EMAIL_DB_PASSWORD: str = "changeme"

    @property
    def EMAIL_DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.EMAIL_DB_USER}:{self.EMAIL_DB_PASSWORD}@{self.EMAIL_DB_HOST}:{self.EMAIL_DB_PORT}/{self.EMAIL_DB_NAME}"
        )

    # Medusa Database (target)
    MEDUSA_DB_HOST: str = "postgres-medusa-backend"
    MEDUSA_DB_PORT: int = 5432
    MEDUSA_DB_NAME: str = "klapp-backend"
    MEDUSA_DB_USER: str = "postgres"
    MEDUSA_DB_PASSWORD: str = "postgres"

    @property
    def MEDUSA_DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.MEDUSA_DB_USER}:{self.MEDUSA_DB_PASSWORD}@{self.MEDUSA_DB_HOST}:{self.MEDUSA_DB_PORT}/{self.MEDUSA_DB_NAME}"
        )

    # Medusa API (alternative to direct DB)
    MEDUSA_API_URL: str = "http://medusa:9000"
    MEDUSA_API_KEY: Optional[str] = None
    MEDUSA_USE_API: bool = False  # Set to True to use API instead of direct DB

    # Redis
    REDIS_URL: str = "redis://redis:6379/5"
    REDIS_KEY_PREFIX: str = "rfq_sync:"
    REDIS_LOCK_TIMEOUT: int = 30

    # Circuit Breaker
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = 60
    CIRCUIT_BREAKER_EXPECTED_EXCEPTION: str = "Exception"

    # Retry Configuration
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_WAIT_EXPONENTIAL_MULTIPLIER: float = 1.0
    RETRY_WAIT_EXPONENTIAL_MAX: int = 60

    # Batch Processing
    BATCH_SIZE: int = 50
    BATCH_TIMEOUT_SECONDS: int = 5

    # Monitoring
    METRICS_PORT: int = 9100
    ENABLE_METRICS: bool = True

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
