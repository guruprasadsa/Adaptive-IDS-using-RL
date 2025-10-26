"""
Real Traffic Replay Script
Reads actual network traffic from CICIDS2017/2018 CSV files and produces to Kafka.
This simulates real production traffic using actual captured network data.
"""

import os
import sys
import json
import time
import random
import logging
import pandas as pd
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


# CICFlowMeter feature column names (standardized)
FEATURE_COLUMNS = [
    'Flow Duration', 'Total Fwd Packets', 'Total Backward Packets',
    'Total Length of Fwd Packets', 'Total Length of Bwd Packets',
    'Fwd Packet Length Max', 'Fwd Packet Length Min', 'Fwd Packet Length Mean', 'Fwd Packet Length Std',
    'Bwd Packet Length Max', 'Bwd Packet Length Min', 'Bwd Packet Length Mean', 'Bwd Packet Length Std',
    'Flow Bytes/s', 'Flow Packets/s', 'Flow IAT Mean', 'Flow IAT Std', 'Flow IAT Max', 'Flow IAT Min',
    'Fwd IAT Total', 'Fwd IAT Mean', 'Fwd IAT Std', 'Fwd IAT Max', 'Fwd IAT Min',
    'Bwd IAT Total', 'Bwd IAT Mean', 'Bwd IAT Std', 'Bwd IAT Max', 'Bwd IAT Min',
    'Fwd PSH Flags', 'Bwd PSH Flags', 'Fwd URG Flags', 'Bwd URG Flags',
    'Fwd Header Length', 'Bwd Header Length',
    'Fwd Packets/s', 'Bwd Packets/s',
    'Min Packet Length', 'Max Packet Length', 'Packet Length Mean', 'Packet Length Std', 'Packet Length Variance'
]


def normalize_column_name(col):
    """Normalize column names to handle variations in CSV files"""
    # Remove extra spaces and convert to title case
    col = ' '.join(col.split())
    
    # Common variations
    replacements = {
        'Fwd Packet Length Mean': 'Fwd Packet Length Mean',
        'Bwd Packet Length Mean': 'Bwd Packet Length Mean',
        'Flow Bytes/s': 'Flow Bytes/s',
        'Flow Packets/s': 'Flow Packets/s',
    }
    
    return replacements.get(col, col)


def csv_row_to_flow_features(row, feature_cols):
    """
    Convert a CSV row to FlowFeatures schema format.
    
    Args:
        row: pandas Series with network flow data
        feature_cols: List of column names to extract as features
    
    Returns:
        Dict matching FlowFeatures schema
    """
    # Extract flow identification
    src_ip = row.get('Source IP', row.get('Src IP', '192.168.1.1'))
    dst_ip = row.get('Destination IP', row.get('Dst IP', '10.0.0.1'))
    src_port = int(row.get('Source Port', row.get('Src Port', 0)))
    dst_port = int(row.get('Destination Port', row.get('Dst Port', 0)))
    protocol = str(row.get('Protocol', 'TCP')).upper()
    
    # Handle protocol number to name conversion
    if protocol.isdigit():
        proto_num = int(protocol)
        if proto_num == 6:
            protocol = 'TCP'
        elif proto_num == 17:
            protocol = 'UDP'
        elif proto_num == 1:
            protocol = 'ICMP'
    
    flow_id = f"{src_ip}:{src_port}:{dst_ip}:{dst_port}:{protocol}"
    
    # Extract and normalize features (exactly 41 features)
    features = []
    for col in feature_cols[:41]:  # Take first 41 features
        try:
            val = row.get(col, 0.0)
            # Handle NaN, inf, or invalid values
            if pd.isna(val) or val == float('inf') or val == float('-inf'):
                val = 0.0
            features.append(float(val))
        except (ValueError, TypeError):
            features.append(0.0)
    
    # Ensure exactly 41 features
    while len(features) < 41:
        features.append(0.0)
    features = features[:41]
    
    # Create flow record
    flow = {
        'flow_id': flow_id,
        'timestamp': int(time.time() * 1000),  # milliseconds since epoch
        'src_ip': src_ip,
        'dst_ip': dst_ip,
        'src_port': src_port,
        'dst_port': dst_port,
        'protocol': protocol,
        'features': features,
        'feature_version': 'v1.0',
        'schema_version': 1
    }
    
    return flow


