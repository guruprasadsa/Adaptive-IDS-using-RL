"""
Packet Capture Producer for Kafka
Windows-compatible packet capture using pyshark/tshark with Npcap.
Produces minimal packet metadata to raw.packets topic for development.

Production deployments should use Zeek or Suricata for robust packet processing.
"""

import os
import sys
import signal
import json
import logging
from datetime import datetime
from typing import Dict, Optional
from threading import Event
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass  # dotenv not required, will use system env vars

try:
    import pyshark
except ImportError:
    print("ERROR: pyshark not installed. Install with: pip install pyshark")
    sys.exit(1)

try:
    from confluent_kafka import Producer, KafkaError
except ImportError:
    print("ERROR: confluent-kafka not installed. Install with: pip install confluent-kafka")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global shutdown event
shutdown_event = Event()


class PacketCaptureProducer:
    """
    Captures live packets and produces minimal metadata to Kafka.
    Windows-compatible using pyshark with Npcap backend.
    """
    
    def __init__(
        self,
        kafka_brokers: str,
        topic: str,
        interface: str = None,
        bpf_filter: str = None
    ):
        """
        Initialize packet capture producer.
        
        Args:
            kafka_brokers: Comma-separated Kafka broker addresses
            topic: Kafka topic to produce to (default: raw.packets)
            interface: Network interface to capture on (None = auto-detect)
            bpf_filter: BPF filter for packet capture (e.g., "tcp port 80")
        """
        self.kafka_brokers = kafka_brokers
        self.topic = topic
        self.interface = interface
        self.bpf_filter = bpf_filter
        
        # Statistics
        self.packets_captured = 0
        self.packets_produced = 0
        self.packets_failed = 0
        
        # Initialize Kafka producer
        self.producer = self._create_producer()
        
        logger.info(f"PacketCaptureProducer initialized")
        logger.info(f"Kafka Brokers: {kafka_brokers}")
        logger.info(f"Topic: {topic}")
        logger.info(f"Interface: {interface or 'auto-detect'}")
        logger.info(f"BPF Filter: {bpf_filter or 'none'}")
    
    def _create_producer(self) -> Producer:
        """Create Kafka producer with optimal settings."""
        config = {
            'bootstrap.servers': self.kafka_brokers,
            'compression.type': 'lz4',
            'enable.idempotence': True,
            'acks': 'all',
            'max.in.flight.requests.per.connection': 5,
            'retries': 10,
            'retry.backoff.ms': 100,
            'client.id': 'pcap-producer',
        }
        
        producer = Producer(config)
        logger.info("Kafka producer created successfully")
        return producer
    
    def _delivery_callback(self, err, msg):
        """Callback for message delivery reports."""
        if err is not None:
            self.packets_failed += 1
            logger.error(f"Message delivery failed: {err}")
        else:
            self.packets_produced += 1
            if self.packets_produced % 1000 == 0:
                logger.info(
                    f"Produced {self.packets_produced} packets "
                    f"(captured: {self.packets_captured}, failed: {self.packets_failed})"
                )
    
    def _extract_packet_metadata(self, packet) -> Optional[Dict]:
        """
        Extract minimal metadata from captured packet.
        
        Args:
            packet: pyshark packet object
            
        Returns:
            Dictionary with packet metadata or None if extraction fails
        """
        try:
            metadata = {}
            
            # Extract timestamp - handle both float and ISO string formats
            try:
                metadata['ts'] = float(packet.sniff_timestamp)
            except (ValueError, AttributeError):
                # Try parsing ISO format timestamp
                try:
                    from datetime import datetime
                    ts_str = str(packet.sniff_timestamp)
                    # Remove 'Z' and parse
                    ts_str = ts_str.rstrip('Z')
                    dt = datetime.fromisoformat(ts_str)
                    metadata['ts'] = dt.timestamp()
                except:
                    # Fallback to current time
                    from time import time
                    metadata['ts'] = time()
            
            metadata['raw_len'] = int(packet.length)
            
            # Extract IP layer info
            if hasattr(packet, 'ip'):
                metadata['src_ip'] = packet.ip.src
                metadata['dst_ip'] = packet.ip.dst
                metadata['proto'] = packet.transport_layer or 'UNKNOWN'
            elif hasattr(packet, 'ipv6'):
                metadata['src_ip'] = packet.ipv6.src
                metadata['dst_ip'] = packet.ipv6.dst
                metadata['proto'] = packet.transport_layer or 'UNKNOWN'
            else:
                # Non-IP packet (ARP, etc.) - skip
                return None
            
            # Extract transport layer ports
            if hasattr(packet, 'tcp'):
                metadata['src_port'] = int(packet.tcp.srcport)
                metadata['dst_port'] = int(packet.tcp.dstport)
            elif hasattr(packet, 'udp'):
                metadata['src_port'] = int(packet.udp.srcport)
                metadata['dst_port'] = int(packet.udp.dstport)
            else:
                # ICMP, etc. - use 0 for ports
                metadata['src_port'] = 0
                metadata['dst_port'] = 0
            
            return metadata
            
        except AttributeError as e:
            logger.debug(f"Failed to extract metadata from packet: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error extracting packet metadata: {e}")
            return None
    
    def _produce_packet(self, metadata: Dict):
        """
        Produce packet metadata to Kafka.
        
        Args:
            metadata: Packet metadata dictionary
        """
        try:
            # Create message key from 5-tuple for partitioning
            key = f"{metadata['src_ip']}:{metadata['src_port']}:" \
                  f"{metadata['dst_ip']}:{metadata['dst_port']}:{metadata['proto']}"
            
            # Serialize to JSON
            value = json.dumps(metadata)
            
            # Produce to Kafka
            self.producer.produce(
                topic=self.topic,
                key=key.encode('utf-8'),
                value=value.encode('utf-8'),
                callback=self._delivery_callback
            )
            
            # Poll for delivery reports (non-blocking)
            self.producer.poll(0)
            
        except BufferError:
            logger.warning("Producer queue full, waiting...")
            self.producer.flush()
            self._produce_packet(metadata)  # Retry
        except Exception as e:
            logger.error(f"Failed to produce packet: {e}")
            self.packets_failed += 1
    
    def start_capture(self):
        """Start live packet capture and production to Kafka."""
        logger.info("Starting packet capture...")
        
        try:
            # Create capture object
            capture_kwargs = {
                'interface': self.interface,
                'use_json': True,
                'include_raw': False,
            }
            
            if self.bpf_filter:
                capture_kwargs['bpf_filter'] = self.bpf_filter
            
            # Start live capture
            capture = pyshark.LiveCapture(**capture_kwargs)
            
            logger.info("Packet capture started successfully")
            logger.info("Press Ctrl+C to stop...")
            
            # Process packets
            for packet in capture.sniff_continuously():
                # Check for shutdown signal
                if shutdown_event.is_set():
                    logger.info("Shutdown signal received, stopping capture...")
                    break
                
                self.packets_captured += 1
                
                # Extract metadata
                metadata = self._extract_packet_metadata(packet)
                if metadata is None:
                    continue
                
                # Produce to Kafka
                self._produce_packet(metadata)
                
                # Log progress every 1000 packets
                if self.packets_captured % 1000 == 0:
                    logger.info(f"Captured {self.packets_captured} packets")
        
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Capture failed: {e}", exc_info=True)
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Gracefully shutdown producer."""
        logger.info("Shutting down producer...")
        
        # Flush pending messages
        remaining = self.producer.flush(timeout=10)
        if remaining > 0:
            logger.warning(f"Failed to flush {remaining} messages")
        
        # Log final statistics
        logger.info("=" * 60)
        logger.info("Final Statistics:")
        logger.info(f"  Packets Captured: {self.packets_captured}")
        logger.info(f"  Packets Produced: {self.packets_produced}")
        logger.info(f"  Packets Failed:   {self.packets_failed}")
        logger.info("=" * 60)
        
        logger.info("Shutdown complete")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}")
    shutdown_event.set()


def main():
    """Main entry point."""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Load configuration from environment
    kafka_brokers = os.getenv('KAFKA_BROKERS', 'localhost:9092')
    topic = os.getenv('PACKETS_TOPIC', 'raw.packets')
    interface = os.getenv('PCAP_IFACE', None)  # None = auto-detect
    bpf_filter = os.getenv('PCAP_FILTER', None)  # None = capture all
    
    # Clean up filter - ignore if it's empty or a comment
    if bpf_filter:
        bpf_filter = bpf_filter.strip()
        if not bpf_filter or bpf_filter.startswith('#'):
            bpf_filter = None
    
    # Validate configuration
    if not kafka_brokers:
        logger.error("KAFKA_BROKERS environment variable not set")
        sys.exit(1)
    
    # Create and start producer
    try:
        producer = PacketCaptureProducer(
            kafka_brokers=kafka_brokers,
            topic=topic,
            interface=interface,
            bpf_filter=bpf_filter
        )
        
        producer.start_capture()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
