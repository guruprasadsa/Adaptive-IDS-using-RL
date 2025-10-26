"""
Dead Letter Queue (DLQ) Module
Captures and logs failed alert deliveries to Kafka DLQ topic with retry metadata.
"""
import json
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

from confluent_kafka import Producer, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic

logger = logging.getLogger(__name__)


class DLQProducer:
    """
    Dead Letter Queue producer for failed alert deliveries.
    Writes failed messages to alerts.dlq topic with error context.
    """
    
    def __init__(
        self,
        kafka_brokers: str,
        dlq_topic: str = "alerts.dlq",
        enable_idempotence: bool = True
    ):
        """
        Initialize DLQ producer.
        
        Args:
            kafka_brokers: Kafka bootstrap servers
            dlq_topic: DLQ topic name
            enable_idempotence: Enable idempotent producer
        """
        self.kafka_brokers = kafka_brokers
        self.dlq_topic = dlq_topic
        
        # Configure producer for reliability
        producer_config = {
            'bootstrap.servers': kafka_brokers,
            'enable.idempotence': enable_idempotence,
            'acks': 'all',
            'retries': 3,
            'max.in.flight.requests.per.connection': 5,
            'compression.type': 'snappy',
            'linger.ms': 10,
            'batch.size': 16384,
        }
        
        self.producer = Producer(producer_config)
        self._ensure_topic_exists()
        
        logger.info(f"DLQ Producer initialized: topic={dlq_topic}, brokers={kafka_brokers}")
    
    def _ensure_topic_exists(self):
        """Create DLQ topic if it doesn't exist."""
        try:
            admin_client = AdminClient({'bootstrap.servers': self.kafka_brokers})
            
            # Check if topic exists
            metadata = admin_client.list_topics(timeout=5)
            if self.dlq_topic in metadata.topics:
                logger.info(f"DLQ topic '{self.dlq_topic}' already exists")
                return
            
            # Create topic
            new_topic = NewTopic(
                self.dlq_topic,
                num_partitions=3,
                replication_factor=1,
                config={
                    'retention.ms': str(7 * 24 * 60 * 60 * 1000),  # 7 days
                    'cleanup.policy': 'delete',
                    'compression.type': 'snappy',
                }
            )
            
            futures = admin_client.create_topics([new_topic])
            for topic, future in futures.items():
                try:
                    future.result()  # Block for result
                    logger.info(f"DLQ topic '{topic}' created successfully")
                except Exception as e:
                    logger.warning(f"Failed to create DLQ topic '{topic}': {e}")
        
        except Exception as e:
            logger.error(f"Error ensuring DLQ topic exists: {e}")
    
    def write(
        self,
        original_message: Dict[str, Any],
        error: Exception,
        destination: str,
        retry_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Write failed delivery to DLQ.
        
        Args:
            original_message: Original alert/prediction message
            error: Exception that caused the failure
            destination: Target destination that failed (e.g., 'syslog', 'email')
            retry_count: Number of retry attempts
            metadata: Additional metadata
        
        Returns:
            True if successfully written to DLQ, False otherwise
        """
        try:
            dlq_message = {
                'timestamp': datetime.utcnow().isoformat(),
                'destination': destination,
                'error': {
                    'type': type(error).__name__,
                    'message': str(error),
                    'traceback': None  # Could include full traceback if needed
                },
                'retry_count': retry_count,
                'original_message': original_message,
                'metadata': metadata or {}
            }
            
            # Serialize to JSON
            dlq_payload = json.dumps(dlq_message).encode('utf-8')
            
            # Produce to DLQ topic
            self.producer.produce(
                self.dlq_topic,
                value=dlq_payload,
                key=original_message.get('alert_id', '').encode('utf-8'),
                callback=self._delivery_callback
            )
            
            # Flush to ensure delivery
            self.producer.flush(timeout=5.0)
            
            logger.warning(
                f"Wrote failed delivery to DLQ: destination={destination}, "
                f"alert_id={original_message.get('alert_id')}, retry_count={retry_count}"
            )
            return True
        
        except Exception as e:
            logger.error(f"Failed to write to DLQ: {e}")
            # Last resort: log to file
            self._log_to_file(original_message, error, destination, retry_count)
            return False
    
    def _delivery_callback(self, err, msg):
        """Kafka delivery callback."""
        if err:
            logger.error(f"DLQ message delivery failed: {err}")
        else:
            logger.debug(
                f"DLQ message delivered: topic={msg.topic()}, "
                f"partition={msg.partition()}, offset={msg.offset()}"
            )
    
    def _log_to_file(
        self,
        original_message: Dict[str, Any],
        error: Exception,
        destination: str,
        retry_count: int
    ):
        """Fallback: log to file if DLQ write fails."""
        try:
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'destination': destination,
                'error': str(error),
                'retry_count': retry_count,
                'alert_id': original_message.get('alert_id'),
                'flow_id': original_message.get('flow_id'),
            }
            
            # Log as structured JSON
            logger.error(f"DLQ_FALLBACK: {json.dumps(log_entry)}")
        except Exception as e:
            logger.critical(f"Failed to log DLQ fallback: {e}")
    
    def close(self):
        """Close producer and flush pending messages."""
        try:
            remaining = self.producer.flush(timeout=10.0)
            if remaining > 0:
                logger.warning(f"DLQ producer closed with {remaining} pending messages")
            else:
                logger.info("DLQ producer closed successfully")
        except Exception as e:
            logger.error(f"Error closing DLQ producer: {e}")


class RetryPolicy:
    """
    Retry policy with exponential backoff.
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay_ms: int = 1000,
        max_delay_ms: int = 60000,
        backoff_multiplier: float = 2.0
    ):
        """
        Initialize retry policy.
        
        Args:
            max_attempts: Maximum number of retry attempts
            initial_delay_ms: Initial delay in milliseconds
            max_delay_ms: Maximum delay in milliseconds
            backoff_multiplier: Exponential backoff multiplier
        """
        self.max_attempts = max_attempts
        self.initial_delay_ms = initial_delay_ms
        self.max_delay_ms = max_delay_ms
        self.backoff_multiplier = backoff_multiplier
    
    def should_retry(self, attempt: int) -> bool:
        """Check if should retry based on attempt count."""
        return attempt < self.max_attempts
    
    def get_delay_ms(self, attempt: int) -> int:
        """
        Calculate delay for given attempt using exponential backoff.
        
        Args:
            attempt: Current attempt number (0-indexed)
        
        Returns:
            Delay in milliseconds
        """
        delay = self.initial_delay_ms * (self.backoff_multiplier ** attempt)
        return min(int(delay), self.max_delay_ms)
    
    def wait(self, attempt: int):
        """Sleep for calculated delay."""
        delay_ms = self.get_delay_ms(attempt)
        logger.debug(f"Retry attempt {attempt + 1}, waiting {delay_ms}ms")
        time.sleep(delay_ms / 1000.0)


def with_retry(
    func,
    retry_policy: RetryPolicy,
    dlq_producer: Optional[DLQProducer] = None,
    destination: str = "unknown",
    message: Optional[Dict[str, Any]] = None
):
    """
    Execute function with retry policy and DLQ fallback.
    
    Args:
        func: Function to execute
        retry_policy: Retry policy
        dlq_producer: DLQ producer for failed attempts
        destination: Destination name for DLQ
        message: Original message for DLQ
    
    Returns:
        Function result if successful, None otherwise
    """
    last_error = None
    
    for attempt in range(retry_policy.max_attempts):
        try:
            return func()
        except Exception as e:
            last_error = e
            logger.warning(
                f"Attempt {attempt + 1}/{retry_policy.max_attempts} failed for {destination}: {e}"
            )
            
            if retry_policy.should_retry(attempt + 1):
                retry_policy.wait(attempt)
            else:
                break
    
    # All retries exhausted, write to DLQ
    if dlq_producer and message:
        dlq_producer.write(
            original_message=message,
            error=last_error,
            destination=destination,
            retry_count=retry_policy.max_attempts
        )
    
    logger.error(f"All retry attempts exhausted for {destination}: {last_error}")
    return None
