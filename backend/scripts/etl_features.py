"""
ETL Pipeline for NSL-KDD and CIC-IDS-2017/2018 Datasets
Unifies heterogeneous datasets into standardized 41-feature vectors with consistent taxonomy
"""

import os
import sys
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Unified Attack Taxonomy (15+ classes)
UNIFIED_TAXONOMY = {
    'Benign': {
        'severity': 'INFO',
        'category': 'Normal',
        'description': 'Normal benign traffic'
    },
    'DoS': {
        'severity': 'HIGH',
        'category': 'Denial of Service',
        'description': 'Denial of Service attacks'
    },
    'DDoS': {
        'severity': 'CRITICAL',
        'category': 'Distributed Denial of Service',
        'description': 'Distributed DoS attacks'
    },
    'PortScan': {
        'severity': 'MEDIUM',
        'category': 'Reconnaissance',
        'description': 'Port scanning activity'
    },
    'BruteForce': {
        'severity': 'HIGH',
        'category': 'Credential Access',
        'description': 'Brute force password attacks'
    },
    'WebAttack': {
        'severity': 'HIGH',
        'category': 'Web Exploitation',
        'description': 'Web-based attacks (SQLi, XSS, etc.)'
    },
    'Infiltration': {
        'severity': 'CRITICAL',
        'category': 'Lateral Movement',
        'description': 'Network infiltration attempts'
    },
    'Botnet': {
        'severity': 'CRITICAL',
        'category': 'Command and Control',
        'description': 'Botnet C&C traffic'
    },
    'HeartBleed': {
        'severity': 'CRITICAL',
        'category': 'Exploitation',
        'description': 'Heartbleed vulnerability exploitation'
    },
    'U2R': {
        'severity': 'CRITICAL',
        'category': 'Privilege Escalation',
        'description': 'User to Root attacks'
    },
    'R2L': {
        'severity': 'HIGH',
        'category': 'Remote Access',
        'description': 'Remote to Local attacks'
    },
    'Probe': {
        'severity': 'MEDIUM',
        'category': 'Reconnaissance',
        'description': 'Network probing'
    },
    'FTP-Patator': {
        'severity': 'HIGH',
        'category': 'Brute Force',
        'description': 'FTP brute force'
    },
    'SSH-Patator': {
        'severity': 'HIGH',
        'category': 'Brute Force',
        'description': 'SSH brute force'
    },
    'GoldenEye': {
        'severity': 'HIGH',
        'category': 'DoS',
        'description': 'GoldenEye DoS attack'
    },
    'Slowloris': {
        'severity': 'HIGH',
        'category': 'DoS',
        'description': 'Slowloris DoS attack'
    },
    'Hulk': {
        'severity': 'HIGH',
        'category': 'DoS',
        'description': 'Hulk DoS attack'
    },
    'Slowhttptest': {
        'severity': 'HIGH',
        'category': 'DoS',
        'description': 'SlowHTTPTest DoS attack'
    }
}

