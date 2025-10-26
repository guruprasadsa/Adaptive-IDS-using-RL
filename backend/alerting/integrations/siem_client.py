"""
SIEM Integration Clients
Adapters for Splunk HEC, QRadar REST API, and Elastic SIEM.
"""
import json
import logging
import time
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class SIEMClientBase(ABC):
    """Base class for SIEM integrations."""
    
    def __init__(
        self,
        url: str,
        verify_ssl: bool = True,
        timeout: float = 5.0,
        max_retries: int = 3
    ):
        """
        Initialize SIEM client.
        
        Args:
            url: SIEM endpoint URL
            verify_ssl: Verify SSL certificates
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.url = url
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Create session with retry logic
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    @abstractmethod
    def send(self, alert: Dict[str, Any]) -> bool:
        """
        Send alert to SIEM.
        
        Args:
            alert: Alert dictionary
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def send_batch(self, alerts: List[Dict[str, Any]]) -> bool:
        """
        Send batch of alerts to SIEM.
        
        Args:
            alerts: List of alert dictionaries
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    def close(self):
        """Close session."""
        self.session.close()


class SplunkHECClient(SIEMClientBase):
    """
    Splunk HTTP Event Collector (HEC) client.
    Sends alerts to Splunk via HEC endpoint.
    """
    
    def __init__(
        self,
        url: str,
        token: str,
        index: str = 'main',
        source: str = 'adaptive_ids',
        sourcetype: str = 'ids:alert',
        verify_ssl: bool = True,
        timeout: float = 5.0,
        max_retries: int = 3,
        batch_size: int = 10
    ):
        """
        Initialize Splunk HEC client.
        
        Args:
            url: Splunk HEC endpoint URL
            token: HEC token
            index: Splunk index
            source: Event source
            sourcetype: Event sourcetype
            verify_ssl: Verify SSL certificates
            timeout: Request timeout
            max_retries: Maximum retries
            batch_size: Batch size for bulk sends
        """
        super().__init__(url, verify_ssl, timeout, max_retries)
        self.token = token
        self.index = index
        self.source = source
        self.sourcetype = sourcetype
        self.batch_size = batch_size
        
        # Set authorization header
        self.session.headers.update({
            'Authorization': f'Splunk {token}',
            'Content-Type': 'application/json'
        })
        
        logger.info(f"Splunk HEC client initialized: {url}, index={index}")
    
    def _format_event(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format alert as Splunk HEC event.
        
        Args:
            alert: Alert dictionary
        
        Returns:
            HEC event dictionary
        """
        return {
            'time': alert.get('timestamp', time.time()) / 1000.0,  # Convert ms to seconds
            'index': self.index,
            'source': self.source,
            'sourcetype': self.sourcetype,
            'event': {
                'alert_id': alert.get('alert_id'),
                'flow_id': alert.get('flow_id'),
                'severity': alert.get('severity'),
                'class_name': alert.get('class_name'),
                'class_idx': alert.get('class_idx'),
                'confidence': alert.get('confidence'),
                'src_ip': alert.get('src_ip'),
                'dst_ip': alert.get('dst_ip'),
                'src_port': alert.get('src_port'),
                'dst_port': alert.get('dst_port'),
                'protocol': alert.get('protocol'),
                'model_version': alert.get('model_version'),
                'feature_version': alert.get('feature_version'),
                'status': alert.get('status'),
                'tags': alert.get('tags', []),
            }
        }
    
    def send(self, alert: Dict[str, Any]) -> bool:
        """Send single alert to Splunk HEC."""
        try:
            event = self._format_event(alert)
            
            response = self.session.post(
                self.url,
                json=event,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            logger.debug(f"Sent alert {alert.get('alert_id')} to Splunk HEC")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send alert to Splunk HEC: {e}")
            return False
    
    def send_batch(self, alerts: List[Dict[str, Any]]) -> bool:
        """Send batch of alerts to Splunk HEC."""
        if not alerts:
            return True
        
        try:
            # Format all events
            events = [self._format_event(alert) for alert in alerts]
            
            # Splunk HEC expects newline-delimited JSON for batch
            payload = '\n'.join([json.dumps(event) for event in events])
            
            response = self.session.post(
                self.url,
                data=payload,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            logger.info(f"Sent batch of {len(alerts)} alerts to Splunk HEC")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send batch to Splunk HEC: {e}")
            return False


class QRadarClient(SIEMClientBase):
    """
    IBM QRadar SIEM REST API client.
    Creates offenses in QRadar from alerts.
    """
    
    def __init__(
        self,
        url: str,
        api_key: str,
        verify_ssl: bool = True,
        timeout: float = 5.0,
        max_retries: int = 3
    ):
        """
        Initialize QRadar client.
        
        Args:
            url: QRadar API base URL
            api_key: QRadar API key
            verify_ssl: Verify SSL certificates
            timeout: Request timeout
            max_retries: Maximum retries
        """
        super().__init__(url, verify_ssl, timeout, max_retries)
        self.api_key = api_key
        
        # Set authorization header
        self.session.headers.update({
            'SEC': api_key,
            'Content-Type': 'application/json',
            'Version': '14.0'  # API version
        })
        
        logger.info(f"QRadar client initialized: {url}")
    
    def _format_offense(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format alert as QRadar offense.
        
        Args:
            alert: Alert dictionary
        
        Returns:
            Offense dictionary
        """
        # Map severity to QRadar severity (1-10)
        severity_map = {
            'INFO': 2,
            'LOW': 4,
            'MEDIUM': 6,
            'HIGH': 8,
            'CRITICAL': 10
        }
        
        return {
            'offense_type': 'Custom Offense',
            'severity': severity_map.get(alert.get('severity'), 5),
            'description': (
                f"{alert.get('class_name')} detected from "
                f"{alert.get('src_ip')} to {alert.get('dst_ip')}"
            ),
            'source_ip': alert.get('src_ip'),
            'destination_ip': alert.get('dst_ip'),
            'username': None,
            'credibility': int(alert.get('confidence', 0.5) * 10),  # Scale to 0-10
            'relevance': 5,
            'magnitude': severity_map.get(alert.get('severity'), 5),
        }
    
    def send(self, alert: Dict[str, Any]) -> bool:
        """Send alert to QRadar as offense."""
        try:
            offense = self._format_offense(alert)
            
            # Create offense
            url = urljoin(self.url, '/api/siem/offenses')
            response = self.session.post(
                url,
                json=offense,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            logger.debug(f"Sent alert {alert.get('alert_id')} to QRadar")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send alert to QRadar: {e}")
            return False
    
    def send_batch(self, alerts: List[Dict[str, Any]]) -> bool:
        """Send batch of alerts to QRadar."""
        # QRadar doesn't have native batch API, send individually
        success_count = 0
        for alert in alerts:
            if self.send(alert):
                success_count += 1
        
        logger.info(f"Sent {success_count}/{len(alerts)} alerts to QRadar")
        return success_count == len(alerts)


class ElasticSIEMClient(SIEMClientBase):
    """
    Elastic SIEM (Elasticsearch) client.
    Indexes alerts into Elasticsearch.
    """
    
    def __init__(
        self,
        url: str,
        api_key: str,
        index: str = 'ids-alerts',
        verify_ssl: bool = True,
        timeout: float = 5.0,
        max_retries: int = 3,
        batch_size: int = 20
    ):
        """
        Initialize Elastic SIEM client.
        
        Args:
            url: Elasticsearch URL
            api_key: API key for authentication
            index: Index name
            verify_ssl: Verify SSL certificates
            timeout: Request timeout
            max_retries: Maximum retries
            batch_size: Batch size for bulk API
        """
        super().__init__(url, verify_ssl, timeout, max_retries)
        self.api_key = api_key
        self.index = index
        self.batch_size = batch_size
        
        # Set authorization header
        self.session.headers.update({
            'Authorization': f'ApiKey {api_key}',
            'Content-Type': 'application/json'
        })
        
        logger.info(f"Elastic SIEM client initialized: {url}, index={index}")
    
    def _format_document(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format alert as Elasticsearch document (ECS compatible).
        
        Args:
            alert: Alert dictionary
        
        Returns:
            ECS-compatible document
        """
        return {
            '@timestamp': alert.get('timestamp'),
            'event': {
                'kind': 'alert',
                'category': ['intrusion_detection'],
                'type': ['indicator'],
                'severity': {
                    'INFO': 0,
                    'LOW': 1,
                    'MEDIUM': 2,
                    'HIGH': 3,
                    'CRITICAL': 4
                }.get(alert.get('severity'), 2),
                'id': alert.get('alert_id'),
            },
            'rule': {
                'name': alert.get('class_name'),
                'description': f"ML-detected {alert.get('class_name')}",
                'version': alert.get('model_version'),
            },
            'source': {
                'ip': alert.get('src_ip'),
                'port': alert.get('src_port'),
                'geo': {'country_iso_code': alert.get('src_geo')} if alert.get('src_geo') else None,
            },
            'destination': {
                'ip': alert.get('dst_ip'),
                'port': alert.get('dst_port'),
                'geo': {'country_iso_code': alert.get('dst_geo')} if alert.get('dst_geo') else None,
            },
            'network': {
                'protocol': alert.get('protocol'),
                'community_id': alert.get('flow_id'),
            },
            'ids': {
                'alert_id': alert.get('alert_id'),
                'flow_id': alert.get('flow_id'),
                'class_idx': alert.get('class_idx'),
                'confidence': alert.get('confidence'),
                'model_version': alert.get('model_version'),
                'feature_version': alert.get('feature_version'),
            },
            'tags': alert.get('tags', []),
        }
    
    def send(self, alert: Dict[str, Any]) -> bool:
        """Index single alert in Elasticsearch."""
        try:
            doc = self._format_document(alert)
            
            # Index document
            url = urljoin(self.url, f'/{self.index}/_doc')
            response = self.session.post(
                url,
                json=doc,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            logger.debug(f"Indexed alert {alert.get('alert_id')} in Elasticsearch")
            return True
        
        except Exception as e:
            logger.error(f"Failed to index alert in Elasticsearch: {e}")
            return False
    
    def send_batch(self, alerts: List[Dict[str, Any]]) -> bool:
        """Bulk index alerts in Elasticsearch."""
        if not alerts:
            return True
        
        try:
            # Build bulk request (newline-delimited JSON)
            bulk_data = []
            for alert in alerts:
                # Action line
                bulk_data.append(json.dumps({'index': {'_index': self.index}}))
                # Document line
                bulk_data.append(json.dumps(self._format_document(alert)))
            
            payload = '\n'.join(bulk_data) + '\n'
            
            # Send bulk request
            url = urljoin(self.url, '/_bulk')
            response = self.session.post(
                url,
                data=payload,
                headers={'Content-Type': 'application/x-ndjson'},
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            logger.info(f"Bulk indexed {len(alerts)} alerts in Elasticsearch")
            return True
        
        except Exception as e:
            logger.error(f"Failed to bulk index alerts in Elasticsearch: {e}")
            return False
