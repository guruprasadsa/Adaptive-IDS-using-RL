"""
Traffic Simulation Script
Simulates network traffic by producing flow features directly to Kafka flows.features topic.
This allows testing the complete pipeline (flows.features → predictions → alerts) without live packet capture.
"""

import os
import sys
import json
import time
import random
import logging
from pathlib import Path
from datetime import datetime
from confluent_kafka import Producer

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_sample_flow(flow_type='BENIGN'):
    """
    Create a sample flow feature record matching FlowFeatures schema.
    
    Args:
        flow_type: Type of traffic (BENIGN, DDoS, PortScan, etc.)
    
    Returns:
        Dict with flow features matching the FlowFeatures Pydantic schema
    """
    # Generate basic flow identification
    src_ip = f'192.168.{random.randint(1, 10)}.{random.randint(1, 254)}'
    src_port = random.randint(1024, 65535)
    dst_ip = f'10.0.{random.randint(0, 10)}.{random.randint(1, 254)}'
    dst_port = 80 if flow_type == 'Web Attack' else (22 if flow_type == 'SSH-Patator' else random.randint(1, 1024))
    protocol = random.choice(['TCP', 'UDP'])
    
    flow_id = f"{src_ip}:{src_port}:{dst_ip}:{dst_port}:{protocol}"
    
    # Generate 41+ feature values based on traffic type
    # These should match the features expected by the model
    features = []
    
    # Features 0-10: Flow duration and packet statistics
    if flow_type == 'DDoS':
        features.extend([
            random.uniform(0.001, 0.1),  # flow_duration (short for DDoS)
            float(random.randint(5000, 50000)),  # total_fwd_packets (high for DDoS)
            float(random.randint(10, 100)),  # total_bwd_packets
            float(random.randint(50000, 500000)),  # total_length_fwd_packets
            float(random.randint(200, 20000)),  # total_length_bwd_packets
        ])
    elif flow_type == 'PortScan':
        features.extend([
            random.uniform(0.001, 0.05),  # flow_duration (very short)
            float(random.randint(1, 5)),  # total_fwd_packets (few packets)
            float(random.randint(0, 2)),  # total_bwd_packets
            float(random.randint(40, 300)),  # total_length_fwd_packets
            float(random.randint(0, 200)),  # total_length_bwd_packets
        ])
    else:  # BENIGN and others
        features.extend([
            random.uniform(0.1, 10.0),  # flow_duration
            float(random.randint(10, 100)),  # total_fwd_packets
            float(random.randint(5, 50)),  # total_bwd_packets
            float(random.randint(500, 50000)),  # total_length_fwd_packets
            float(random.randint(200, 20000)),  # total_length_bwd_packets
        ])
    
    # Features 5-15: Packet length statistics (forward)
    features.extend([
        random.uniform(500, 1500),  # fwd_packet_length_max
        random.uniform(40, 100),  # fwd_packet_length_min
        random.uniform(100, 800),  # fwd_packet_length_mean
        random.uniform(50, 300),  # fwd_packet_length_std
    ])
    
    # Features 16-20: Packet length statistics (backward)
    features.extend([
        random.uniform(500, 1500),  # bwd_packet_length_max
        random.uniform(40, 100),  # bwd_packet_length_min
        random.uniform(100, 600),  # bwd_packet_length_mean
        random.uniform(50, 250),  # bwd_packet_length_std
    ])
    
    # Features 21-25: Flow statistics
    flow_pps = random.uniform(5000, 50000) if flow_type == 'DDoS' else random.uniform(10, 100)
    features.extend([
        random.uniform(1000, 100000) if flow_type == 'DDoS' else random.uniform(100, 10000),  # flow_bytes_per_s
        flow_pps,  # flow_packets_per_s
        random.uniform(0.00001, 0.0001) if flow_type == 'DDoS' else random.uniform(0.001, 1.0),  # flow_iat_mean
        random.uniform(0.001, 0.5),  # flow_iat_std
        random.uniform(0.01, 5.0),  # flow_iat_max
    ])
    
    # Features 26-35: IAT statistics
    features.extend([
        random.uniform(0.0001, 0.01),  # flow_iat_min
        random.uniform(0.1, 10.0),  # fwd_iat_total
        random.uniform(0.001, 1.0),  # fwd_iat_mean
        random.uniform(0.001, 0.5),  # fwd_iat_std
        random.uniform(0.01, 5.0),  # fwd_iat_max
        random.uniform(0.0001, 0.01),  # fwd_iat_min
        random.uniform(0.1, 5.0),  # bwd_iat_total
        random.uniform(0.001, 1.0),  # bwd_iat_mean
        random.uniform(0.001, 0.5),  # bwd_iat_std
        random.uniform(0.01, 5.0),  # bwd_iat_max
    ])
    
    # Features 36-41: Additional flow features (exactly 41 features total)
    features.extend([
        random.uniform(0.0001, 0.01),  # bwd_iat_min
        float(random.randint(0, 2)),  # fwd_psh_flags
        float(random.randint(0, 2)),  # bwd_psh_flags
        float(random.randint(20, 60)),  # fwd_header_length
        float(random.randint(20, 60)),  # bwd_header_length
        flow_pps * 0.7,  # fwd_packets_per_s
    ])
    
    # Ensure we have exactly 41 features (trim or pad)
    if len(features) > 41:
        features = features[:41]
    while len(features) < 41:
        features.append(0.0)
    
    # Create flow record matching FlowFeatures schema
    flow = {
        'flow_id': flow_id,
        'timestamp': int(time.time() * 1000),  # milliseconds since epoch
        'src_ip': src_ip,
        'dst_ip': dst_ip,
        'src_port': src_port,
        'dst_port': dst_port,
        'protocol': protocol,  # String (TCP/UDP)
        'features': features,  # List of float values
        'feature_version': 'v1.0',
        'schema_version': 1
    }
    
    return flow