# CIC-IDS-2017 Column Names (78 features originally)
CIC_COLUMNS = [
    ' Destination Port', ' Flow Duration', ' Total Fwd Packets',
    ' Total Backward Packets', 'Total Length of Fwd Packets',
    ' Total Length of Bwd Packets', ' Fwd Packet Length Max',
    ' Fwd Packet Length Min', ' Fwd Packet Length Mean',
    ' Fwd Packet Length Std', 'Bwd Packet Length Max',
    ' Bwd Packet Length Min', ' Bwd Packet Length Mean',
    ' Bwd Packet Length Std', 'Flow Bytes/s', ' Flow Packets/s',
    ' Flow IAT Mean', ' Flow IAT Std', ' Flow IAT Max', ' Flow IAT Min',
    'Fwd IAT Total', ' Fwd IAT Mean', ' Fwd IAT Std', ' Fwd IAT Max',
    ' Fwd IAT Min', 'Bwd IAT Total', ' Bwd IAT Mean', ' Bwd IAT Std',
    ' Bwd IAT Max', ' Bwd IAT Min', 'Fwd PSH Flags', ' Bwd PSH Flags',
    ' Fwd URG Flags', ' Bwd URG Flags', ' Fwd Header Length',
    ' Bwd Header Length', 'Fwd Packets/s', ' Bwd Packets/s',
    ' Min Packet Length', ' Max Packet Length', ' Packet Length Mean',
    ' Packet Length Std', ' Packet Length Variance', 'FIN Flag Count',
    ' SYN Flag Count', ' RST Flag Count', ' PSH Flag Count',
    ' ACK Flag Count', ' URG Flag Count', ' CWE Flag Count',
    ' ECE Flag Count', ' Down/Up Ratio', ' Average Packet Size',
    ' Avg Fwd Segment Size', ' Avg Bwd Segment Size',
    ' Fwd Header Length.1', 'Fwd Avg Bytes/Bulk', ' Fwd Avg Packets/Bulk',
    ' Fwd Avg Bulk Rate', ' Bwd Avg Bytes/Bulk', ' Bwd Avg Packets/Bulk',
    'Bwd Avg Bulk Rate', 'Subflow Fwd Packets', ' Subflow Fwd Bytes',
    ' Subflow Bwd Packets', ' Subflow Bwd Bytes', 'Init_Win_bytes_forward',
    ' Init_Win_bytes_backward', ' act_data_pkt_fwd', ' min_seg_size_forward',
    'Active Mean', ' Active Std', ' Active Max', ' Active Min',
    'Idle Mean', ' Idle Std', ' Idle Max', ' Idle Min', ' Label'
]


