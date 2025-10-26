"""
PCAP File Replay Producer for Kafka
Replays PCAP files from disk and produces packet metadata to Kafka.
Designed for development/testing with historical network traffic data.
"""

import glob
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Dict, List, Optional

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass

try:
    import pyshark
except ImportError:
    print("ERROR: pyshark not installed. Install with: pip install pyshark")
    sys.exit(1)

try:
    from confluent_kafka import Producer
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


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal")
    shutdown_event.set()


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class PcapReplayProducer:
    """
    Replays PCAP files and produces packet metadata to Kafka.
    Supports looping through multiple PCAP files continuously.
    """
    
    def __init__(
        self,
        kafka_brokers: str,
        topic: str,
        pcap_dir: str,
        batch_size: int = 100,
        delay_ms: int = 10,
        loop: bool = True
    ):
        """
        Initialize PCAP replay producer.
        
        Args:
            kafka_brokers: Comma-separated Kafka broker addresses
            topic: Kafka topic to produce to
            pcap_dir: Directory containing PCAP files
            batch_size: Number of packets to buffer before flushing
            delay_ms: Delay in milliseconds between batches (for throttling)
            loop: Whether to loop through PCAP files continuously
        """
        self.kafka_brokers = kafka_brokers
        self.topic = topic
        self.pcap_dir = Path(pcap_dir)
        self.batch_size = batch_size
        self.delay_ms = delay_ms
        self.loop = loop
        
        # Statistics
        self.total_packets = 0
        self.total_produced = 0
        self.total_failed = 0
        self.files_processed = 0
        
        # Create producer
        self.producer = self._create_producer()
        
        # Find PCAP files
        self.pcap_files = self._find_pcap_files()
        
        logger.info("PcapReplayProducer initialized")
        logger.info(f"  Kafka Brokers: {kafka_brokers}")
        logger.info(f"  Topic: {topic}")
        logger.info(f"  PCAP Directory: {pcap_dir}")
        logger.info(f"  Batch Size: {batch_size}")
        logger.info(f"  Delay: {delay_ms}ms")
        logger.info(f"  Loop: {loop}")
        logger.info(f"  Found {len(self.pcap_files)} PCAP files")
    
    def _create_producer(self) -> Producer:
        """Create Kafka producer"""
        config = {
            'bootstrap.servers': self.kafka_brokers,
            'compression.type': 'lz4',
            'enable.idempotence': True,
            'acks': 'all',
            'max.in.flight.requests.per.connection': 5,
            'retries': 10,
            'retry.backoff.ms': 100,
            'client.id': 'pcap-replay-producer',
            'linger.ms': 10,
            'batch.size': 16384,
        }
        return Producer(config)
    
    def _find_pcap_files(self) -> List[Path]:
        """Find all PCAP files in directory"""
        if not self.pcap_dir.exists():
            logger.error(f"PCAP directory not found: {self.pcap_dir}")
            return []
        
        # Search for .pcap and .pcapng files recursively
        pcap_files = []
        for pattern in ['**/*.pcap', '**/*.pcapng']:
            pcap_files.extend(self.pcap_dir.glob(pattern))
        
        # Sort by name for consistent ordering
        pcap_files.sort()
        
        if not pcap_files:
            logger.warning(f"No PCAP files found in {self.pcap_dir}")
        else:
            logger.info(f"Found PCAP files:")
            for f in pcap_files[:5]:  # Show first 5
                logger.info(f"  - {f.name}")
            if len(pcap_files) > 5:
                logger.info(f"  ... and {len(pcap_files) - 5} more")
        
        return pcap_files
    
    def _delivery_callback(self, err, msg):
        """Callback for message delivery"""
        if err:
            self.total_failed += 1
            logger.error(f"Delivery failed: {err}")
        else:
            self.total_produced += 1
    
    def _extract_packet_metadata(self, packet) -> Optional[Dict]:
        """Extract minimal metadata from packet"""
        try:
            metadata = {
                'ts': float(packet.sniff_timestamp),
                'raw_len': int(packet.length)
            }
            
            # Extract IP layer info
            if hasattr(packet, 'ip'):
                metadata['src_ip'] = str(packet.ip.src)
                metadata['dst_ip'] = str(packet.ip.dst)
                metadata['proto'] = 'IP'
                
                # TCP
                if hasattr(packet, 'tcp'):
                    metadata['proto'] = 'TCP'
                    metadata['src_port'] = int(packet.tcp.srcport)
                    metadata['dst_port'] = int(packet.tcp.dstport)
                # UDP
                elif hasattr(packet, 'udp'):
                    metadata['proto'] = 'UDP'
                    metadata['src_port'] = int(packet.udp.srcport)
                    metadata['dst_port'] = int(packet.udp.dstport)
                # ICMP
                elif hasattr(packet, 'icmp'):
                    metadata['proto'] = 'ICMP'
            
            # IPv6
            elif hasattr(packet, 'ipv6'):
                metadata['src_ip'] = str(packet.ipv6.src)
                metadata['dst_ip'] = str(packet.ipv6.dst)
                metadata['proto'] = 'IPv6'
            
            # ARP
            elif hasattr(packet, 'arp'):
                metadata['proto'] = 'ARP'
                if hasattr(packet.arp, 'src_proto_ipv4'):
                    metadata['src_ip'] = str(packet.arp.src_proto_ipv4)
                if hasattr(packet.arp, 'dst_proto_ipv4'):
                    metadata['dst_ip'] = str(packet.arp.dst_proto_ipv4)
            
            return metadata
        
        except Exception as e:
            logger.debug(f"Failed to extract packet metadata: {e}")
            return None
    
    def _process_pcap_file(self, pcap_file: Path):
        """Process a single PCAP file"""
        logger.info(f"Processing PCAP file: {pcap_file.name}")
        
        packets_in_file = 0
        batch_count = 0
        
        try:
            # Open PCAP file
            capture = pyshark.FileCapture(
                str(pcap_file),
                keep_packets=False  # Don't keep packets in memory
            )
            
            for packet in capture:
                # Check for shutdown
                if shutdown_event.is_set():
                    logger.info("Shutdown requested, stopping file processing")
                    break
                
                # Extract metadata
                metadata = self._extract_packet_metadata(packet)
                if not metadata:
                    continue
                
                # Produce to Kafka
                try:
                    self.producer.produce(
                        self.topic,
                        key=None,
                        value=json.dumps(metadata).encode('utf-8'),
                        callback=self._delivery_callback
                    )
                    
                    self.total_packets += 1
                    packets_in_file += 1
                    
                    # Batch flush and throttle
                    if self.total_packets % self.batch_size == 0:
                        self.producer.poll(0)
                        batch_count += 1
                        
                        # Throttle to avoid overwhelming the system
                        if self.delay_ms > 0:
                            time.sleep(self.delay_ms / 1000.0)
                        
                        # Log progress
                        if batch_count % 10 == 0:
                            logger.info(
                                f"  Processed {packets_in_file} packets from {pcap_file.name} "
                                f"(total: {self.total_packets}, produced: {self.total_produced})"
                            )
                
                except BufferError:
                    # Producer queue full, wait and retry
                    self.producer.poll(1)
                    self.producer.produce(
                        self.topic,
                        key=None,
                        value=json.dumps(metadata).encode('utf-8'),
                        callback=self._delivery_callback
                    )
            
            # Close capture
            capture.close()
            
            # Final flush for this file
            self.producer.flush()
            
            self.files_processed += 1
            logger.info(
                f"Completed {pcap_file.name}: {packets_in_file} packets "
                f"(total produced: {self.total_produced})"
            )
        
        except Exception as e:
            logger.error(f"Error processing {pcap_file}: {e}")
    
    def run(self):
        """Run the replay producer"""
        if not self.pcap_files:
            logger.error("No PCAP files to process")
            return
        
        logger.info("Starting PCAP replay...")
        logger.info(f"Press Ctrl+C to stop")
        
        start_time = time.time()
        
        try:
            while not shutdown_event.is_set():
                for pcap_file in self.pcap_files:
                    if shutdown_event.is_set():
                        break
                    
                    self._process_pcap_file(pcap_file)
                
                # If not looping, stop after one pass
                if not self.loop:
                    break
                
                # If looping, add a brief pause between cycles
                if self.loop and not shutdown_event.is_set():
                    logger.info("Completed one cycle, restarting from beginning...")
                    time.sleep(2)
        
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        
        finally:
            # Cleanup
            logger.info("Shutting down...")
            self.producer.flush(timeout=10)
            
            elapsed = time.time() - start_time
            logger.info("=" * 60)
            logger.info("Final Statistics:")
            logger.info(f"  Files Processed: {self.files_processed}")
            logger.info(f"  Packets Captured: {self.total_packets}")
            logger.info(f"  Packets Produced: {self.total_produced}")
            logger.info(f"  Packets Failed: {self.total_failed}")
            logger.info(f"  Elapsed Time: {elapsed:.1f}s")
            logger.info(f"  Rate: {self.total_produced / elapsed:.1f} packets/sec")
            logger.info("=" * 60)


def main():
    """Main entry point"""
    # Configuration from environment variables
    kafka_brokers = os.getenv('KAFKA_BROKERS', 'localhost:9092')
    topic = os.getenv('RAW_PACKETS_TOPIC', 'raw.packets')
    pcap_dir = os.getenv('PCAP_DIR', '/app/data')
    batch_size = int(os.getenv('BATCH_SIZE', '100'))
    delay_ms = int(os.getenv('DELAY_MS', '10'))
    loop = os.getenv('LOOP_PCAP', 'true').lower() in ('true', '1', 'yes')
    
    # Create and run producer
    producer = PcapReplayProducer(
        kafka_brokers=kafka_brokers,
        topic=topic,
        pcap_dir=pcap_dir,
        batch_size=batch_size,
        delay_ms=delay_ms,
        loop=loop
    )
    
    producer.run()


if __name__ == '__main__':
    main()
