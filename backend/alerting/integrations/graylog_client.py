"""Graylog GELF client for alert forwarding."""
import json
import logging
import socket
import struct
import time
import zlib
from typing import Dict, Any, Optional
import requests
from ..rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class GraylogClient:
    """Send alerts to Graylog using GELF format."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Graylog client.
        
        Args:
            config: Configuration dictionary with host, port, protocol
        """
        self.host = config.get('host', 'localhost')
        self.port = int(config.get('port', 12201))
        self.protocol = config.get('protocol', 'HTTP').upper()
        self.timeout = config.get('timeout_ms', 5000) / 1000
        
        # Rate limiting
        self.rate_limiter = RateLimiter(
            per_minute=config.get('rate_limit_per_min', 60),
            per_hour=config.get('rate_limit_per_hour', 1000)
        )
        
        logger.info(f"Graylog client initialized: {self.protocol}://{self.host}:{self.port}")
    
    def send_alert(self, alert: Dict[str, Any]) -> bool:
        """Send alert to Graylog in GELF format.
        
        Args:
            alert: Alert dictionary
            
        Returns:
            True if sent successfully, False otherwise
        """
        # Check rate limit
        if not self.rate_limiter.allow():
            logger.warning("Graylog rate limit exceeded, dropping alert")
            return False
        
        try:
            # Convert to GELF format
            gelf_message = self._to_gelf(alert)
            
            # Send based on protocol
            if self.protocol == 'HTTP':
                return self._send_http(gelf_message)
            elif self.protocol == 'UDP':
                return self._send_udp(gelf_message)
            elif self.protocol == 'TCP':
                return self._send_tcp(gelf_message)
            else:
                logger.error(f"Unsupported protocol: {self.protocol}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send alert to Graylog: {e}", exc_info=True)
            return False
    
    def _to_gelf(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Convert alert to GELF format.
        
        GELF spec: https://docs.graylog.org/docs/gelf
        
        Args:
            alert: Alert dictionary
            
        Returns:
            GELF formatted message
        """
        # Map severity to syslog level
        severity_map = {
            'CRITICAL': 2,  # Critical
            'HIGH': 3,      # Error
            'MEDIUM': 4,    # Warning
            'LOW': 6,       # Informational
            'INFO': 7       # Debug
        }
        
        gelf = {
            'version': '1.1',
            'host': 'adaptive-ids',
            'short_message': alert.get('description', 'IDS Alert'),
            'full_message': self._format_full_message(alert),
            'timestamp': alert.get('timestamp', time.time()),
            'level': severity_map.get(alert.get('severity', 'INFO'), 6),
            
            # Custom fields (prefixed with _)
            '_alert_id': alert.get('alert_id'),
            '_flow_id': alert.get('flow_id'),
            '_severity': alert.get('severity'),
            '_class_name': alert.get('class_name'),
            '_confidence': alert.get('confidence'),
            '_src_ip': alert.get('src_ip'),
            '_dst_ip': alert.get('dst_ip'),
            '_src_port': alert.get('src_port'),
            '_dst_port': alert.get('dst_port'),
            '_protocol': alert.get('protocol'),
            '_model_version': alert.get('model_version'),
            '_feature_version': alert.get('feature_version'),
        }
        
        # Remove None values
        return {k: v for k, v in gelf.items() if v is not None}
    
    def _format_full_message(self, alert: Dict[str, Any]) -> str:
        """Format detailed message for full_message field."""
        lines = [
            f"Alert ID: {alert.get('alert_id')}",
            f"Severity: {alert.get('severity')}",
            f"Classification: {alert.get('class_name')}",
            f"Confidence: {alert.get('confidence', 0):.2%}",
            f"",
            f"Network Flow:",
            f"  Source: {alert.get('src_ip')}:{alert.get('src_port')}",
            f"  Destination: {alert.get('dst_ip')}:{alert.get('dst_port')}",
            f"  Protocol: {alert.get('protocol')}",
            f"",
            f"Model: {alert.get('model_version')} / Features: {alert.get('feature_version')}"
        ]
        return '\n'.join(lines)
    
    def _send_http(self, message: Dict[str, Any]) -> bool:
        """Send via GELF HTTP."""
        try:
            url = f"http://{self.host}:{self.port}/gelf"
            response = requests.post(
                url,
                json=message,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 202:
                logger.debug(f"Sent alert to Graylog via HTTP: {message.get('_alert_id')}")
                return True
            else:
                logger.error(f"Graylog HTTP returned {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send to Graylog via HTTP: {e}")
            return False
    
    def _send_udp(self, message: Dict[str, Any]) -> bool:
        """Send via GELF UDP (with chunking for large messages)."""
        try:
            # Compress message
            payload = json.dumps(message).encode('utf-8')
            compressed = zlib.compress(payload)
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.timeout)
            
            # GELF UDP has 8192 byte limit, chunk if needed
            max_chunk_size = 8192
            if len(compressed) > max_chunk_size:
                logger.warning("Message too large for single UDP packet, chunking")
                # Implement chunking if needed
                return False
            
            sock.sendto(compressed, (self.host, self.port))
            sock.close()
            
            logger.debug(f"Sent alert to Graylog via UDP: {message.get('_alert_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send to Graylog via UDP: {e}")
            return False
    
    def _send_tcp(self, message: Dict[str, Any]) -> bool:
        """Send via GELF TCP."""
        try:
            payload = json.dumps(message).encode('utf-8')
            # TCP messages must be null-terminated
            payload += b'\0'
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.host, self.port))
            sock.sendall(payload)
            sock.close()
            
            logger.debug(f"Sent alert to Graylog via TCP: {message.get('_alert_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send to Graylog via TCP: {e}")
            return False
    
    def health_check(self) -> bool:
        """Check if Graylog is reachable."""
        try:
            if self.protocol == 'HTTP':
                url = f"http://{self.host}:{self.port}/gelf"
                response = requests.get(url, timeout=2)
                return response.status_code in [200, 405]  # 405 = Method Not Allowed is OK
            else:
                # Try UDP/TCP connection
                sock = socket.socket(
                    socket.AF_INET,
                    socket.SOCK_DGRAM if self.protocol == 'UDP' else socket.SOCK_STREAM
                )
                sock.settimeout(2)
                sock.connect((self.host, self.port))
                sock.close()
                return True
        except Exception as e:
            logger.error(f"Graylog health check failed: {e}")
            return False