def delivery_callback(err, msg):
    """Kafka delivery callback"""
    if err:
        logger.error(f'Message delivery failed: {err}')


def replay_csv_traffic(csv_path, kafka_brokers='127.0.0.1:9092', rate_per_second=10, max_flows=None):
    """
    Replay real network traffic from CSV file to Kafka.
    
    Args:
        csv_path: Path to CICIDS CSV file
        kafka_brokers: Kafka broker address
        rate_per_second: Number of flows to produce per second
        max_flows: Maximum number of flows to replay (None = all)
    """
    logger.info(f"Loading traffic data from: {csv_path}")
    
    # Read CSV file
    try:
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} flows from CSV")
    except Exception as e:
        logger.error(f"Failed to load CSV: {e}")
        return
    
    # Normalize column names
    df.columns = [normalize_column_name(col) for col in df.columns]
    
    # Identify available feature columns
    available_features = [col for col in FEATURE_COLUMNS if col in df.columns]
    logger.info(f"Found {len(available_features)} feature columns")
    
    if len(available_features) < 10:
        logger.error(f"Insufficient feature columns. Need at least 10, found {len(available_features)}")
        return
    
    # Create Kafka producer
    producer_config = {
        'bootstrap.servers': kafka_brokers,
        'compression.type': 'lz4',
        'client.id': 'real-traffic-replay'
    }
    producer = Producer(producer_config)
    
    logger.info(f"Starting traffic replay")
    logger.info(f"Kafka Brokers: {kafka_brokers}")
    logger.info(f"Rate: {rate_per_second} flows/sec")
    logger.info(f"Max flows: {max_flows or 'unlimited'}")
    
    # Replay traffic
    start_time = time.time()
    total_produced = 0
    total_rows = len(df) if max_flows is None else min(len(df), max_flows)
    
    # Sample rows if needed
    if max_flows and len(df) > max_flows:
        df = df.sample(n=max_flows, random_state=42)
    
    try:
        batch_start = time.time()
        for idx, row in df.iterrows():
            # Convert row to flow features
            try:
                flow = csv_row_to_flow_features(row, available_features)
                
                # Produce to Kafka
                producer.produce(
                    topic='flows.features',
                    value=json.dumps(flow).encode('utf-8'),
                    key=flow['flow_id'].encode('utf-8'),
                    callback=delivery_callback
                )
                total_produced += 1
                
                # Rate limiting
                if total_produced % rate_per_second == 0:
                    producer.flush()
                    elapsed = time.time() - batch_start
                    sleep_time = max(0, 1.0 - elapsed)
                    time.sleep(sleep_time)
                    batch_start = time.time()
                
                # Progress reporting
                if total_produced % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = total_produced / elapsed if elapsed > 0 else 0
                    progress = (total_produced / total_rows) * 100
                    logger.info(f"Progress: {progress:.1f}% | Produced {total_produced}/{total_rows} flows | Rate: {rate:.1f} flows/sec")
                    
            except Exception as e:
                logger.error(f"Error processing row {idx}: {e}")
                continue
                
    except KeyboardInterrupt:
        logger.info("Replay interrupted by user")
    
    finally:
        # Final flush
        logger.info("Flushing remaining messages...")
        producer.flush(timeout=10)
        
        elapsed = time.time() - start_time
        logger.info(f"Replay complete!")
        logger.info(f"Total time: {elapsed:.2f}s")
        logger.info(f"Total flows replayed: {total_produced}")
        logger.info(f"Average rate: {total_produced/elapsed:.2f} flows/sec")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Replay real network traffic from CSV')
    parser.add_argument('csv_file', help='Path to CICIDS CSV file')
    parser.add_argument('--kafka-brokers', default='127.0.0.1:9092', help='Kafka broker address')
    parser.add_argument('--rate', type=int, default=10, help='Flows per second')
    parser.add_argument('--max-flows', type=int, default=None, help='Maximum flows to replay')
    
    args = parser.parse_args()
    
    replay_csv_traffic(
        csv_path=args.csv_file,
        kafka_brokers=args.kafka_brokers,
        rate_per_second=args.rate,
        max_flows=args.max_flows
    )
