"""
CSV Packet Replay Producer for Kafka
Reads pre-processed CSV network traffic data and simulates packets to Kafka.
Designed for CICIDS2017/2018 and similar datasets.
"""

import csv
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


class CsvReplayProducer:
    """
    Replays CSV network traffic files and produces packet metadata to Kafka.
    Supports CICIDS2017/2018 format CSV files.
    """
    
    def __init__(
        self,
        kafka_brokers: str,
        topic: str,
        csv_dir: str,
        batch_size: int = 100,
        delay_ms: int = 5,
        loop: bool = True,
        max_rows_per_file: int = None
    ):
        """
        Initialize CSV replay producer.
        
        Args:
            kafka_brokers: Comma-separated Kafka broker addresses
            topic: Kafka topic to produce to
            csv_dir: Directory containing CSV files
            batch_size: Number of packets to buffer before flushing
            delay_ms: Delay in milliseconds between batches
            loop: Whether to loop through CSV files continuously
            max_rows_per_file: Maximum rows to read per file (None = unlimited)
        """
        self.kafka_brokers = kafka_brokers
        self.topic = topic
        self.csv_dir = Path(csv_dir)
        self.batch_size = batch_size
        self.delay_ms = delay_ms
        self.loop = loop
        self.max_rows_per_file = max_rows_per_file
        
        # Statistics
        self.total_packets = 0
        self.total_produced = 0
        self.total_failed = 0
        self.files_processed = 0
        
        # Create producer
        self.producer = self._create_producer()
        
        # Find CSV files
        self.csv_files = self._find_csv_files()
        
        logger.info("CsvReplayProducer initialized")
        logger.info(f"  Kafka Brokers: {kafka_brokers}")
        logger.info(f"  Topic: {topic}")
        logger.info(f"  CSV Directory: {csv_dir}")
        logger.info(f"  Batch Size: {batch_size}")
        logger.info(f"  Delay: {delay_ms}ms")
        logger.info(f"  Loop: {loop}")
        logger.info(f"  Max Rows/File: {max_rows_per_file or 'unlimited'}")
        logger.info(f"  Found {len(self.csv_files)} CSV files")
    
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
            'client.id': 'csv-replay-producer',
            'linger.ms': 10,
            'batch.size': 16384,
        }
        return Producer(config)
    
    def _find_csv_files(self) -> List[Path]:
        """Find all CSV files in directory"""
        if not self.csv_dir.exists():
            logger.error(f"CSV directory not found: {self.csv_dir}")
            return []
        
        # Search for CSV files
        csv_files = list(self.csv_dir.glob('**/*.csv'))
        csv_files.sort()
        
        if not csv_files:
            logger.warning(f"No CSV files found in {self.csv_dir}")
        else:
            logger.info(f"Found CSV files:")
            for f in csv_files:
                logger.info(f"  - {f.name}")
        
        return csv_files
    
    def _delivery_callback(self, err, msg):
        """Callback for message delivery"""
        if err:
            self.total_failed += 1
            if self.total_failed % 100 == 0:
                logger.error(f"Delivery failed (total: {self.total_failed}): {err}")
        else:
            self.total_produced += 1
    
    def _csv_row_to_packet(self, row: Dict[str, str]) -> Optional[Dict]:
        """
        Convert CSV row to packet metadata.
        Handles CICIDS2017/2018 format.
        """
        try:
            # Extract key fields (case-insensitive column matching)
            row_lower = {k.strip().lower(): v for k, v in row.items()}
            
            # Build packet metadata
            packet = {
                'ts': time.time(),  # Current time for replay
                'raw_len': int(float(row_lower.get('total length of fwd packets', 0) or 0)) + \
                          int(float(row_lower.get('total length of bwd packets', 0) or 0)),
            }
            
            # Source IP
            for key in ['source ip', 'src ip', ' source ip']:
                if key in row_lower and row_lower[key]:
                    packet['src_ip'] = str(row_lower[key]).strip()
                    break
            
            # Destination IP
            for key in ['destination ip', 'dst ip', ' destination ip']:
                if key in row_lower and row_lower[key]:
                    packet['dst_ip'] = str(row_lower[key]).strip()
                    break
            
            # Source Port
            for key in ['source port', 'src port', ' source port']:
                if key in row_lower and row_lower[key]:
                    try:
                        packet['src_port'] = int(float(row_lower[key]))
                    except:
                        pass
                    break
            
            # Destination Port
            for key in ['destination port', 'dst port', ' destination port']:
                if key in row_lower and row_lower[key]:
                    try:
                        packet['dst_port'] = int(float(row_lower[key]))
                    except:
                        pass
                    break
            
            # Protocol
            for key in ['protocol', ' protocol']:
                if key in row_lower and row_lower[key]:
                    proto_val = str(row_lower[key]).strip()
                    if proto_val.isdigit():
                        # Protocol number
                        proto_num = int(proto_val)
                        packet['proto'] = {6: 'TCP', 17: 'UDP', 1: 'ICMP'}.get(proto_num, f'PROTO_{proto_num}')
                    else:
                        packet['proto'] = proto_val.upper()
                    break
            
            # Default protocol if not found
            if 'proto' not in packet:
                packet['proto'] = 'TCP'  # Default
            
            # Ensure we have at least basic info
            if 'src_ip' not in packet or 'dst_ip' not in packet:
                return None
            
            if packet['raw_len'] == 0:
                packet['raw_len'] = 60  # Minimum packet size
            
            return packet
        
        except Exception as e:
            logger.debug(f"Failed to convert CSV row to packet: {e}")
            return None
    
    def _process_csv_file(self, csv_file: Path):
        """Process a single CSV file"""
        logger.info(f"Processing CSV file: {csv_file.name}")
        
        packets_in_file = 0
        rows_processed = 0
        batch_count = 0
        
        try:
            with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                # Try to detect CSV format
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Check for shutdown
                    if shutdown_event.is_set():
                        logger.info("Shutdown requested, stopping file processing")
                        break
                    
                    rows_processed += 1
                    
                    # Check max rows limit
                    if self.max_rows_per_file and rows_processed > self.max_rows_per_file:
                        logger.info(f"  Reached max rows limit ({self.max_rows_per_file})")
                        break
                    
                    # Convert to packet
                    packet = self._csv_row_to_packet(row)
                    if not packet:
                        continue
                    
                    # Produce to Kafka
                    try:
                        self.producer.produce(
                            self.topic,
                            key=None,
                            value=json.dumps(packet).encode('utf-8'),
                            callback=self._delivery_callback
                        )
                        
                        self.total_packets += 1
                        packets_in_file += 1
                        
                        # Batch flush and throttle
                        if self.total_packets % self.batch_size == 0:
                            self.producer.poll(0)
                            batch_count += 1
                            
                            # Throttle
                            if self.delay_ms > 0:
                                time.sleep(self.delay_ms / 1000.0)
                            
                            # Log progress
                            if batch_count % 20 == 0:
                                logger.info(
                                    f"  Processed {packets_in_file} packets from {csv_file.name} "
                                    f"(total: {self.total_packets}, produced: {self.total_produced})"
                                )
                    
                    except BufferError:
                        # Producer queue full, wait and retry
                        self.producer.poll(1)
                        self.producer.produce(
                            self.topic,
                            key=None,
                            value=json.dumps(packet).encode('utf-8'),
                            callback=self._delivery_callback
                        )
            
            # Final flush for this file
            self.producer.flush()
            
            self.files_processed += 1
            logger.info(
                f"Completed {csv_file.name}: {packets_in_file} packets from {rows_processed} rows "
                f"(total produced: {self.total_produced})"
            )
        
        except Exception as e:
            logger.error(f"Error processing {csv_file}: {e}")
    
    def run(self):
        """Run the replay producer"""
        if not self.csv_files:
            logger.error("No CSV files to process")
            return
        
        logger.info("Starting CSV replay...")
        logger.info("Press Ctrl+C to stop")
        
        start_time = time.time()
        
        try:
            while not shutdown_event.is_set():
                for csv_file in self.csv_files:
                    if shutdown_event.is_set():
                        break
                    
                    self._process_csv_file(csv_file)
                
                # If not looping, stop after one pass
                if not self.loop:
                    break
                
                # If looping, add a brief pause between cycles
                if self.loop and not shutdown_event.is_set():
                    logger.info("Completed one cycle, restarting from beginning...")
                    time.sleep(5)
        
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
            logger.info(f"  Packets Produced: {self.total_produced}")
            logger.info(f"  Packets Failed: {self.total_failed}")
            logger.info(f"  Elapsed Time: {elapsed:.1f}s")
            if elapsed > 0:
                logger.info(f"  Rate: {self.total_produced / elapsed:.1f} packets/sec")
            logger.info("=" * 60)


def main():
    """Main entry point"""
    # Configuration from environment variables
    kafka_brokers = os.getenv('KAFKA_BROKERS', 'localhost:9092')
    topic = os.getenv('RAW_PACKETS_TOPIC', 'raw.packets')
    csv_dir = os.getenv('CSV_DIR', '/app/data/2017')
    batch_size = int(os.getenv('BATCH_SIZE', '100'))
    delay_ms = int(os.getenv('DELAY_MS', '5'))
    loop = os.getenv('LOOP_CSV', 'true').lower() in ('true', '1', 'yes')
    max_rows = os.getenv('MAX_ROWS_PER_FILE')
    max_rows_per_file = int(max_rows) if max_rows else None
    
    # Create and run producer
    producer = CsvReplayProducer(
        kafka_brokers=kafka_brokers,
        topic=topic,
        csv_dir=csv_dir,
        batch_size=batch_size,
        delay_ms=delay_ms,
        loop=loop,
        max_rows_per_file=max_rows_per_file
    )
    
    producer.run()


if __name__ == '__main__':
    main()