class FeatureExtractor:
    """Extract and standardize 41 features from different dataset formats"""
    
    def __init__(self, feature_version: str = "v1.0-cic41"):
        self.feature_version = feature_version
        self.n_features = 41
        
        # Feature names in order (matching stream/feature_extractor.py)
        self.feature_names = [
            'duration', 'total_fwd_packets', 'total_bwd_packets',
            'total_fwd_bytes', 'total_bwd_bytes',
            'fwd_pkt_len_min', 'fwd_pkt_len_max', 'fwd_pkt_len_mean', 'fwd_pkt_len_std',
            'bwd_pkt_len_min', 'bwd_pkt_len_max', 'bwd_pkt_len_mean', 'bwd_pkt_len_std',
            'flow_pkts_per_sec', 'flow_bytes_per_sec',
            'fwd_iat_mean', 'fwd_iat_std', 'fwd_iat_max', 'fwd_iat_min',
            'bwd_iat_mean', 'bwd_iat_std', 'bwd_iat_max', 'bwd_iat_min',
            'fwd_fin_flags', 'bwd_fin_flags', 'fwd_syn_flags', 'bwd_syn_flags',
            'fwd_rst_flags', 'bwd_rst_flags', 'fwd_psh_flags', 'bwd_psh_flags',
            'fwd_ack_flags', 'bwd_ack_flags', 'fwd_urg_flags', 'bwd_urg_flags',
            'fwd_pkt_rate', 'bwd_pkt_rate', 'fwd_byte_rate', 'bwd_byte_rate',
            'fwd_pkt_ratio', 'fwd_byte_ratio'
        ]
    
    def extract_cic_features(self, row: pd.Series) -> np.ndarray:
        """Extract 41 features from CIC-IDS-2017/2018 row"""
        try:
            features = np.zeros(self.n_features, dtype=np.float32)
            
            # 0: Duration
            features[0] = float(row.get(' Flow Duration', 0))
            
            # 1-2: Packet counts
            features[1] = float(row.get(' Total Fwd Packets', 0))
            features[2] = float(row.get(' Total Backward Packets', 0))
            
            # 3-4: Byte counts
            features[3] = float(row.get('Total Length of Fwd Packets', 0))
            features[4] = float(row.get(' Total Length of Bwd Packets', 0))
            
            # 5-8: Forward packet length stats
            features[5] = float(row.get(' Fwd Packet Length Min', 0))
            features[6] = float(row.get(' Fwd Packet Length Max', 0))
            features[7] = float(row.get(' Fwd Packet Length Mean', 0))
            features[8] = float(row.get(' Fwd Packet Length Std', 0))
            
            # 9-12: Backward packet length stats
            features[9] = float(row.get(' Bwd Packet Length Min', 0))
            features[10] = float(row.get('Bwd Packet Length Max', 0))
            features[11] = float(row.get(' Bwd Packet Length Mean', 0))
            features[12] = float(row.get(' Bwd Packet Length Std', 0))
            
            # 13-14: Flow rates
            features[13] = float(row.get(' Flow Packets/s', 0))
            features[14] = float(row.get('Flow Bytes/s', 0))
            
            # 15-18: Forward IAT stats
            features[15] = float(row.get(' Fwd IAT Mean', 0))
            features[16] = float(row.get(' Fwd IAT Std', 0))
            features[17] = float(row.get(' Fwd IAT Max', 0))
            features[18] = float(row.get(' Fwd IAT Min', 0))
            
            # 19-22: Backward IAT stats
            features[19] = float(row.get(' Bwd IAT Mean', 0))
            features[20] = float(row.get(' Bwd IAT Std', 0))
            features[21] = float(row.get(' Bwd IAT Max', 0))
            features[22] = float(row.get(' Bwd IAT Min', 0))
            
            # 23-34: TCP flags (approximated - CIC doesn't separate fwd/bwd for all flags)
            fin_flags = float(row.get('FIN Flag Count', 0))
            syn_flags = float(row.get(' SYN Flag Count', 0))
            rst_flags = float(row.get(' RST Flag Count', 0))
            psh_flags = float(row.get(' PSH Flag Count', 0))
            ack_flags = float(row.get(' ACK Flag Count', 0))
            urg_flags = float(row.get(' URG Flag Count', 0))
            
            # Split flags proportionally between fwd/bwd based on packet counts
            total_pkts = features[1] + features[2]
            fwd_ratio = features[1] / total_pkts if total_pkts > 0 else 0.5
            
            features[23] = fin_flags * fwd_ratio  # fwd_fin
            features[24] = fin_flags * (1 - fwd_ratio)  # bwd_fin
            features[25] = syn_flags * fwd_ratio  # fwd_syn
            features[26] = syn_flags * (1 - fwd_ratio)  # bwd_syn
            features[27] = rst_flags * fwd_ratio  # fwd_rst
            features[28] = rst_flags * (1 - fwd_ratio)  # bwd_rst
            features[29] = psh_flags * fwd_ratio  # fwd_psh
            features[30] = psh_flags * (1 - fwd_ratio)  # bwd_psh
            features[31] = ack_flags * fwd_ratio  # fwd_ack
            features[32] = ack_flags * (1 - fwd_ratio)  # bwd_ack
            features[33] = urg_flags * fwd_ratio  # fwd_urg
            features[34] = urg_flags * (1 - fwd_ratio)  # bwd_urg
            
            # 35-38: Packet/byte rates (computed from packet counts and duration)
            duration_sec = features[0] / 1e6 if features[0] > 0 else 1e-6  # microseconds to seconds
            features[35] = features[1] / duration_sec  # fwd_pkt_rate
            features[36] = features[2] / duration_sec  # bwd_pkt_rate
            features[37] = features[3] / duration_sec  # fwd_byte_rate
            features[38] = features[4] / duration_sec  # bwd_byte_rate
            
            # 39-40: Ratios
            features[39] = features[1] / total_pkts if total_pkts > 0 else 0.0  # fwd_pkt_ratio
            total_bytes = features[3] + features[4]
            features[40] = features[3] / total_bytes if total_bytes > 0 else 0.0  # fwd_byte_ratio
            
            # Replace inf and nan
            features = np.nan_to_num(features, nan=0.0, posinf=1e10, neginf=-1e10)
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting CIC features: {e}")
            return np.zeros(self.n_features, dtype=np.float32)


