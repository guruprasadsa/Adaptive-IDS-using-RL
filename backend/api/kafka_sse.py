"""
Kafka consumer utilities for Server-Sent Events (SSE) streaming.
Provides real-time event streaming from Kafka topics to web clients.
"""
import json
import logging
import os
import queue
import threading
import time
from typing import Any, Dict, Generator, Optional

from confluent_kafka import Consumer, KafkaError, KafkaException

logger = logging.getLogger(__name__)


class KafkaSSEConsumer:
    """
    Kafka consumer for SSE streaming.
    Consumes messages from a Kafka topic and provides them as Server-Sent Events.
    """
    
    def __init__(
        self,
        topic: str,
        group_id: str = "sse-consumer",
        kafka_brokers: Optional[str] = None,
        auto_offset_reset: str = "latest",
        max_queue_size: int = 100
    ):
        """
        Initialize Kafka SSE consumer.
        
        Args:
            topic: Kafka topic to consume from
            group_id: Consumer group ID
            kafka_brokers: Kafka broker addresses (defaults to env var)
            auto_offset_reset: Where to start consuming (latest/earliest)
            max_queue_size: Maximum size of internal message queue
        """
        self.topic = topic
        self.group_id = group_id
        self.kafka_brokers = kafka_brokers or os.getenv("KAFKA_BROKERS", "localhost:9092")
        self.auto_offset_reset = auto_offset_reset
        self.max_queue_size = max_queue_size
        
        # Internal message queue for thread-safe communication
        self.message_queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        
        # Consumer instance (created per stream)
        self.consumer: Optional[Consumer] = None
        
        # Control flags
        self.running = False
        self.consumer_thread: Optional[threading.Thread] = None
        
        logger.info(f"Initialized KafkaSSEConsumer for topic '{topic}' with brokers '{self.kafka_brokers}'")
    
    def _create_consumer(self) -> Consumer:
        """Create and configure Kafka consumer"""
        config = {
            'bootstrap.servers': self.kafka_brokers,
            'group.id': self.group_id,
            'auto.offset.reset': self.auto_offset_reset,
            'enable.auto.commit': True,
            'auto.commit.interval.ms': 5000,
            'session.timeout.ms': 30000,
            'max.poll.interval.ms': 300000,
        }
        
        consumer = Consumer(config)
        consumer.subscribe([self.topic])
        logger.info(f"Created Kafka consumer for topic '{self.topic}'")
        return consumer
    
    def _consume_loop(self):
        """Background thread that consumes Kafka messages"""
        try:
            self.consumer = self._create_consumer()
            
            while self.running:
                try:
                    # Poll for messages with timeout
                    msg = self.consumer.poll(timeout=1.0)
                    
                    if msg is None:
                        continue
                    
                    if msg.error():
                        if msg.error().code() == KafkaError._PARTITION_EOF:
                            logger.debug(f"Reached end of partition {msg.partition()}")
                        else:
                            logger.error(f"Kafka error: {msg.error()}")
                        continue
                    
                    # Parse message
                    try:
                        value = msg.value().decode('utf-8')
                        data = json.loads(value)
                        
                        # Add to queue (non-blocking with timeout)
                        try:
                            self.message_queue.put(data, block=True, timeout=0.5)
                        except queue.Full:
                            logger.warning("Message queue full, dropping oldest message")
                            try:
                                self.message_queue.get_nowait()
                                self.message_queue.put(data, block=False)
                            except queue.Empty:
                                pass
                    
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to decode message: {e}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                
                except Exception as e:
                    logger.error(f"Error in consume loop: {e}")
                    if self.running:
                        time.sleep(1)  # Brief pause before retry
        
        finally:
            if self.consumer:
                try:
                    self.consumer.close()
                except Exception as e:
                    logger.error(f"Error closing consumer: {e}")
                self.consumer = None
            logger.info("Consumer loop terminated")
    
    def start(self):
        """Start consuming messages in background thread"""
        if self.running:
            logger.warning("Consumer already running")
            return
        
        self.running = True
        self.consumer_thread = threading.Thread(target=self._consume_loop, daemon=True)
        self.consumer_thread.start()
        logger.info("Started Kafka consumer thread")
    
    def stop(self):
        """Stop consuming messages"""
        if not self.running:
            return
        
        logger.info("Stopping Kafka consumer...")
        self.running = False
        
        if self.consumer_thread:
            self.consumer_thread.join(timeout=5)
            self.consumer_thread = None
        
        logger.info("Kafka consumer stopped")
    
    def stream_events(self, heartbeat_interval: int = 30) -> Generator[str, None, None]:
        """
        Generate SSE-formatted events from Kafka messages.
        
        Args:
            heartbeat_interval: Seconds between heartbeat messages
        
        Yields:
            SSE-formatted event strings
        """
        # Start consumer if not already running
        if not self.running:
            self.start()
        
        last_heartbeat = time.time()
        
        try:
            while True:
                current_time = time.time()
                
                # Send heartbeat to keep connection alive
                if current_time - last_heartbeat >= heartbeat_interval:
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': int(current_time * 1000)})}\n\n"
                    last_heartbeat = current_time
                
                # Check for messages with timeout
                try:
                    message = self.message_queue.get(timeout=1.0)
                    
                    # Format as SSE event
                    event_type = self._determine_event_type(message)
                    event_data = json.dumps(message)
                    
                    yield f"event: {event_type}\ndata: {event_data}\n\n"
                    
                except queue.Empty:
                    continue
                
        except GeneratorExit:
            logger.info("SSE client disconnected")
        except Exception as e:
            logger.error(f"Error in stream_events: {e}")
        finally:
            # Note: We don't stop the consumer here as it may be shared
            # The consumer will be stopped when the app shuts down
            pass
    
    def _determine_event_type(self, message: Dict[str, Any]) -> str:
        """
        Determine SSE event type from message content.
        
        Args:
            message: Kafka message data
        
        Returns:
            Event type string
        """
        # Check for specific message types
        if "alert_id" in message:
            return "alert"
        elif "prediction" in message or "class_name" in message:
            return "prediction"
        elif "flow_id" in message and "features" in message:
            return "flow"
        else:
            return "message"


