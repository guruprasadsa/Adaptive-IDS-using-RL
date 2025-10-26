"""
Alerting Service
Consumes predictions from Kafka, classifies severity, persists to database,
and dispatches to configured external integrations (syslog, SIEM, email).
"""
import os
import sys
import json
import logging
import signal
import time
import uuid
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from collections import defaultdict, deque
from threading import Lock

import yaml
import psycopg2
from psycopg2.extras import execute_batch
from confluent_kafka import Consumer, Producer, KafkaError

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alerting.dlq import DLQProducer, RetryPolicy, with_retry
from alerting.integrations import (
    SyslogClient,
    SplunkHECClient,
    QRadarClient,
    ElasticSIEMClient,
    EmailClient
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Config:
    """Service configuration from environment and config file."""
    
    def __init__(self, config_path: str = None):
        """
        Load configuration from YAML file and environment variables.
        
        Args:
            config_path: Path to config.yaml file
        """
        # Load YAML config
        if config_path is None:
            config_path = os.path.join(
                Path(__file__).parent,
                'config.yaml'
            )
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Expand environment variables in config
        self.config = self._expand_env_vars(config_data)
        
        # Kafka
        self.KAFKA_BROKERS = os.getenv('KAFKA_BROKERS', 'localhost:9092')
        self.PRED_TOPIC = os.getenv('PRED_TOPIC', 'predictions')
        self.CONSUMER_GROUP = os.getenv('ALERT_CONSUMER_GROUP', 'alerting-service')
        # Alerts Kafka topic for SSE streaming
        self.ALERTS_TOPIC = os.getenv('ALERTS_TOPIC', 'alerts')
        
        # Database
        self.PG_DSN = os.getenv(
            'PG_DSN',
            'host=localhost port=55432 dbname=adaptive_ids user=adaptive_ids password=adaptive_ids_password'
        )
        
        logger.info("Configuration loaded successfully")
    
    def _expand_env_vars(self, config: Any) -> Any:
        """Recursively expand environment variables in config."""
        if isinstance(config, dict):
            return {k: self._expand_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._expand_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith('${') and config.endswith('}'):
            # Extract env var and default: ${VAR:default}
            match = re.match(r'\$\{([^:}]+)(?::([^}]*))?\}', config)
            if match:
                var_name, default = match.groups()
                return os.getenv(var_name, default or '')
        return config
    
    def get(self, *keys, default=None):
        """Get nested config value by keys."""
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value


class SeverityClassifier:
    """Maps attack classes to severity levels."""
    
    def __init__(self, config: Config):
        """
        Initialize severity classifier.
        
        Args:
            config: Service configuration
        """
        self.severity_mapping = config.get('severity_mapping', default={})
        self.confidence_thresholds = config.get('confidence_thresholds', default={})
        self.default_severity = self.severity_mapping.get('_default', 'MEDIUM')
        
        logger.info(f"Severity classifier initialized with {len(self.severity_mapping)} mappings")
    
    def classify(self, class_name: str, confidence: float) -> Optional[str]:
        """
        Classify severity based on class name and confidence.
        
        Args:
            class_name: Attack class name
            confidence: Prediction confidence
        
        Returns:
            Severity level or None if below threshold
        """
        # Get base severity from mapping
        severity = self.severity_mapping.get(class_name, self.default_severity)
        
        # Check confidence threshold
        threshold = self.confidence_thresholds.get(severity, 0.5)
        if confidence < threshold:
            logger.debug(
                f"Alert suppressed: confidence {confidence:.2f} below threshold {threshold:.2f} for {severity}"
            )
            return None
        
        return severity


class AlertFilter:
    """Filters and deduplicates alerts."""
    
    def __init__(self, config: Config):
        """
        Initialize alert filter.
        
        Args:
            config: Service configuration
        """
        self.suppress_info = config.get('alert_filtering', 'suppress_info', default=True)
        self.suppress_classes = set(config.get('alert_filtering', 'suppress_classes', default=[]))
        self.min_confidence = config.get('alert_filtering', 'min_confidence', default=0.5)
        
        # Deduplication
        self.dedup_window = config.get('alert_filtering', 'deduplication_window', default=300)
        self.dedup_keys = config.get('alert_filtering', 'deduplication_keys', default=[])
        self.seen_alerts: Dict[str, float] = {}
        self._lock = Lock()
        
        logger.info(f"Alert filter initialized: suppress_info={self.suppress_info}")
    
    def should_alert(self, alert: Dict[str, Any]) -> bool:
        """
        Check if alert should be dispatched.
        
        Args:
            alert: Alert dictionary
        
        Returns:
            True if should dispatch, False if should suppress
        """
        # Check confidence threshold
        if alert.get('confidence', 0.0) < self.min_confidence:
            return False
        
        # Check severity suppression
        if self.suppress_info and alert.get('severity') == 'INFO':
            return False
        
        # Check class suppression
        if alert.get('class_name') in self.suppress_classes:
            return False
        
        # Check deduplication
        if self.dedup_keys:
            dedup_key = self._get_dedup_key(alert)
            with self._lock:
                now = time.time()
                
                # Clean old entries
                self.seen_alerts = {
                    k: v for k, v in self.seen_alerts.items()
                    if now - v < self.dedup_window
                }
                
                # Check if duplicate
                if dedup_key in self.seen_alerts:
                    logger.debug(f"Duplicate alert suppressed: {dedup_key}")
                    return False
                
                # Record alert
                self.seen_alerts[dedup_key] = now
        
        return True
    
    def _get_dedup_key(self, alert: Dict[str, Any]) -> str:
        """Generate deduplication key from alert."""
        key_parts = [str(alert.get(key, '')) for key in self.dedup_keys]
        return '|'.join(key_parts)


class DatabaseWriter:
    """Writes alerts to PostgreSQL database."""
    
    def __init__(self, dsn: str, batch_size: int = 10, batch_timeout: float = 0.5):
        """
        Initialize database writer.
        
        Args:
            dsn: PostgreSQL connection string
            batch_size: Batch size for bulk inserts
            batch_timeout: Batch timeout in seconds
        """
        self.dsn = dsn
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        
        # Batch buffer
        self.buffer: List[Dict[str, Any]] = []
        self.last_flush = time.time()
        self._lock = Lock()
        
        # Test connection
        self._test_connection()
        
        logger.info(f"Database writer initialized: batch_size={batch_size}")
    
    def _test_connection(self):
        """Test database connection."""
        try:
            conn = psycopg2.connect(self.dsn)
            conn.close()
            logger.info("Database connection successful")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def write(self, alert: Dict[str, Any]):
        """
        Write alert to database (buffered).
        
        Args:
            alert: Alert dictionary
        """
        with self._lock:
            self.buffer.append(alert)
            
            # Flush if batch size reached or timeout expired
            if (len(self.buffer) >= self.batch_size or
                time.time() - self.last_flush >= self.batch_timeout):
                self._flush()
    
    def _flush(self):
        """Flush buffer to database."""
        if not self.buffer:
            return
        
        try:
            conn = psycopg2.connect(self.dsn)
            cursor = conn.cursor()
            
            # Prepare batch insert
            query = """
                INSERT INTO alerts (
                    alert_id, flow_id, timestamp,
                    class_idx, class_name, confidence, severity,
                    src_ip, dst_ip, src_port, dst_port, protocol,
                    model_version, feature_version,
                    status, raw_payload,
                    src_geo, dst_geo, src_reputation, dst_reputation, tags,
                    destinations, dispatch_status,
                    priority, description, source, alert_type
                ) VALUES (
                    %(alert_id)s, %(flow_id)s, to_timestamp(%(timestamp)s / 1000.0),
                    %(class_idx)s, %(class_name)s, %(confidence)s, %(severity)s,
                    %(src_ip)s, %(dst_ip)s, %(src_port)s, %(dst_port)s, %(protocol)s,
                    %(model_version)s, %(feature_version)s,
                    %(status)s, %(raw_payload)s,
                    %(src_geo)s, %(dst_geo)s, %(src_reputation)s, %(dst_reputation)s, %(tags)s,
                    %(destinations)s, %(dispatch_status)s,
                    %(priority)s, %(description)s, %(source)s, %(alert_type)s
                )
            """
            
            # Convert dict fields to JSON for each alert
            prepared_buffer = []
            for alert in self.buffer:
                prepared_alert = alert.copy()
                prepared_alert['raw_payload'] = json.dumps(alert.get('raw_payload', {}))
                prepared_alert['dispatch_status'] = json.dumps(alert.get('dispatch_status', {}))
                prepared_buffer.append(prepared_alert)
            
            # Execute batch
            execute_batch(cursor, query, prepared_buffer)
            conn.commit()
            
            logger.info(f"Wrote {len(self.buffer)} alerts to database")
            
            cursor.close()
            conn.close()
            
            # Clear buffer
            self.buffer = []
            self.last_flush = time.time()
        
        except Exception as e:
            logger.error(f"Failed to write alerts to database: {e}")
            # Don't clear buffer on error - will retry next flush
    
    def close(self):
        """Flush and close writer."""
        with self._lock:
            self._flush()


class AlertDispatcher:
    """Dispatches alerts to configured integrations."""
    
    def __init__(self, config: Config, dlq_producer: DLQProducer):
        """
        Initialize alert dispatcher.
        
        Args:
            config: Service configuration
            dlq_producer: Dead letter queue producer
        """
        self.config = config
        self.dlq_producer = dlq_producer
        self.retry_policy = RetryPolicy(
            max_attempts=config.get('dlq', 'retry', 'max_attempts', default=3),
            initial_delay_ms=config.get('dlq', 'retry', 'initial_delay_ms', default=1000),
            max_delay_ms=config.get('dlq', 'retry', 'max_delay_ms', default=60000),
            backoff_multiplier=config.get('dlq', 'retry', 'backoff_multiplier', default=2.0)
        )
        
        # Initialize integrations
        self.integrations = self._init_integrations()
        
        logger.info(f"Alert dispatcher initialized with {len(self.integrations)} integrations")
    
    def _init_integrations(self) -> Dict[str, Any]:
        """Initialize enabled integrations."""
        integrations = {}
        
        # Syslog
        if self.config.get('integrations', 'syslog', 'enabled', default=False):
            try:
                integrations['syslog'] = SyslogClient(
                    host=self.config.get('integrations', 'syslog', 'host', default='localhost'),
                    port=self.config.get('integrations', 'syslog', 'port', default=6514),
                    protocol=self.config.get('integrations', 'syslog', 'protocol', default='TLS'),
                    facility=self.config.get('integrations', 'syslog', 'facility', default=16),
                    tls_config=self.config.get('integrations', 'syslog', 'tls', default={}),
                    pool_size=self.config.get('integrations', 'syslog', 'connection', 'pool_size', default=5),
                    timeout=self.config.get('integrations', 'syslog', 'connection', 'timeout_ms', default=5000) / 1000.0,
                    max_retries=self.config.get('integrations', 'syslog', 'connection', 'max_retries', default=3)
                )
                logger.info("Syslog integration enabled")
            except Exception as e:
                logger.error(f"Failed to initialize syslog integration: {e}")
        
        # Splunk
        if self.config.get('integrations', 'splunk', 'enabled', default=False):
            try:
                integrations['splunk'] = SplunkHECClient(
                    url=self.config.get('integrations', 'splunk', 'url', default=''),
                    token=self.config.get('integrations', 'splunk', 'token', default=''),
                    index=self.config.get('integrations', 'splunk', 'index', default='ids_alerts'),
                    verify_ssl=self.config.get('integrations', 'splunk', 'verify_ssl', default=True),
                    batch_size=self.config.get('integrations', 'splunk', 'batch_size', default=10)
                )
                logger.info("Splunk integration enabled")
            except Exception as e:
                logger.error(f"Failed to initialize Splunk integration: {e}")
        
        # QRadar
        if self.config.get('integrations', 'qradar', 'enabled', default=False):
            try:
                integrations['qradar'] = QRadarClient(
                    url=self.config.get('integrations', 'qradar', 'url', default=''),
                    api_key=self.config.get('integrations', 'qradar', 'api_key', default=''),
                    verify_ssl=self.config.get('integrations', 'qradar', 'verify_ssl', default=True)
                )
                logger.info("QRadar integration enabled")
            except Exception as e:
                logger.error(f"Failed to initialize QRadar integration: {e}")
        
        # Elastic
        if self.config.get('integrations', 'elastic', 'enabled', default=False):
            try:
                integrations['elastic'] = ElasticSIEMClient(
                    url=self.config.get('integrations', 'elastic', 'url', default=''),
                    api_key=self.config.get('integrations', 'elastic', 'api_key', default=''),
                    index=self.config.get('integrations', 'elastic', 'index', default='ids-alerts'),
                    verify_ssl=self.config.get('integrations', 'elastic', 'verify_ssl', default=True),
                    batch_size=self.config.get('integrations', 'elastic', 'batch_size', default=20)
                )
                logger.info("Elastic integration enabled")
            except Exception as e:
                logger.error(f"Failed to initialize Elastic integration: {e}")
        
        # Email
        if self.config.get('integrations', 'email', 'enabled', default=False):
            try:
                integrations['email'] = EmailClient(
                    smtp_host=self.config.get('integrations', 'email', 'smtp_host', default='localhost'),
                    smtp_port=self.config.get('integrations', 'email', 'smtp_port', default=587),
                    smtp_tls=self.config.get('integrations', 'email', 'smtp_tls', default=True),
                    smtp_user=self.config.get('integrations', 'email', 'smtp_user', default=None),
                    smtp_password=self.config.get('integrations', 'email', 'smtp_password', default=None),
                    from_address=self.config.get('integrations', 'email', 'from_address', default='ids-alerts@example.com'),
                    to_addresses=self.config.get('integrations', 'email', 'to_addresses', default='security-team@example.com'),
                    cc_addresses=self.config.get('integrations', 'email', 'cc_addresses', default=None),
                    subject_template=self.config.get('integrations', 'email', 'subject_template', default=''),
                    max_per_minute=self.config.get('integrations', 'email', 'rate_limit', 'max_per_hour', default=10) // 60,
                    max_per_hour=self.config.get('integrations', 'email', 'rate_limit', 'max_per_hour', default=10),
                    max_per_day=self.config.get('integrations', 'email', 'rate_limit', 'max_per_day', default=50)
                )
                logger.info("Email integration enabled")
            except Exception as e:
                logger.error(f"Failed to initialize email integration: {e}")
        
        return integrations
    
    def dispatch(self, alert: Dict[str, Any]):
        """
        Dispatch alert to all applicable integrations.
        
        Args:
            alert: Alert dictionary
        """
        alert_severity = alert.get('severity', 'MEDIUM')
        destinations = []
        dispatch_status = {}
        
        for name, client in self.integrations.items():
            # Check severity threshold
            min_severity = self.config.get('integrations', name, 'min_severity', default='INFO')
            if not self._meets_severity_threshold(alert_severity, min_severity):
                continue
            
            # Dispatch with retry
            success = with_retry(
                func=lambda: client.send(alert),
                retry_policy=self.retry_policy,
                dlq_producer=self.dlq_producer,
                destination=name,
                message=alert
            )
            
            destinations.append(name)
            dispatch_status[name] = 'success' if success else 'failed'
        
        # Update alert with dispatch info
        alert['destinations'] = destinations
        alert['dispatch_status'] = dispatch_status
    
    def _meets_severity_threshold(self, severity: str, min_severity: str) -> bool:
        """Check if severity meets minimum threshold."""
        severity_order = ['INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        try:
            return severity_order.index(severity) >= severity_order.index(min_severity)
        except ValueError:
            return True
    
    def close(self):
        """Close all integrations."""
        for name, client in self.integrations.items():
            try:
                if hasattr(client, 'close'):
                    client.close()
            except Exception as e:
                logger.error(f"Error closing {name} integration: {e}")


class AlertingService:
    """Main alerting service."""
    
    def __init__(self, config_path: str = None):
        """
        Initialize alerting service.
        
        Args:
            config_path: Path to config.yaml
        """
        self.config = Config(config_path)
        self.running = False
        
        # Initialize components
        self.consumer = self._create_consumer()
        self.db_writer = DatabaseWriter(
            self.config.PG_DSN,
            batch_size=self.config.get('integrations', 'database', 'batch_size', default=10),
            batch_timeout=self.config.get('integrations', 'database', 'batch_timeout_ms', default=500) / 1000.0
        )
        self.dlq_producer = DLQProducer(
            self.config.KAFKA_BROKERS,
            dlq_topic=self.config.get('dlq', 'topic', default='alerts.dlq')
        )
        self.severity_classifier = SeverityClassifier(self.config)
        self.alert_filter = AlertFilter(self.config)
        self.dispatcher = AlertDispatcher(self.config, self.dlq_producer)
        # Initialize alerts producer for SSE topic
        self.alerts_topic = self.config.ALERTS_TOPIC
        try:
            self.alerts_producer = Producer({
                'bootstrap.servers': self.config.KAFKA_BROKERS,
                'compression.type': 'lz4',
                'linger.ms': 10,
                'batch.size': 16384,
                'enable.idempotence': True,
            })
            logger.info(f"Kafka alerts producer initialized: topic={self.alerts_topic}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka alerts producer: {e}")
            self.alerts_producer = None
        
        # Metrics
        self.metrics = {
            'predictions_consumed': 0,
            'alerts_created': 0,
            'alerts_suppressed': 0,
            'alerts_dispatched': 0,
            'errors': 0
        }
        
        logger.info("Alerting service initialized")
    
    def _create_consumer(self) -> Consumer:
        """Create Kafka consumer."""
        consumer_config = {
            'bootstrap.servers': self.config.KAFKA_BROKERS,
            'group.id': self.config.CONSUMER_GROUP,
            'auto.offset.reset': 'latest',
            'enable.auto.commit': True,
            'max.poll.interval.ms': 300000,
        }
        
        consumer = Consumer(consumer_config)
        consumer.subscribe([self.config.PRED_TOPIC])
        
        logger.info(f"Kafka consumer created: topic={self.config.PRED_TOPIC}")
        return consumer
    
    def process_prediction(self, prediction: Dict[str, Any]):
        """
        Process prediction and create alert if needed.
        
        Args:
            prediction: Prediction message from Kafka
        """
        try:
            self.metrics['predictions_consumed'] += 1
            
            # Classify severity
            severity = self.severity_classifier.classify(
                prediction.get('class_name', ''),
                prediction.get('confidence', 0.0)
            )
            
            if severity is None:
                self.metrics['alerts_suppressed'] += 1
                return
            
            # Create alert
            class_name = prediction.get('class_name', 'Unknown')
            src_ip = prediction.get('src_ip', 'unknown')
            dst_ip = prediction.get('dst_ip', 'unknown')
            src_port = prediction.get('src_port', 0)
            dst_port = prediction.get('dst_port', 0)
            protocol = prediction.get('protocol', 'unknown')
            confidence = prediction.get('confidence', 0.0)
            
            # Generate detailed alert description
            description = self._generate_alert_description(
                class_name, src_ip, dst_ip, src_port, dst_port, protocol, confidence, severity
            )
            
            # Generate actionable tags
            tags = self._generate_alert_tags(class_name, severity, protocol)
            
            alert = {
                'alert_id': str(uuid.uuid4()),
                'flow_id': prediction.get('flow_id', ''),
                'timestamp': prediction.get('timestamp', int(time.time() * 1000)),
                'class_idx': prediction.get('class_idx', 0),
                'class_name': class_name,
                'confidence': confidence,
                'severity': severity,
                'src_ip': src_ip,
                'dst_ip': dst_ip,
                'src_port': src_port,
                'dst_port': dst_port,
                'protocol': protocol,
                'model_version': prediction.get('model_version', ''),
                'feature_version': prediction.get('feature_version', ''),
                'status': 'NEW',
                'raw_payload': prediction,
                'src_geo': None,
                'dst_geo': None,
                'src_reputation': None,
                'dst_reputation': None,
                'tags': tags,
                'destinations': [],
                'dispatch_status': {},
                # Legacy fields for backward compatibility
                'priority': severity,  # Map severity to priority
                'description': description,
                'source': 'adaptive-ids-ml-model',
                'alert_type': class_name
            }
            
            # Apply filters
            if not self.alert_filter.should_alert(alert):
                self.metrics['alerts_suppressed'] += 1
                return
            
            self.metrics['alerts_created'] += 1
            
            # Dispatch to integrations
            self.dispatcher.dispatch(alert)
            self.metrics['alerts_dispatched'] += 1
            
            # Write to database
            self.db_writer.write(alert)

            # Publish alert to Kafka alerts topic for SSE consumers
            try:
                if self.alerts_producer and self.alerts_topic:
                    self.alerts_producer.produce(
                        self.alerts_topic,
                        value=json.dumps(alert).encode('utf-8')
                    )
                    # Poll to trigger delivery callbacks
                    self.alerts_producer.poll(0)
            except Exception as e:
                logger.error(f"Failed to publish alert to Kafka topic '{self.alerts_topic}': {e}")
            
            logger.info(
                f"Alert created: {alert['alert_id']} | {alert['severity']} | "
                f"{alert['class_name']} | {alert['src_ip']} -> {alert['dst_ip']}"
            )
        
        except Exception as e:
            self.metrics['errors'] += 1
            logger.error(f"Error processing prediction: {e}", exc_info=True)
    
    def _generate_alert_description(self, class_name: str, src_ip: str, dst_ip: str,
                                   src_port: int, dst_port: int, protocol: str,
                                   confidence: float, severity: str) -> str:
        """
        Generate detailed, actionable alert description.
        
        Args:
            class_name: Attack type
            src_ip, dst_ip: Source and destination IPs
            src_port, dst_port: Source and destination ports
            protocol: Network protocol
            confidence: Model confidence score
            severity: Alert severity level
        
        Returns:
            Detailed alert description
        """
        # Attack-specific descriptions
        attack_descriptions = {
            'DDoS': f'Distributed Denial of Service attack detected. Source {src_ip} is generating excessive traffic to {dst_ip}:{dst_port} ({protocol}). This may impact service availability.',
            'Botnet': f'Botnet activity detected from {src_ip}. The system may be compromised and part of a command-and-control network communicating with {dst_ip}:{dst_port}.',
            'PortScan': f'Port scanning activity detected from {src_ip} targeting {dst_ip}. Attacker is probing {protocol} port {dst_port} for vulnerabilities.',
            'Hulk': f'HTTP Flood (Hulk) attack detected. Source {src_ip} is overwhelming {dst_ip} with HTTP requests on port {dst_port}.',
            'GoldenEye': f'GoldenEye HTTP DoS attack detected from {src_ip} targeting {dst_ip}:{dst_port}. Server resources may be exhausted.',
            'Slowloris': f'Slowloris attack detected. Source {src_ip} is keeping connections open to {dst_ip}:{dst_port} to exhaust server resources.',
            'Slowhttptest': f'Slow HTTP attack (slowhttptest) detected from {src_ip}. Gradual resource exhaustion attempt against {dst_ip}:{dst_port}.',
            'FTP-Patator': f'FTP brute force attack detected from {src_ip} targeting {dst_ip}. Multiple login attempts observed on FTP port {dst_port}.',
            'SSH-Patator': f'SSH brute force attack detected from {src_ip} targeting {dst_ip}. Automated password guessing on SSH port {dst_port}.',
            'Benign': f'Normal traffic pattern observed from {src_ip} to {dst_ip}:{dst_port} ({protocol}). No malicious activity detected.',
        }
        
        base_desc = attack_descriptions.get(
            class_name,
            f'Suspicious {class_name} activity detected from {src_ip} to {dst_ip}:{dst_port} via {protocol}.'
        )
        
        # Add confidence and severity context
        confidence_pct = int(confidence * 100)
        return f'{base_desc} Confidence: {confidence_pct}%, Severity: {severity}'
    
    def _generate_alert_tags(self, class_name: str, severity: str, protocol: str) -> List[str]:
        """
        Generate relevant tags for alert categorization.
        
        Args:
            class_name: Attack type
            severity: Alert severity
            protocol: Network protocol
        
        Returns:
            List of relevant tags
        """
        tags = [class_name.lower(), severity.lower(), protocol.lower()]
        
        # Add category tags
        category_mapping = {
            'DDoS': ['dos', 'availability', 'volumetric'],
            'Botnet': ['malware', 'c2', 'compromised'],
            'PortScan': ['reconnaissance', 'scanning', 'enumeration'],
            'Hulk': ['dos', 'http-flood', 'web-attack'],
            'GoldenEye': ['dos', 'http-attack', 'web-attack'],
            'Slowloris': ['dos', 'slow-attack', 'web-attack'],
            'Slowhttptest': ['dos', 'slow-attack', 'web-attack'],
            'FTP-Patator': ['brute-force', 'credential-attack', 'authentication'],
            'SSH-Patator': ['brute-force', 'credential-attack', 'authentication'],
            'Benign': ['normal', 'baseline']
        }
        
        tags.extend(category_mapping.get(class_name, ['unknown']))
        
        return list(set(tags))  # Remove duplicates
    
    def run(self):
        """Run alerting service."""
        self.running = True
        logger.info("Alerting service started")
        
        try:
            while self.running:
                msg = self.consumer.poll(timeout=1.0)
                
                if msg is None:
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Kafka error: {msg.error()}")
                        continue
                
                # Deserialize and process
                try:
                    prediction = json.loads(msg.value().decode('utf-8'))
                    self.process_prediction(prediction)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode message: {e}")
                    self.metrics['errors'] += 1
        
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Shutdown service gracefully."""
        logger.info("Shutting down alerting service")
        self.running = False
        
        try:
            self.consumer.close()
            self.db_writer.close()
            self.dispatcher.close()
            self.dlq_producer.close()
            if getattr(self, 'alerts_producer', None):
                try:
                    self.alerts_producer.flush(5)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        
        # Log metrics
        logger.info(f"Final metrics: {self.metrics}")
        logger.info("Alerting service stopped")


def main():
    """Main entry point."""
    config_path = os.getenv('ALERT_CONFIG_PATH')
    
    service = AlertingService(config_path)
    
    # Handle signals
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        service.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run service
    service.run()


if __name__ == '__main__':
    main()