class LabelMapper:
    """Map heterogeneous attack labels to unified taxonomy"""
    
    def __init__(self):
        self.taxonomy = UNIFIED_TAXONOMY
        
        # CIC-IDS-2017 label mappings
        self.cic_2017_map = {
            'BENIGN': 'Benign',
            'DoS Hulk': 'Hulk',
            'DoS GoldenEye': 'GoldenEye',
            'DoS slowloris': 'Slowloris',
            'DoS Slowhttptest': 'Slowhttptest',
            'DDoS': 'DDoS',
            'PortScan': 'PortScan',
            'FTP-Patator': 'FTP-Patator',
            'SSH-Patator': 'SSH-Patator',
            'Bot': 'Botnet',
            'Web Attack – Brute Force': 'WebAttack',
            'Web Attack – XSS': 'WebAttack',
            'Web Attack – Sql Injection': 'WebAttack',
            'Infiltration': 'Infiltration',
            'Heartbleed': 'HeartBleed'
        }
        
        # CIC-IDS-2018 label mappings
        self.cic_2018_map = {
            'Benign': 'Benign',
            'DoS attacks-GoldenEye': 'GoldenEye',
            'DoS attacks-Slowloris': 'Slowloris',
            'DoS attacks-Hulk': 'Hulk',
            'DoS attacks-SlowHTTPTest': 'Slowhttptest',
            'DDoS attacks-LOIC-HTTP': 'DDoS',
            'DDoS attacks-HOIC': 'DDoS',
            'Brute Force -Web': 'BruteForce',
            'Brute Force -XSS': 'BruteForce',
            'SQL Injection': 'WebAttack',
            'Infilteration': 'Infiltration',
            'Bot': 'Botnet',
            'FTP-BruteForce': 'FTP-Patator',
            'SSH-Bruteforce': 'SSH-Patator'
        }
        
        # Build reverse mapping (unified -> original labels)
        self.unified_classes = sorted(list(self.taxonomy.keys()))
        self.class_to_idx = {cls: idx for idx, cls in enumerate(self.unified_classes)}
        self.idx_to_class = {idx: cls for cls, idx in self.class_to_idx.items()}
        
        logger.info(f"Initialized label mapper with {len(self.unified_classes)} classes")
    
    def map_cic_label(self, label: str, year: int = 2017) -> str:
        """Map CIC label to unified taxonomy"""
        label = label.strip()
        
        if year == 2017:
            return self.cic_2017_map.get(label, 'Benign')
        elif year == 2018:
            return self.cic_2018_map.get(label, 'Benign')
        else:
            logger.warning(f"Unknown year {year}, defaulting to 2017 mapping")
            return self.cic_2017_map.get(label, 'Benign')
    
    def get_class_idx(self, unified_label: str) -> int:
        """Get class index for unified label"""
        return self.class_to_idx.get(unified_label, 0)  # Default to Benign
    
    def save_taxonomy(self, output_path: Path):
        """Save taxonomy mapping to JSON"""
        taxonomy_data = {
            'classes': self.unified_classes,
            'class_to_idx': self.class_to_idx,
            'idx_to_class': self.idx_to_class,
            'taxonomy': self.taxonomy,
            'num_classes': len(self.unified_classes)
        }
        
        with open(output_path, 'w') as f:
            json.dump(taxonomy_data, f, indent=2)
        
        logger.info(f"Saved taxonomy to {output_path}")


def load_cic_dataset(data_path: Path, year: int, sample_size: Optional[int] = None) -> pd.DataFrame:
    """Load CIC-IDS dataset from CSV files (recursively searches subdirectories)"""
    logger.info(f"Loading CIC-IDS-{year} from {data_path}")
    
    # Recursively find all CSV files
    csv_files = list(data_path.rglob('*.csv'))
    
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_path}")
    
    logger.info(f"Found {len(csv_files)} CSV files")
    
    dfs = []
    for csv_file in csv_files:
        try:
            logger.info(f"  Reading {csv_file.relative_to(data_path)}...")
            df = pd.read_csv(csv_file, encoding='utf-8', low_memory=False, on_bad_lines='skip')
            
            # Sample if requested
            if sample_size and len(df) > sample_size:
                df = df.sample(n=sample_size, random_state=42)
            
            dfs.append(df)
            
        except Exception as e:
            logger.error(f"  Error reading {csv_file}: {e}")
            continue
    
    if not dfs:
        raise ValueError(f"No data loaded from {data_path}")
    
    combined = pd.concat(dfs, ignore_index=True)
    logger.info(f"Loaded {len(combined)} samples from {len(dfs)} files")
    
    return combined