def create_sse_stream(
    topic: str,
    group_id: str = "sse-consumer",
    auto_offset_reset: str = "latest",
    heartbeat_interval: int = 30
) -> Generator[str, None, None]:
    """
    Convenience function to create an SSE stream from a Kafka topic.
    
    Args:
        topic: Kafka topic to stream from
        group_id: Consumer group ID
        auto_offset_reset: Where to start consuming (latest/earliest)
        heartbeat_interval: Seconds between heartbeat messages
    
    Yields:
        SSE-formatted event strings
    
    Example:
        ```python
        @app.route('/events')
        def events():
            return Response(
                create_sse_stream('alerts'),
                mimetype='text/event-stream'
            )
        ```
    """
    consumer = KafkaSSEConsumer(
        topic=topic,
        group_id=group_id,
        auto_offset_reset=auto_offset_reset
    )
    
    try:
        for event in consumer.stream_events(heartbeat_interval=heartbeat_interval):
            yield event
    finally:
        consumer.stop()


# Singleton consumer instances to avoid creating multiple consumers per topic
_consumer_instances: Dict[str, KafkaSSEConsumer] = {}
_consumer_lock = threading.Lock()


def get_shared_consumer(
    topic: str,
    group_id: str = "sse-consumer",
    auto_offset_reset: str = "latest"
) -> KafkaSSEConsumer:
    """
    Get or create a shared consumer instance for a topic.
    Multiple SSE streams can share the same consumer.
    
    Args:
        topic: Kafka topic
        group_id: Consumer group ID
        auto_offset_reset: Offset reset strategy
    
    Returns:
        Shared KafkaSSEConsumer instance
    """
    key = f"{topic}:{group_id}"
    
    with _consumer_lock:
        if key not in _consumer_instances:
            consumer = KafkaSSEConsumer(
                topic=topic,
                group_id=group_id,
                auto_offset_reset=auto_offset_reset
            )
            _consumer_instances[key] = consumer
            logger.info(f"Created shared consumer for {key}")
        
        return _consumer_instances[key]


def cleanup_consumers():
    """
    Stop and cleanup all shared consumer instances.
    Should be called on application shutdown.
    """
    with _consumer_lock:
        for key, consumer in _consumer_instances.items():
            logger.info(f"Cleaning up consumer {key}")
            consumer.stop()
        _consumer_instances.clear()
