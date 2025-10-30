"""
Simple Network Traffic Simulator for Kafka
Generates realistic simulated network packets for development/testing.
Creates diverse traffic patterns including web, DNS, SSH, database, etc.
"""

import json
import logging
import os
import random
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Dict, List

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
    print("ERROR: confluent-kafka not installed")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

shutdown_event = Event()


def signal_handler(signum, frame):
    logger.info("Received shutdown signal")
    shutdown_event.set()


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class TrafficSimulator:
    """Generates realistic network traffic patterns"""
    
    # Common services and their typical behaviors
    TRAFFIC_PATTERNS = [
        # Web traffic (HTTP/HTTPS) - Benign (reduced to make room for attacks)
        {'name': 'web_http', 'proto': 'TCP', 'dst_port': 80, 'weight': 8, 'size_range': (60, 1500), 'attack': None},
        {'name': 'web_https', 'proto': 'TCP', 'dst_port': 443, 'weight': 10, 'size_range': (60, 1500), 'attack': None},
        
        # DNS queries - Benign
        {'name': 'dns', 'proto': 'UDP', 'dst_port': 53, 'weight': 6, 'size_range': (60, 512), 'attack': None},
        
        # SSH connections - Benign
        {'name': 'ssh', 'proto': 'TCP', 'dst_port': 22, 'weight': 2, 'size_range': (60, 200), 'attack': None},
        
        # Database - Benign
        {'name': 'mysql', 'proto': 'TCP', 'dst_port': 3306, 'weight': 2, 'size_range': (60, 1000), 'attack': None},
        
        # Attack patterns - DDoS REDUCED, other attacks INCREASED for diversity
        {'name': 'ddos_syn', 'proto': 'TCP', 'dst_port': 80, 'weight': 3, 'size_range': (40, 60), 'attack': 'DDoS'},
        {'name': 'ddos_http', 'proto': 'TCP', 'dst_port': 80, 'weight': 2, 'size_range': (60, 100), 'attack': 'DDoS'},
        {'name': 'hulk_flood', 'proto': 'TCP', 'dst_port': 80, 'weight': 15, 'size_range': (200, 1500), 'attack': 'Hulk'},
        {'name': 'goldeneye', 'proto': 'TCP', 'dst_port': 80, 'weight': 14, 'size_range': (100, 500), 'attack': 'GoldenEye'},
        {'name': 'slowloris', 'proto': 'TCP', 'dst_port': 80, 'weight': 13, 'size_range': (60, 100), 'attack': 'Slowloris'},
        {'name': 'slowhttp', 'proto': 'TCP', 'dst_port': 80, 'weight': 12, 'size_range': (60, 200), 'attack': 'Slowhttptest'},
        {'name': 'port_scan', 'proto': 'TCP', 'dst_port': None, 'weight': 16, 'size_range': (40, 60), 'attack': 'PortScan'},
        {'name': 'ftp_brute', 'proto': 'TCP', 'dst_port': 21, 'weight': 13, 'size_range': (60, 150), 'attack': 'FTP-Patator'},
        {'name': 'ssh_brute', 'proto': 'TCP', 'dst_port': 22, 'weight': 14, 'size_range': (60, 150), 'attack': 'SSH-Patator'},
        {'name': 'botnet_c2', 'proto': 'TCP', 'dst_port': 6667, 'weight': 15, 'size_range': (100, 300), 'attack': 'Botnet'},
    ]
    
    # Internal network ranges
    INTERNAL_SUBNETS = [
        '192.168.1',
        '192.168.0',
        '10.0.0',
        '10.0.1',
        '172.16.0',
    ]
    
    # External IP ranges (simulated)
    EXTERNAL_SUBNETS = [
        '8.8.8',      # Google DNS
        '1.1.1',      # Cloudflare
        '13.107.4',   # Microsoft
        '151.101.1',  # Fastly CDN
        '104.16.1',   # Cloudflare CDN
        '172.217.1',  # Google
        '23.20.0',    # AWS
    ]
    
    def __init__(
        self,
        kafka_brokers: str,
        topic: str,
        rate_pps: int = 100,
        burst_enabled: bool = True
    ):
        self.kafka_brokers = kafka_brokers
        self.topic = topic
        self.rate_pps = rate_pps
        self.burst_enabled = burst_enabled
        
        # Stats
        self.total_produced = 0
        self.total_failed = 0
        
        # Create producer
        self.producer = self._create_producer()
        
        # Weighted traffic patterns
        self.patterns = []
        total_weight = sum(p['weight'] for p in self.TRAFFIC_PATTERNS)
        for pattern in self.TRAFFIC_PATTERNS:
            self.patterns.extend([pattern] * pattern['weight'])
        
        logger.info("TrafficSimulator initialized")
        logger.info(f"  Kafka Brokers: {kafka_brokers}")
        logger.info(f"  Topic: {topic}")
        logger.info(f"  Rate: {rate_pps} packets/sec")
        logger.info(f"  Burst: {burst_enabled}")
        logger.info(f"  Traffic patterns: {len(self.TRAFFIC_PATTERNS)}")
    
    def _create_producer(self) -> Producer:
        config = {
            'bootstrap.servers': self.kafka_brokers,
            'compression.type': 'lz4',
            'enable.idempotence': True,
            'acks': 'all',
            'linger.ms': 10,
            'batch.size': 16384,
        }
        return Producer(config)
    
    def _generate_ip(self, internal: bool = True) -> str:
        """Generate a random IP address"""
        if internal:
            subnet = random.choice(self.INTERNAL_SUBNETS)
        else:
            subnet = random.choice(self.EXTERNAL_SUBNETS)
        return f"{subnet}.{random.randint(1, 254)}"
    
    def _generate_packet(self) -> Dict:
        """Generate a simulated packet with attack-specific behaviors"""
        pattern = random.choice(self.patterns)
        
        # Determine direction (outbound vs inbound)
        outbound = random.random() < 0.6  # 60% outbound
        
        if outbound:
            src_ip = self._generate_ip(internal=True)
            dst_ip = self._generate_ip(internal=False)
            src_port = random.randint(49152, 65535)  # Ephemeral ports
            dst_port = pattern['dst_port'] if pattern['dst_port'] else random.randint(1, 1024)
        else:
            src_ip = self._generate_ip(internal=False)
            dst_ip = self._generate_ip(internal=True)
            src_port = pattern['dst_port'] if pattern['dst_port'] else random.randint(1, 1024)
            dst_port = random.randint(49152, 65535)
        
        # Generate packet size
        size = random.randint(*pattern['size_range'])
        
        # Attack-specific behaviors
        attack_type = pattern.get('attack', None)
        
        if attack_type == 'PortScan':
            # Port scan - sequential or random ports from same source
            dst_port = random.randint(1, 65535)
            if random.random() < 0.9:  # 90% from same scanners
                src_ip = random.choice(['192.168.1.100', '192.168.1.101', '192.168.1.102'])
            # Often scan multiple targets
            if random.random() < 0.5:
                dst_ip = f"10.0.0.{random.randint(1, 254)}"
            size = random.randint(40, 64)  # Very small SYN packets
        
        elif attack_type == 'DDoS':
            # DDoS - flood same target from many sources with small packets
            if random.random() < 0.8:
                dst_ip = random.choice(['10.0.0.100', '10.0.0.101'])  # Common targets
            # Many different source IPs (distributed attack)
            src_ip = f"192.168.{random.randint(0, 2)}.{random.randint(1, 254)}"
            size = random.randint(40, 90)  # Small packets for SYN flood
            dst_port = random.choice([80, 443, 53, 22])  # Common target ports
        
        elif attack_type == 'Hulk':
            # Hulk - HTTP flood with large payloads and high rate
            dst_port = random.choice([80, 443, 8080])
            if random.random() < 0.7:
                dst_ip = '10.0.0.100'  # Target web server
            size = random.randint(800, 1500)  # Very large HTTP requests
            # Multiple concurrent connections from same source
            if random.random() < 0.6:
                src_ip = random.choice(['192.168.1.50', '192.168.1.51', '192.168.1.52'])
        
        elif attack_type == 'GoldenEye':
            # GoldenEye - HTTP DoS with random parameters and Keep-Alive
            dst_port = random.choice([80, 443, 8080])
            if random.random() < 0.6:
                dst_ip = '10.0.0.100'
            size = random.randint(300, 900)  # Medium sized requests
            # Randomize source ports more
            src_port = random.randint(1024, 65535)
        
        elif attack_type == 'Slowloris':
            # Slowloris - Keep-alive exhaustion, very small packets, slow rate
            dst_port = 80
            if random.random() < 0.85:
                dst_ip = '10.0.0.100'
                # Single or few attackers
                src_ip = random.choice(['192.168.1.60', '192.168.1.61'])
            size = random.randint(40, 80)  # Very small partial requests
            # Low packet rate is key characteristic
        
        elif attack_type == 'Slowhttptest':
            # Slow HTTP - Slow headers/body, POST requests
            dst_port = 80
            if random.random() < 0.75:
                dst_ip = '10.0.0.100'
                src_ip = random.choice(['192.168.1.70', '192.168.1.71', '192.168.1.72'])
            size = random.randint(80, 250)  # Small to medium packets
        
        elif attack_type == 'FTP-Patator':
            # FTP Brute force - Repeated login attempts to port 21
            dst_port = 21
            if random.random() < 0.95:
                src_ip = random.choice(['192.168.1.150', '192.168.1.151'])  # 1-2 attackers
                dst_ip = '10.0.0.50'  # FTP server
            size = random.randint(60, 120)  # Small FTP commands
            # High frequency from same source
        
        elif attack_type == 'SSH-Patator':
            # SSH Brute force - Repeated login attempts to port 22
            dst_port = 22
            if random.random() < 0.95:
                src_ip = random.choice(['192.168.1.160', '192.168.1.161'])  # 1-2 attackers
                dst_ip = '10.0.0.51'  # SSH server
            size = random.randint(70, 130)  # Small SSH auth packets
            # High frequency from same source
        
        elif attack_type == 'Botnet':
            # Botnet C2 - Periodic beaconing, distinctive ports and patterns
            dst_port = random.choice([6667, 6668, 8080, 443, 1337])  # IRC or HTTP C2
            if random.random() < 0.5:
                dst_ip = random.choice(['203.0.113.50', '203.0.113.51'])  # C2 servers
            # Infected hosts beaconing
            if random.random() < 0.7:
                src_ip = random.choice([
                    '192.168.1.200', '192.168.1.201', '192.168.1.202',
                    '192.168.1.203', '192.168.1.204'
                ])
            size = random.randint(100, 400)  # Small to medium command packets
            # Regular intervals are characteristic
        
        packet = {
            'ts': time.time(),
            'raw_len': size,
            'src_ip': src_ip,
            'dst_ip': dst_ip,
            'proto': pattern['proto'],
            'src_port': src_port,
            'dst_port': dst_port,
        }
        
        return packet
    
    def _delivery_callback(self, err, msg):
        if err:
            self.total_failed += 1
        else:
            self.total_produced += 1
    
    def run(self):
        """Run traffic simulator"""
        logger.info("Starting traffic simulator...")
        logger.info("Press Ctrl+C to stop")
        
        start_time = time.time()
        last_log_time = start_time
        packets_since_log = 0
        
        # Calculate delay between packets
        delay = 1.0 / self.rate_pps if self.rate_pps > 0 else 0.01
        
        try:
            while not shutdown_event.is_set():
                # Generate burst occasionally
                if self.burst_enabled and random.random() < 0.05:  # 5% chance
                    burst_size = random.randint(50, 200)
                    logger.info(f"Generating burst of {burst_size} packets")
                    
                    for _ in range(burst_size):
                        packet = self._generate_packet()
                        self.producer.produce(
                            self.topic,
                            value=json.dumps(packet).encode('utf-8'),
                            callback=self._delivery_callback
                        )
                        packets_since_log += 1
                    
                    self.producer.poll(0)
                    time.sleep(0.5)  # Brief pause after burst
                
                # Normal packet
                packet = self._generate_packet()
                
                try:
                    self.producer.produce(
                        self.topic,
                        value=json.dumps(packet).encode('utf-8'),
                        callback=self._delivery_callback
                    )
                    packets_since_log += 1
                    
                    # Poll occasionally
                    if packets_since_log % 50 == 0:
                        self.producer.poll(0)
                    
                except BufferError:
                    self.producer.poll(1)
                
                # Logging
                current_time = time.time()
                if current_time - last_log_time >= 10:
                    rate = packets_since_log / (current_time - last_log_time)
                    logger.info(
                        f"Generated {packets_since_log} packets in 10s "
                        f"(~{rate:.1f} pkt/s, total: {self.total_produced})"
                    )
                    packets_since_log = 0
                    last_log_time = current_time
                
                # Rate limiting
                time.sleep(delay)
        
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        
        finally:
            logger.info("Shutting down...")
            self.producer.flush(timeout=10)
            
            elapsed = time.time() - start_time
            logger.info("=" * 60)
            logger.info("Final Statistics:")
            logger.info(f"  Packets Generated: {self.total_produced}")
            logger.info(f"  Packets Failed: {self.total_failed}")
            logger.info(f"  Elapsed Time: {elapsed:.1f}s")
            if elapsed > 0:
                logger.info(f"  Average Rate: {self.total_produced / elapsed:.1f} pkt/s")
            logger.info("=" * 60)


def main():
    kafka_brokers = os.getenv('KAFKA_BROKERS', 'localhost:9092')
    topic = os.getenv('RAW_PACKETS_TOPIC', 'raw.packets')
    rate_pps = int(os.getenv('RATE_PPS', '100'))
    burst_enabled = os.getenv('BURST_ENABLED', 'true').lower() in ('true', '1', 'yes')
    
    simulator = TrafficSimulator(
        kafka_brokers=kafka_brokers,
        topic=topic,
        rate_pps=rate_pps,
        burst_enabled=burst_enabled
    )
    
    simulator.run()


if __name__ == '__main__':
    main()