def process_dataset(
    data_path: Path,
    year: int,
    extractor: FeatureExtractor,
    mapper: LabelMapper,
    output_dir: Path,
    sample_size: Optional[int] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """Process dataset: extract features and map labels"""
    
    # Load data
    df = load_cic_dataset(data_path, year, sample_size)
    
    # Extract features
    logger.info("Extracting features...")
    features_list = []
    labels_list = []
    
    for idx, row in df.iterrows():
        if idx % 10000 == 0:
            logger.info(f"  Processed {idx}/{len(df)} samples...")
        
        # Extract features
        features = extractor.extract_cic_features(row)
        features_list.append(features)
        
        # Map label
        original_label = row.get(' Label', 'Benign')
        unified_label = mapper.map_cic_label(str(original_label), year)
        label_idx = mapper.get_class_idx(unified_label)
        labels_list.append(label_idx)
    
    X = np.array(features_list, dtype=np.float32)
    y = np.array(labels_list, dtype=np.int64)
    
    logger.info(f"Extracted {X.shape[0]} samples with {X.shape[1]} features")
    logger.info(f"Class distribution: {np.bincount(y)}")
    
    return X, y


def main():
    """Main ETL pipeline"""
    logger.info("="*60)
    logger.info("Starting ETL Pipeline for Hybrid RL Training")
    logger.info("="*60)
    
    # Paths
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / 'data'
    output_dir = project_root / 'data' / 'processed'
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Initialize components
    extractor = FeatureExtractor(feature_version="v1.0-cic41")
    mapper = LabelMapper()
    
    # Save taxonomy
    taxonomy_path = output_dir / 'taxonomy.json'
    mapper.save_taxonomy(taxonomy_path)
    
    # Save feature specification
    feature_spec = {
        'feature_version': extractor.feature_version,
        'n_features': extractor.n_features,
        'feature_names': extractor.feature_names,
        'feature_hash': hashlib.sha256(
            json.dumps(extractor.feature_names).encode()
        ).hexdigest()[:16]
    }
    
    with open(output_dir / 'feature_spec.json', 'w') as f:
        json.dump(feature_spec, f, indent=2)
    
    logger.info(f"Feature version: {extractor.feature_version}")
    logger.info(f"Feature hash: {feature_spec['feature_hash']}")
    
    # Process CIC-IDS-2017
    cic_2017_path = data_dir / '2017'
    if cic_2017_path.exists():
        logger.info("\nProcessing CIC-IDS-2017...")
        X_2017, y_2017 = process_dataset(
            cic_2017_path, 2017, extractor, mapper, output_dir,
            sample_size=50000  # Limit for faster processing during dev
        )
        
        # Save
        np.save(output_dir / 'X_2017.npy', X_2017)
        np.save(output_dir / 'y_2017.npy', y_2017)
        logger.info(f"Saved CIC-2017: X={X_2017.shape}, y={y_2017.shape}")
    
    # Process CIC-IDS-2018
    cic_2018_path = data_dir / '2018'
    if cic_2018_path.exists():
        logger.info("\nProcessing CIC-IDS-2018...")
        X_2018, y_2018 = process_dataset(
            cic_2018_path, 2018, extractor, mapper, output_dir,
            sample_size=50000
        )
        
        # Save
        np.save(output_dir / 'X_2018.npy', X_2018)
        np.save(output_dir / 'y_2018.npy', y_2018)
        logger.info(f"Saved CIC-2018: X={X_2018.shape}, y={y_2018.shape}")
    
    # Combine and split
    logger.info("\nCombining datasets...")
    X_all = np.concatenate([X_2017, X_2018], axis=0)
    y_all = np.concatenate([y_2017, y_2018], axis=0)
    
    logger.info(f"Total samples: {len(X_all)}")
    logger.info(f"Class distribution: {np.bincount(y_all)}")
    
    # Remove classes with too few samples (need at least 5 for stratified split)
    class_counts = np.bincount(y_all)
    min_samples_per_class = 5  # Reduced from 10 to keep more attack types
    
    logger.info("\nFiltering classes with insufficient samples...")
    valid_mask = np.ones(len(y_all), dtype=bool)
    for class_id in range(len(class_counts)):
        if class_counts[class_id] < min_samples_per_class:
            class_name = mapper.idx_to_class.get(class_id, f"Class_{class_id}")
            logger.warning(f"Removing class {class_id} ({class_name}): only {class_counts[class_id]} samples")
            valid_mask &= (y_all != class_id)
    
    X_all = X_all[valid_mask]
    y_all = y_all[valid_mask]
    
    logger.info(f"Filtered samples: {len(X_all)}")
    logger.info(f"Filtered class distribution: {np.bincount(y_all)}")
    
    # Remap labels to be contiguous (0, 1, 2, ...) after removing classes
    unique_labels = np.unique(y_all)
    label_mapping = {int(old_label): int(new_label) for new_label, old_label in enumerate(unique_labels)}
    y_all_remapped = np.array([label_mapping[label] for label in y_all])
    
    # Update taxonomy to reflect remaining classes
    filtered_classes = [mapper.idx_to_class[i] for i in unique_labels if i in mapper.idx_to_class]
    taxonomy = {
        'classes': filtered_classes,
        'num_classes': len(filtered_classes),
        'label_mapping': label_mapping,
        'original_taxonomy': {
            'classes': mapper.unified_classes,
            'class_to_idx': mapper.class_to_idx,
            'taxonomy_details': UNIFIED_TAXONOMY
        }
    }
    
    logger.info(f"Remaining classes ({len(filtered_classes)}): {filtered_classes}")
    
    # Stratified split: 70% train, 15% val, 15% test
    logger.info("\nSplitting dataset...")
    try:
        X_train, X_temp, y_train, y_temp = train_test_split(
            X_all, y_all_remapped, test_size=0.30, random_state=42, stratify=y_all_remapped
        )
        
        X_val, X_test, y_val, y_test = train_test_split(
            X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
        )
    except ValueError as e:
        logger.warning(f"Stratified split failed: {e}. Using random split instead.")
        X_train, X_temp, y_train, y_temp = train_test_split(
            X_all, y_all_remapped, test_size=0.30, random_state=42
        )
        
        X_val, X_test, y_val, y_test = train_test_split(
            X_temp, y_temp, test_size=0.50, random_state=42
        )
    
    logger.info(f"Train: {len(X_train)} samples")
    logger.info(f"Val:   {len(X_val)} samples")
    logger.info(f"Test:  {len(X_test)} samples")
    
    # Normalize features
    logger.info("\nNormalizing features...")
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)
    X_test = scaler.transform(X_test)
    
    # Save splits
    np.save(output_dir / 'X_train.npy', X_train.astype(np.float32))
    np.save(output_dir / 'y_train.npy', y_train.astype(np.int64))
    np.save(output_dir / 'X_val.npy', X_val.astype(np.float32))
    np.save(output_dir / 'y_val.npy', y_val.astype(np.int64))
    np.save(output_dir / 'X_test.npy', X_test.astype(np.float32))
    np.save(output_dir / 'y_test.npy', y_test.astype(np.int64))
    
    # Save scaler
    import pickle
    with open(output_dir / 'scaler.pkl', 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save taxonomy
    with open(output_dir / 'taxonomy.json', 'w') as f:
        json.dump(taxonomy, f, indent=2)
    
    # Save metadata
    metadata = {
        'created_at': datetime.now().isoformat(),
        'feature_version': extractor.feature_version,
        'num_classes': taxonomy['num_classes'],
        'num_features': extractor.n_features,
        'train_samples': int(len(X_train)),
        'val_samples': int(len(X_val)),
        'test_samples': int(len(X_test)),
        'train_class_dist': {
            int(k): int(v) for k, v in enumerate(np.bincount(y_train))
        },
        'val_class_dist': {
            int(k): int(v) for k, v in enumerate(np.bincount(y_val))
        },
        'test_class_dist': {
            int(k): int(v) for k, v in enumerate(np.bincount(y_test))
        }
    }
    
    with open(output_dir / 'metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info("="*60)
    logger.info("ETL Pipeline Complete!")
    logger.info(f"Output directory: {output_dir}")
    logger.info("="*60)


if __name__ == '__main__':
    main()
