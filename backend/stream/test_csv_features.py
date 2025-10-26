"""
Test feature extraction with real CSV data from CIC-IDS-2017/2018 datasets
"""

import sys
import csv
import time
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from stream.feature_extractor import FlowRecord, OnlineStandardScaler


def load_flows_from_csv(csv_path: Path, max_flows: int = 20):
    """
    Load flows from CIC-IDS CSV files
    Returns list of FlowRecord objects
    """
    flows = {}
    flow_count = 0
    
    print(f"Loading flows from: {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        # Try to detect column names
        reader = csv.DictReader(f)
        
        for i, row in enumerate(reader):
            if flow_count >= max_flows:
                break
            
            try:
                # CIC-IDS-2017/2018 column mapping
                src_ip = row.get('Source IP', row.get(' Source IP', ''))
                dst_ip = row.get('Destination IP', row.get(' Destination IP', ''))
                src_port = int(row.get('Source Port', row.get(' Source Port', 0)))
                dst_port = int(row.get('Destination Port', row.get(' Destination Port', 0)))
                protocol = row.get('Protocol', row.get(' Protocol', 'TCP'))
                
                # Timing
                timestamp_str = row.get('Timestamp', row.get(' Timestamp', ''))
                if not timestamp_str:
                    continue
                
                # Parse timestamp (CIC format: DD/MM/YYYY HH:MM:SS)
                try:
                    from datetime import datetime
                    dt = datetime.strptime(timestamp_str.strip(), '%d/%m/%Y %H:%M:%S')
                    timestamp = dt.timestamp()
                except:
                    timestamp = float(i)
                
                # Packet info
                total_fwd_packets = int(row.get('Total Fwd Packets', row.get(' Total Fwd Packets', 0)))
                total_bwd_packets = int(row.get('Total Backward Packets', row.get(' Total Backward Packets', 0)))
                
                # Create flow ID
                flow_id = f"{src_ip}:{src_port}:{dst_ip}:{dst_port}:{protocol}"
                
                # Create flow if new
                if flow_id not in flows:
                    flow = FlowRecord(
                        flow_id=flow_id,
                        src_ip=src_ip,
                        dst_ip=dst_ip,
                        src_port=src_port,
                        dst_port=dst_port,
                        protocol=str(protocol),
                        start_time=timestamp,
                        last_seen=timestamp
                    )
                    
                    # Simulate packets based on counts
                    # Forward packets
                    for j in range(min(total_fwd_packets, 10)):
                        pkt = {
                            'ts': timestamp + j * 0.1,
                            'raw_len': 100 + j * 10
                        }
                        flow.add_packet(pkt, is_forward=True)
                    
                    # Backward packets
                    for j in range(min(total_bwd_packets, 10)):
                        pkt = {
                            'ts': timestamp + 0.05 + j * 0.1,
                            'raw_len': 200 + j * 20
                        }
                        flow.add_packet(pkt, is_forward=False)
                    
                    flows[flow_id] = flow
                    flow_count += 1
                    
                    if flow_count % 5 == 0:
                        print(f"  Loaded {flow_count} flows...")
            
            except Exception as e:
                continue
    
    print(f"Loaded {len(flows)} flows from {csv_path.name}")
    return list(flows.values())


def test_feature_extraction_from_csv():
    """Test feature extraction with real CSV data"""
    
    # Find CSV files
    data_dir = Path(__file__).parent.parent.parent / 'data'
    
    if not data_dir.exists():
        print(f"ERROR: Data directory not found: {data_dir}")
        return
    
    # Try to find CSV files
    csv_files = list(data_dir.rglob('*.csv'))
    
    if not csv_files:
        print(f"ERROR: No CSV files found in {data_dir}")
        return
    
    print(f"Found {len(csv_files)} CSV files")
    print("=" * 60)
    
    all_flows = []
    
    # Load flows from first few CSV files
    for csv_file in csv_files[:3]:  # Test with first 3 files
        try:
            flows = load_flows_from_csv(csv_file, max_flows=20)
            all_flows.extend(flows)
        except Exception as e:
            print(f"  Skipping {csv_file.name}: {e}")
    
    if not all_flows:
        print("ERROR: No flows loaded")
        return
    
    print("=" * 60)
    print(f"\nTotal flows loaded: {len(all_flows)}")
    print("=" * 60)
    
    # Compute features
    print("\nComputing features...")
    feature_vectors = []
    
    for i, flow in enumerate(all_flows):
        try:
            features = flow.compute_features()
            
            if len(features) != 41:
                print(f"  WARNING: Flow {i} has {len(features)} features (expected 41)")
                continue
            
            feature_vectors.append(features)
            
            # Print sample
            if i < 3:
                print(f"\nFlow {i}: {flow.flow_id}")
                print(f"  Duration: {features[0]:.3f}s")
                print(f"  Forward packets: {features[1]:.0f}")
                print(f"  Backward packets: {features[2]:.0f}")
                print(f"  Total bytes: {features[3] + features[4]:.0f}")
                print(f"  Bytes/sec: {features[14]:.2f}")
                print(f"  Packets/sec: {features[15]:.2f}")
        
        except Exception as e:
            print(f"  ERROR computing features for flow {i}: {e}")
    
    print(f"\nComputed features for {len(feature_vectors)} flows")
    
    # Test normalization
    print("=" * 60)
    print("\nTesting normalization...")
    
    import numpy as np
    
    scaler = OnlineStandardScaler(n_features=41)
    
    # Fit incrementally
    for i, features in enumerate(feature_vectors):
        scaler.partial_fit(np.array(features))
    
    print(f"  Fitted scaler with {scaler.n_samples} samples")
    print(f"  Mean: min={scaler.mean.min():.2f}, max={scaler.mean.max():.2f}")
    print(f"  Std: min={scaler.std.min():.2f}, max={scaler.std.max():.2f}")
    
    # Transform
    X = np.array(feature_vectors)
    X_normalized = scaler.transform(X)
    
    print(f"\nNormalized shape: {X_normalized.shape}")
    print(f"  Mean: {X_normalized.mean():.6f} (should be ~0)")
    print(f"  Std: {X_normalized.std():.6f} (should be ~1)")
    print(f"  Min: {X_normalized.min():.2f}")
    print(f"  Max: {X_normalized.max():.2f}")
    
    # Check for NaN/Inf
    nan_count = np.isnan(X_normalized).sum()
    inf_count = np.isinf(X_normalized).sum()
    
    print(f"\n  NaN values: {nan_count}")
    print(f"  Inf values: {inf_count}")
    
    if nan_count == 0 and inf_count == 0:
        print("\n✓ SUCCESS: All features computed and normalized correctly!")
    else:
        print("\n✗ WARNING: Found NaN or Inf values in normalized features")
    
    print("=" * 60)
    
    # Feature statistics
    print("\nFeature Statistics:")
    print("-" * 60)
    print(f"{'Feature Index':<15} {'Min':<12} {'Max':<12} {'Mean':<12} {'Std':<12}")
    print("-" * 60)
    
    for i in range(min(10, X.shape[1])):  # Show first 10 features
        col = X[:, i]
        print(f"{i:<15} {col.min():<12.2f} {col.max():<12.2f} {col.mean():<12.2f} {col.std():<12.2f}")
    
    if X.shape[1] > 10:
        print(f"... ({X.shape[1] - 10} more features)")
    
    print("=" * 60)
    
    return len(feature_vectors)


if __name__ == '__main__':
    print("CIC-IDS Feature Extraction Test")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        flow_count = test_feature_extraction_from_csv()
        
        elapsed = time.time() - start_time
        
        print(f"\nTest completed in {elapsed:.2f}s")
        
        if flow_count and flow_count >= 20:
            print(f"✓ SUCCESS: Processed {flow_count} flows")
        else:
            print(f"⚠ WARNING: Only processed {flow_count} flows (expected >= 20)")
    
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
