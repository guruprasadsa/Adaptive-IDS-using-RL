"""
Real-time Flow Feature Extractor
Consumes raw packet metadata from Kafka, aggregates into flows, computes 41+ CICFlowMeter-compatible features,
applies online normalization, and produces to flows.features topic.
"""

import os
import sys
import json
import signal
import logging
import hashlib
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Event, Lock
import time

import numpy as np
from confluent_kafka import Consumer, Producer, KafkaError

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from schemas.models import FlowFeatures
except ImportError:
    print("ERROR: schemas module not found. Run from backend directory.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global shutdown event
shutdown_event = Event()


@dataclass
class PacketStats:
    """Statistics for a single packet direction (forward or backward)"""
    count: int = 0
    bytes: int = 0
    iat_times: List[float] = field(default_factory=list)  # Inter-arrival times
    pkt_sizes: List[int] = field(default_factory=list)
    
    # TCP flags
    fin_count: int = 0
    syn_count: int = 0
    rst_count: int = 0
    psh_count: int = 0
    ack_count: int = 0
    urg_count: int = 0
    ece_count: int = 0
    cwe_count: int = 0
    
    # Timing
    last_timestamp: Optional[float] = None
    
    def add_packet(self, size: int, timestamp: float, flags: Optional[Dict] = None):
        """Add packet statistics"""
        self.count += 1
        self.bytes += size
        self.pkt_sizes.append(size)
        
        # Calculate IAT
        if self.last_timestamp is not None:
            iat = timestamp - self.last_timestamp
            self.iat_times.append(iat)
        
        self.last_timestamp = timestamp
        
        # Update flags if provided (TCP only)
        if flags:
            self.fin_count += flags.get('FIN', 0)
            self.syn_count += flags.get('SYN', 0)
            self.rst_count += flags.get('RST', 0)
            self.psh_count += flags.get('PSH', 0)
            self.ack_count += flags.get('ACK', 0)
            self.urg_count += flags.get('URG', 0)
            self.ece_count += flags.get('ECE', 0)
            self.cwe_count += flags.get('CWE', 0)


@dataclass
class FlowRecord:
    """Represents a bidirectional network flow"""
    flow_id: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    
    # Timing
    start_time: float
    last_seen: float
    
    # Direction statistics
    forward: PacketStats = field(default_factory=PacketStats)
    backward: PacketStats = field(default_factory=PacketStats)
    
    # Additional metadata
    total_packets: int = 0
    total_bytes: int = 0
    
    def is_expired(self, current_time: float, active_timeout: float, idle_timeout: float) -> bool:
        """Check if flow has expired based on timeouts"""
        duration = current_time - self.start_time
        idle_time = current_time - self.last_seen
        
        return duration >= active_timeout or idle_time >= idle_timeout
    
    def add_packet(self, packet: Dict, is_forward: bool):
        """Add packet to flow statistics"""
        timestamp = packet['ts']
        size = packet['raw_len']
        
        # Update flow-level stats
        self.last_seen = timestamp
        self.total_packets += 1
        self.total_bytes += size
        
        # Update direction-specific stats
        stats = self.forward if is_forward else self.backward
        stats.add_packet(size, timestamp, flags=None)  # TCP flags parsing TODO
    
    def compute_features(self) -> List[float]:
        """
        Compute 41+ CICFlowMeter-compatible features
        Feature order is deterministic and matches CIC-IDS-2017/2018 datasets
        """
        features = []
        
        # 1. Flow duration (seconds)
        duration = max(self.last_seen - self.start_time, 1e-6)  # Avoid division by zero
        features.append(duration)
        
        # 2-3. Total forward/backward packets
        features.append(float(self.forward.count))
        features.append(float(self.backward.count))
        
        # 4-5. Total forward/backward bytes
        features.append(float(self.forward.bytes))
        features.append(float(self.backward.bytes))
        
        # 6-9. Forward packet length stats (min, max, mean, std)
        if self.forward.pkt_sizes:
            features.extend([
                float(min(self.forward.pkt_sizes)),
                float(max(self.forward.pkt_sizes)),
                float(np.mean(self.forward.pkt_sizes)),
                float(np.std(self.forward.pkt_sizes))
            ])
        else:
            features.extend([0.0, 0.0, 0.0, 0.0])
        
        # 10-13. Backward packet length stats
        if self.backward.pkt_sizes:
            features.extend([
                float(min(self.backward.pkt_sizes)),
                float(max(self.backward.pkt_sizes)),
                float(np.mean(self.backward.pkt_sizes)),
                float(np.std(self.backward.pkt_sizes))
            ])
        else:
            features.extend([0.0, 0.0, 0.0, 0.0])
        
        # 14-15. Flow packets/bytes per second
        features.append(self.total_packets / duration)
        features.append(self.total_bytes / duration)
        
        # 16-19. Forward IAT (Inter-Arrival Time) stats
        if self.forward.iat_times:
            features.extend([
                float(np.mean(self.forward.iat_times)),
                float(np.std(self.forward.iat_times)),
                float(max(self.forward.iat_times)),
                float(min(self.forward.iat_times))
            ])
        else:
            features.extend([0.0, 0.0, 0.0, 0.0])
        
        # 20-23. Backward IAT stats
        if self.backward.iat_times:
            features.extend([
                float(np.mean(self.backward.iat_times)),
                float(np.std(self.backward.iat_times)),
                float(max(self.backward.iat_times)),
                float(min(self.backward.iat_times))
            ])
        else:
            features.extend([0.0, 0.0, 0.0, 0.0])
        
        # 24-31. TCP flags counts
        features.extend([
            float(self.forward.fin_count),
            float(self.backward.fin_count),
            float(self.forward.syn_count),
            float(self.backward.syn_count),
            float(self.forward.rst_count),
            float(self.backward.rst_count),
            float(self.forward.psh_count),
            float(self.backward.psh_count)
        ])
        
        # 32-33. ACK flags
        features.extend([
            float(self.forward.ack_count),
            float(self.backward.ack_count)
        ])
        
        # 34-35. URG flags
        features.extend([
            float(self.forward.urg_count),
            float(self.backward.urg_count)
        ])
        
        # 36-37. Forward/Backward packet rate
        features.append(self.forward.count / duration if duration > 0 else 0.0)
        features.append(self.backward.count / duration if duration > 0 else 0.0)
        
        # 38-39. Forward/Backward byte rate
        features.append(self.forward.bytes / duration if duration > 0 else 0.0)
        features.append(self.backward.bytes / duration if duration > 0 else 0.0)
        
        # 40-41. Packet size ratio and byte ratio
        total_pkts = self.total_packets
        if total_pkts > 0:
            features.append(self.forward.count / total_pkts)
        else:
            features.append(0.0)
        
        if self.total_bytes > 0:
            features.append(self.forward.bytes / self.total_bytes)
        else:
            features.append(0.0)
        
        return features


class OnlineStandardScaler:
    """
    Incremental StandardScaler for online normalization
    Uses Welford's online algorithm for mean and variance
    """
    
    def __init__(self, n_features: int):
        self.n_features = n_features
        self.n_samples = 0
        self.mean = np.zeros(n_features)
        self.m2 = np.zeros(n_features)  # Sum of squared differences
        self.std = np.ones(n_features)
        
    def partial_fit(self, X: np.ndarray):
        """Update scaler with new samples"""
        if X.ndim == 1:
            X = X.reshape(1, -1)
        
        for sample in X:
            self.n_samples += 1
            delta = sample - self.mean
            self.mean += delta / self.n_samples
            delta2 = sample - self.mean
            self.m2 += delta * delta2
            
        # Update std
        if self.n_samples > 1:
            variance = self.m2 / (self.n_samples - 1)
            self.std = np.sqrt(variance)
            self.std[self.std < 1e-8] = 1.0  # Avoid division by zero
    
    def transform(self, X: np.ndarray) -> np.ndarray:
        """Normalize features"""
        if X.ndim == 1:
            X = X.reshape(1, -1)
        return (X - self.mean) / self.std
    
    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        """Fit and transform"""
        self.partial_fit(X)
        return self.transform(X)
    
    def save(self, path: Path):
        """Save scaler state"""
        state = {
            'n_features': self.n_features,
            'n_samples': self.n_samples,
            'mean': self.mean,
            'm2': self.m2,
            'std': self.std
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump(state, f)
        logger.info(f"Saved scaler state to {path} (n_samples={self.n_samples})")
    
    @classmethod
    def load(cls, path: Path) -> 'OnlineStandardScaler':
        """Load scaler state"""
        with open(path, 'rb') as f:
            state = pickle.load(f)
        
        scaler = cls(state['n_features'])
        scaler.n_samples = state['n_samples']
        scaler.mean = state['mean']
        scaler.m2 = state['m2']
        scaler.std = state['std']
        
        logger.info(f"Loaded scaler state from {path} (n_samples={scaler.n_samples})")
        return scaler


class FeatureExtractor:
    """
    Real-time flow feature extractor
    Consumes raw packets, aggregates into flows, computes features, normalizes, and produces
    """
    
    def __init__(
        self,
        kafka_brokers: str,
        input_topic: str,
        output_topic: str,
        consumer_group: str = "feature-extractor",
        active_timeout: float = 60.0,
        idle_timeout: float = 15.0,
        feature_version: str = "v1.0-cic41",
        state_dir: str = "stream/state"
    ):
        self.kafka_brokers = kafka_brokers
        self.input_topic = input_topic
        self.output_topic = output_topic
        self.active_timeout = active_timeout
        self.idle_timeout = idle_timeout
        self.feature_version = feature_version
        self.state_dir = Path(state_dir)
        
        # Flow tracking
        self.flows: Dict[str, FlowRecord] = {}
        self.flow_lock = Lock()
        
        # Initialize scaler
        self.n_features = 41
        scaler_path = self.state_dir / f"scaler_{feature_version}.pkl"
        if scaler_path.exists():
            self.scaler = OnlineStandardScaler.load(scaler_path)
        else:
            self.scaler = OnlineStandardScaler(self.n_features)
            logger.info(f"Initialized new scaler for {feature_version}")
        
        # Kafka clients
        self.consumer = self._create_consumer(consumer_group)
        self.producer = self._create_producer()
        
        # Metrics
        self.packets_processed = 0
        self.flows_created = 0
        self.flows_expired = 0
        self.features_produced = 0
        self.last_metrics_time = time.time()
        
        logger.info("FeatureExtractor initialized")
        logger.info(f"  Kafka Brokers: {kafka_brokers}")
        logger.info(f"  Input Topic: {input_topic}")
        logger.info(f"  Output Topic: {output_topic}")
        logger.info(f"  Active Timeout: {active_timeout}s")
        logger.info(f"  Idle Timeout: {idle_timeout}s")
        logger.info(f"  Feature Version: {feature_version}")
        logger.info(f"  Features: {self.n_features}")
    
    def _create_consumer(self, group_id: str) -> Consumer:
        """Create Kafka consumer"""
        config = {
            'bootstrap.servers': self.kafka_brokers,
            'group.id': group_id,
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': True,
            'auto.commit.interval.ms': 5000,
            'max.poll.interval.ms': 300000,
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
            'linger.ms': 10,
            'batch.size': 16384,
        }
        return Producer(config)
    
    def _delivery_callback(self, err, msg):
        """Kafka delivery callback"""
        if err:
            logger.error(f"Failed to deliver message: {err}")
        else:
            self.features_produced += 1
    
    def _create_flow_id(self, packet: Dict) -> Tuple[str, bool]:
        """
        Create bidirectional flow ID and determine if packet is forward direction
        Returns: (flow_id, is_forward)
        """
        src_ip = packet['src_ip']
        dst_ip = packet['dst_ip']
        src_port = packet['src_port']
        dst_port = packet['dst_port']
        proto = packet['proto']
        
        # Convert IPs to comparable format for canonical ordering
        def ip_to_tuple(ip_str):
            """Convert IP string to tuple of ints for proper comparison"""
            try:
                return tuple(int(part) for part in ip_str.split('.'))
            except:
                return (0, 0, 0, 0)
        
        src_ip_tuple = ip_to_tuple(src_ip)
        dst_ip_tuple = ip_to_tuple(dst_ip)
        
        # Canonical ordering: lower IP first, or if equal, lower port first
        if (src_ip_tuple, src_port) < (dst_ip_tuple, dst_port):
            flow_id = f"{src_ip}:{src_port}:{dst_ip}:{dst_port}:{proto}"
            is_forward = True
        else:
            flow_id = f"{dst_ip}:{dst_port}:{src_ip}:{src_port}:{proto}"
            is_forward = False
        
        return flow_id, is_forward
    
    def _process_packet(self, packet: Dict):
        """Process a single packet"""
        self.packets_processed += 1
        
        # Create or update flow
        flow_id, is_forward = self._create_flow_id(packet)
        
        with self.flow_lock:
            if flow_id not in self.flows:
                # Create new flow
                if is_forward:
                    flow = FlowRecord(
                        flow_id=flow_id,
                        src_ip=packet['src_ip'],
                        dst_ip=packet['dst_ip'],
                        src_port=packet['src_port'],
                        dst_port=packet['dst_port'],
                        protocol=packet['proto'],
                        start_time=packet['ts'],
                        last_seen=packet['ts']
                    )
                else:
                    # Reverse direction
                    flow = FlowRecord(
                        flow_id=flow_id,
                        src_ip=packet['dst_ip'],
                        dst_ip=packet['src_ip'],
                        src_port=packet['dst_port'],
                        dst_port=packet['src_port'],
                        protocol=packet['proto'],
                        start_time=packet['ts'],
                        last_seen=packet['ts']
                    )
                
                self.flows[flow_id] = flow
                self.flows_created += 1
            
            # Add packet to flow
            self.flows[flow_id].add_packet(packet, is_forward)
    
    def _check_expired_flows(self, current_time: float):
        """Check for and emit expired flows"""
        expired_flows = []
        
        with self.flow_lock:
            for flow_id, flow in list(self.flows.items()):
                if flow.is_expired(current_time, self.active_timeout, self.idle_timeout):
                    expired_flows.append(flow)
                    del self.flows[flow_id]
                    self.flows_expired += 1
        
        # Emit features for expired flows
        for flow in expired_flows:
            self._emit_flow(flow)
    
    def _emit_flow(self, flow: FlowRecord):
        """Compute features and emit to Kafka"""
        try:
            # Compute raw features
            raw_features = flow.compute_features()
            
            # Ensure correct length
            if len(raw_features) != self.n_features:
                logger.warning(
                    f"Feature length mismatch: expected {self.n_features}, got {len(raw_features)}"
                )
                return
            
            # Normalize features
            features_array = np.array(raw_features).reshape(1, -1)
            self.scaler.partial_fit(features_array)
            normalized_features = self.scaler.transform(features_array)[0].tolist()
            
            # Create FlowFeatures message
            flow_features = FlowFeatures(
                flow_id=flow.flow_id,
                timestamp=int(flow.start_time * 1000),  # Convert to ms
                src_ip=flow.src_ip,
                dst_ip=flow.dst_ip,
                src_port=flow.src_port,
                dst_port=flow.dst_port,
                protocol=flow.protocol,
                features=normalized_features,
                feature_version=self.feature_version,
                schema_version=1,
                metadata={
                    'duration': str(flow.last_seen - flow.start_time),
                    'total_packets': str(flow.total_packets),
                    'total_bytes': str(flow.total_bytes)
                }
            )
            
            # Produce to Kafka
            self.producer.produce(
                topic=self.output_topic,
                key=flow.flow_id.encode('utf-8'),
                value=json.dumps(flow_features.to_dict()).encode('utf-8'),
                callback=self._delivery_callback
            )
            
            self.producer.poll(0)
            
        except Exception as e:
            logger.error(f"Failed to emit flow {flow.flow_id}: {e}", exc_info=True)
    
    def _log_metrics(self):
        """Log processing metrics"""
        current_time = time.time()
        elapsed = current_time - self.last_metrics_time
        
        if elapsed >= 10.0:  # Log every 10 seconds
            packets_per_sec = self.packets_processed / elapsed if elapsed > 0 else 0
            
            logger.info("=" * 60)
            logger.info("Metrics:")
            logger.info(f"  Packets Processed: {self.packets_processed} ({packets_per_sec:.1f}/s)")
            logger.info(f"  Active Flows: {len(self.flows)}")
            logger.info(f"  Flows Created: {self.flows_created}")
            logger.info(f"  Flows Expired: {self.flows_expired}")
            logger.info(f"  Features Produced: {self.features_produced}")
            logger.info(f"  Scaler Samples: {self.scaler.n_samples}")
            logger.info("=" * 60)
            
            # Reset counters
            self.packets_processed = 0
            self.last_metrics_time = current_time
    
    def run(self):
        """Main processing loop"""
        logger.info("Starting feature extraction...")
        logger.info("Press Ctrl+C to stop...")
        
        try:
            while not shutdown_event.is_set():
                # Poll for messages
                msg = self.consumer.poll(timeout=1.0)
                
                if msg is None:
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                        continue
                
                # Parse packet
                try:
                    packet = json.loads(msg.value().decode('utf-8'))
                    self._process_packet(packet)
                    
                    # Check for expired flows periodically
                    current_time = time.time()
                    self._check_expired_flows(current_time)
                    
                    # Log metrics
                    self._log_metrics()
                    
                except Exception as e:
                    logger.error(f"Failed to process message: {e}")
                    continue
        
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down feature extractor...")
        
        # Emit all remaining flows
        with self.flow_lock:
            remaining = len(self.flows)
            if remaining > 0:
                logger.info(f"Emitting {remaining} remaining flows...")
                for flow in self.flows.values():
                    self._emit_flow(flow)
        
        # Flush producer
        remaining = self.producer.flush(timeout=10)
        if remaining > 0:
            logger.warning(f"Failed to flush {remaining} messages")
        
        # Save scaler state
        scaler_path = self.state_dir / f"scaler_{self.feature_version}.pkl"
        self.scaler.save(scaler_path)
        
        # Close consumer
        self.consumer.close()
        
        logger.info("Shutdown complete")


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}")
    shutdown_event.set()


def main():
    """Main entry point"""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Load environment
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent.parent / '.env'
        load_dotenv(env_path)
    except ImportError:
        pass
    
    # Configuration
    kafka_brokers = os.getenv('KAFKA_BROKERS', 'localhost:9092')
    input_topic = os.getenv('PACKETS_TOPIC', 'raw.packets')
    output_topic = os.getenv('FEATURES_TOPIC', 'flows.features')
    consumer_group = os.getenv('FEATURE_EXTRACTOR_GROUP', 'feature-extractor')
    active_timeout = float(os.getenv('FLOW_ACTIVE_TIMEOUT', '60.0'))
    idle_timeout = float(os.getenv('FLOW_IDLE_TIMEOUT', '15.0'))
    feature_version = os.getenv('FEATURE_VERSION', 'v1.0-cic41')
    state_dir = os.getenv('STATE_DIR', 'stream/state')
    
    # Create and run extractor
    try:
        extractor = FeatureExtractor(
            kafka_brokers=kafka_brokers,
            input_topic=input_topic,
            output_topic=output_topic,
            consumer_group=consumer_group,
            active_timeout=active_timeout,
            idle_timeout=idle_timeout,
            feature_version=feature_version,
            state_dir=state_dir
        )
        
        extractor.run()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
