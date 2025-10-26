"""
Real-time Traffic Statistics Aggregator for SSE Streaming
Consumes raw packets and produces 1-second aggregated traffic statistics
"""
import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from threading import Thread, Event
from typing import Dict, Any

from confluent_kafka import Consumer, Producer, KafkaError

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TrafficStatsAggregator:
    """
    Aggregates raw packet data into 1-second statistics windows.
    Produces traffic stats to 'traffic.stats' topic for SSE streaming.
    """
    
    def __init__(
        self,
        kafka_brokers: str = None,
        input_topic: str = "raw.packets",
        output_topic: str = "traffic.stats",
        window_seconds: int = 1
    ):
        """
        Initialize traffic statistics aggregator.
        
        Args:
            kafka_brokers: Kafka broker addresses
            input_topic: Topic to consume packets from
            output_topic: Topic to produce stats to
            window_seconds: Aggregation window in seconds
        """
        self.kafka_brokers = kafka_brokers or os.getenv("KAFKA_BROKERS", "localhost:9092")
        self.input_topic = input_topic
        self.output_topic = output_topic
        self.window_seconds = window_seconds
        
        # Statistics accumulators
        self.current_window_start = int(time.time())
        self.packets_count = 0
        self.bytes_count = 0
        self.protocols = defaultdict(int)
        self.src_ips = set()
        self.dst_ips = set()
        
        # Kafka clients
        self.consumer = self._create_consumer()
        self.producer = self._create_producer()
        
        # Control
        self.running = False
        self.shutdown_event = Event()
        
        logger.info(f"TrafficStatsAggregator initialized")
        logger.info(f"  Input: {input_topic}")
        logger.info(f"  Output: {output_topic}")
        logger.info(f"  Window: {window_seconds}s")
    
    def _create_consumer(self) -> Consumer:
        """Create Kafka consumer"""
        config = {
            'bootstrap.servers': self.kafka_brokers,
            'group.id': 'traffic-stats-aggregator',
            'auto.offset.reset': 'latest',
            'enable.auto.commit': True,
            'auto.commit.interval.ms': 5000,
        }
        consumer = Consumer(config)
        consumer.subscribe([self.input_topic])
        logger.info(f"Subscribed to topic: {self.input_topic}")
        return consumer
    
    def _create_producer(self) -> Producer:
        """Create Kafka producer"""
        config = {
            'bootstrap.servers': self.kafka_brokers,
            'compression.type': 'lz4',
            'enable.idempotence': True,
            'acks': 'all',
        }
        producer = Producer(config)
        logger.info(f"Producer initialized for topic: {self.output_topic}")
        return producer
    
    def _reset_window(self):
        """Reset statistics for new time window"""
        self.current_window_start = int(time.time())
        self.packets_count = 0
        self.bytes_count = 0
        self.protocols.clear()
        self.src_ips.clear()
        self.dst_ips.clear()
    
    def _publish_stats(self):
        """Publish current window statistics"""
        if self.packets_count == 0:
            return  # Skip empty windows
        
        stats = {
            "timestamp": self.current_window_start * 1000,  # milliseconds
            "window_seconds": self.window_seconds,
            "packets": self.packets_count,
            "bytes": self.bytes_count,
            "protocols": dict(self.protocols),
            "unique_src_ips": len(self.src_ips),
            "unique_dst_ips": len(self.dst_ips),
            "packets_per_second": self.packets_count / self.window_seconds,
            "bytes_per_second": self.bytes_count / self.window_seconds,
            "mbps": (self.bytes_count * 8) / (self.window_seconds * 1024 * 1024)
        }
        
        try:
            self.producer.produce(
                self.output_topic,
                key=str(self.current_window_start).encode('utf-8'),
                value=json.dumps(stats).encode('utf-8'),
                callback=lambda err, msg: logger.error(f"Failed to produce: {err}") if err else None
            )
            self.producer.poll(0)  # Trigger callbacks
            
            logger.debug(f"Published stats: {self.packets_count} packets, {self.bytes_count} bytes, {stats['mbps']:.2f} Mbps")
        
        except Exception as e:
            logger.error(f"Error publishing stats: {e}")
    
    def _process_packet(self, packet: Dict[str, Any]):
        """Process a single packet and update statistics"""
        try:
            # Update counters
            self.packets_count += 1
            self.bytes_count += packet.get("raw_len", 0)
            
            # Track protocol
            proto = packet.get("proto", "UNKNOWN")
            self.protocols[proto] += 1
            
            # Track unique IPs
            if "src_ip" in packet:
                self.src_ips.add(packet["src_ip"])
            if "dst_ip" in packet:
                self.dst_ips.add(packet["dst_ip"])
        
        except Exception as e:
            logger.error(f"Error processing packet: {e}")
    
    def run(self):
        """Main aggregation loop"""
        self.running = True
        logger.info("Starting traffic statistics aggregator...")
        
        last_publish = time.time()
        
        try:
            while self.running:
                # Poll for messages
                msg = self.consumer.poll(timeout=0.1)
                
                if msg is None:
                    # Check if window expired
                    current_time = time.time()
                    if current_time - last_publish >= self.window_seconds:
                        self._publish_stats()
                        self._reset_window()
                        last_publish = current_time
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Kafka error: {msg.error()}")
                        continue
                
                # Parse and process packet
                try:
                    value = msg.value().decode('utf-8')
                    packet = json.loads(value)
                    self._process_packet(packet)
                except Exception as e:
                    logger.error(f"Error parsing packet: {e}")
                
                # Check if window expired
                current_time = time.time()
                if current_time - last_publish >= self.window_seconds:
                    self._publish_stats()
                    self._reset_window()
                    last_publish = current_time
        
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Fatal error in aggregator: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the aggregator"""
        logger.info("Stopping traffic statistics aggregator...")
        self.running = False
        
        # Publish final stats
        if self.packets_count > 0:
            self._publish_stats()
        
        # Cleanup
        try:
            self.producer.flush(timeout=5)
        except Exception as e:
            logger.error(f"Error flushing producer: {e}")
        
        try:
            self.consumer.close()
        except Exception as e:
            logger.error(f"Error closing consumer: {e}")
        
        logger.info("Traffic statistics aggregator stopped")


def main():
    """Run traffic stats aggregator as standalone service"""
    aggregator = TrafficStatsAggregator()
    aggregator.run()


if __name__ == "__main__":
    main()