def delivery_callback(err, msg):
    """Kafka delivery callback"""
    if err:
        logger.error(f'Message delivery failed: {err}')
    else:
        logger.debug(f'Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}')


def simulate_traffic(kafka_brokers='127.0.0.1:9092', duration_seconds=60, rate_per_second=10):
    """
    Simulate network traffic by producing flow features to Kafka.
    
    Args:
        kafka_brokers: Kafka broker address
        duration_seconds: How long to simulate traffic
        rate_per_second: Number of flows to generate per second
    """
    # Create Kafka producer
    producer_config = {
        'bootstrap.servers': kafka_brokers,
        'compression.type': 'lz4',
        'client.id': 'traffic-simulator'
    }
    producer = Producer(producer_config)
    
    logger.info(f"Starting traffic simulation")
    logger.info(f"Kafka Brokers: {kafka_brokers}")
    logger.info(f"Duration: {duration_seconds}s")
    logger.info(f"Rate: {rate_per_second} flows/sec")
    
    # Traffic mix (distribution of traffic types)
    traffic_mix = [
        ('BENIGN', 0.70),      # 70% benign
        ('DDoS', 0.10),        # 10% DDoS
        ('PortScan', 0.08),    # 8% PortScan
        ('Bot', 0.05),         # 5% Bot
        ('Infiltration', 0.02), # 2% Infiltration
        ('Web Attack', 0.03),   # 3% Web Attack
        ('Brute Force', 0.02)   # 2% Brute Force
    ]
    
    start_time = time.time()
    total_produced = 0
    
    try:
        while time.time() - start_time < duration_seconds:
            iteration_start = time.time()
            
            # Produce flows for this second
            for _ in range(rate_per_second):
                # Select traffic type based on distribution
                rand = random.random()
                cumulative = 0
                flow_type = 'BENIGN'
                for traffic_type, probability in traffic_mix:
                    cumulative += probability
                    if rand <= cumulative:
                        flow_type = traffic_type
                        break
                
                # Create and produce flow
                flow = create_sample_flow(flow_type)
                
                # Produce to Kafka as JSON
                producer.produce(
                    topic='flows.features',
                    value=json.dumps(flow).encode('utf-8'),
                    key=flow['flow_id'].encode('utf-8'),
                    callback=delivery_callback
                )
                total_produced += 1
            
            # Flush periodically
            if total_produced % 100 == 0:
                producer.flush()
                logger.info(f"Produced {total_produced} flows ({flow_type} - last type)")
            
            # Sleep to maintain rate (approximately 1 second per iteration)
            iteration_duration = time.time() - iteration_start
            sleep_time = max(0, 1.0 - iteration_duration)
            time.sleep(sleep_time)
    
    except KeyboardInterrupt:
        logger.info("Simulation interrupted by user")
    
    finally:
        # Final flush
        logger.info("Flushing remaining messages...")
        producer.flush(timeout=10)
        
        elapsed = time.time() - start_time
        logger.info(f"Simulation complete!")
        logger.info(f"Total time: {elapsed:.2f}s")
        logger.info(f"Total flows produced: {total_produced}")
        logger.info(f"Average rate: {total_produced/elapsed:.2f} flows/sec")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Simulate network traffic')
    parser.add_argument('--kafka-brokers', default='127.0.0.1:9092', help='Kafka broker address')
    parser.add_argument('--duration', type=int, default=60, help='Duration in seconds')
    parser.add_argument('--rate', type=int, default=10, help='Flows per second')
    
    args = parser.parse_args()
    
    simulate_traffic(
        kafka_brokers=args.kafka_brokers,
        duration_seconds=args.duration,
        rate_per_second=args.rate
    )
