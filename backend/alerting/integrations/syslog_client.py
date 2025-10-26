"""
Syslog Integration (RFC5424)
Sends alerts to syslog server over TLS with connection pooling and retries.
"""
import socket
import ssl
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime
from queue import Queue, Empty
from threading import Lock

logger = logging.getLogger(__name__)


class SyslogClient:
    """
    RFC5424 Syslog client with TLS support.
    Implements connection pooling and automatic reconnection.
    """
    
    # RFC5424 Severity levels
    SEVERITY_MAP = {
        'CRITICAL': 2,  # Critical
        'HIGH': 3,      # Error
        'MEDIUM': 4,    # Warning
        'LOW': 5,       # Notice
        'INFO': 6,      # Informational
    }
    
    # Syslog facilities
    FACILITY_LOCAL0 = 16
    
    def __init__(
        self,
        host: str,
        port: int = 6514,
        protocol: str = 'TLS',
        facility: int = FACILITY_LOCAL0,
        app_name: str = 'adaptive-ids',
        tls_config: Optional[Dict[str, Any]] = None,
        pool_size: int = 5,
        timeout: float = 5.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        keepalive: bool = True
    ):
        """
        Initialize syslog client.
        
        Args:
            host: Syslog server hostname
            port: Syslog server port (514=UDP, 601=TCP, 6514=TLS)
            protocol: Protocol (TLS, TCP, or UDP)
            facility: Syslog facility (0-23)
            app_name: Application name for syslog messages
            tls_config: TLS configuration dict (cert_file, key_file, ca_file, verify_cert)
            pool_size: Connection pool size
            timeout: Socket timeout in seconds
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries in seconds
            keepalive: Enable TCP keepalive
        """
        self.host = host
        self.port = int(port) if isinstance(port, str) else port
        self.protocol = protocol.upper()
        self.facility = facility
        self.app_name = app_name
        self.tls_config = tls_config or {}
        self.pool_size = pool_size
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.keepalive = keepalive
        
        # Connection pool
        self._pool: Queue = Queue(maxsize=pool_size)
        self._lock = Lock()
        self._connections_created = 0
        
        # Validate configuration
        if self.protocol not in ('TLS', 'TCP', 'UDP'):
            raise ValueError(f"Invalid protocol: {self.protocol}")
        
        logger.info(
            f"Syslog client initialized: {protocol}://{host}:{port}, "
            f"facility={facility}, pool_size={pool_size}"
        )
    
    def _create_connection(self) -> socket.socket:
        """
        Create a new syslog connection.
        
        Returns:
            Socket connection
        """
        try:
            if self.protocol == 'UDP':
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(self.timeout)
                logger.debug(f"Created UDP socket to {self.host}:{self.port}")
                return sock
            
            # TCP or TLS
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            
            # Enable TCP keepalive
            if self.keepalive:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            
            # Connect
            sock.connect((self.host, self.port))
            
            # Wrap with TLS if needed
            if self.protocol == 'TLS':
                context = ssl.create_default_context()
                
                # Configure TLS
                if not self.tls_config.get('verify_cert', True):
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                
                if self.tls_config.get('ca_file'):
                    context.load_verify_locations(cafile=self.tls_config['ca_file'])
                
                if self.tls_config.get('cert_file') and self.tls_config.get('key_file'):
                    context.load_cert_chain(
                        certfile=self.tls_config['cert_file'],
                        keyfile=self.tls_config['key_file']
                    )
                
                sock = context.wrap_socket(sock, server_hostname=self.host)
                logger.debug(f"Created TLS socket to {self.host}:{self.port}")
            else:
                logger.debug(f"Created TCP socket to {self.host}:{self.port}")
            
            self._connections_created += 1
            return sock
        
        except Exception as e:
            logger.error(f"Failed to create syslog connection: {e}")
            raise
    
    def _get_connection(self) -> socket.socket:
        """Get connection from pool or create new one."""
        try:
            # Try to get from pool (non-blocking)
            return self._pool.get_nowait()
        except Empty:
            # Pool is empty, create new connection if under limit
            with self._lock:
                if self._connections_created < self.pool_size:
                    return self._create_connection()
                else:
                    # Wait for connection to be available
                    return self._pool.get(timeout=self.timeout)
    
    def _return_connection(self, conn: socket.socket):
        """Return connection to pool."""
        try:
            self._pool.put_nowait(conn)
        except:
            # Pool is full, close connection
            try:
                conn.close()
            except:
                pass
    
    def _close_connection(self, conn: socket.socket):
        """Close connection."""
        try:
            conn.close()
            with self._lock:
                self._connections_created -= 1
        except:
            pass
    
    def _format_rfc5424(
        self,
        severity: str,
        message: str,
        structured_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format message according to RFC5424.
        
        Format:
        <priority>version timestamp hostname app-name procid msgid [structured-data] message
        
        Args:
            severity: Alert severity
            message: Message text
            structured_data: Structured data dict
        
        Returns:
            RFC5424 formatted message
        """
        # Calculate priority
        syslog_severity = self.SEVERITY_MAP.get(severity, 5)  # Default to Notice
        priority = (self.facility * 8) + syslog_severity
        
        # Version
        version = 1
        
        # Timestamp (ISO8601 with timezone)
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        # Hostname
        hostname = socket.gethostname()
        
        # Process ID
        procid = '-'
        
        # Message ID
        msgid = '-'
        
        # Structured data
        sd_str = '-'
        if structured_data:
            sd_elements = []
            for sd_id, params in structured_data.items():
                param_str = ' '.join([f'{k}="{v}"' for k, v in params.items()])
                sd_elements.append(f'[{sd_id} {param_str}]')
            sd_str = ''.join(sd_elements)
        
        # Assemble message
        syslog_msg = (
            f"<{priority}>{version} {timestamp} {hostname} {self.app_name} "
            f"{procid} {msgid} {sd_str} {message}"
        )
        
        return syslog_msg
    
    def send(self, alert: Dict[str, Any]) -> bool:
        """
        Send alert to syslog.
        
        Args:
            alert: Alert dictionary
        
        Returns:
            True if successful, False otherwise
        """
        severity = alert.get('severity', 'MEDIUM')
        
        # Format message
        message = (
            f"[{severity}] {alert.get('class_name', 'Unknown')} detected: "
            f"{alert.get('src_ip', 'unknown')}:{alert.get('src_port', 0)} -> "
            f"{alert.get('dst_ip', 'unknown')}:{alert.get('dst_port', 0)} "
            f"(confidence: {alert.get('confidence', 0.0):.2%})"
        )
        
        # Structured data
        structured_data = {
            'ids@32473': {  # Private enterprise number
                'alert_id': alert.get('alert_id', ''),
                'flow_id': alert.get('flow_id', ''),
                'class_name': alert.get('class_name', ''),
                'class_idx': str(alert.get('class_idx', '')),
                'confidence': f"{alert.get('confidence', 0.0):.4f}",
                'severity': severity,
                'src_ip': alert.get('src_ip', ''),
                'dst_ip': alert.get('dst_ip', ''),
                'protocol': alert.get('protocol', ''),
                'model_version': alert.get('model_version', ''),
            }
        }
        
        # Format RFC5424 message
        syslog_msg = self._format_rfc5424(severity, message, structured_data)
        
        # Send with retry
        for attempt in range(self.max_retries):
            conn = None
            try:
                conn = self._get_connection()
                
                # Send message
                if self.protocol == 'UDP':
                    conn.sendto(syslog_msg.encode('utf-8'), (self.host, self.port))
                else:
                    # TCP/TLS: append newline and send
                    conn.sendall((syslog_msg + '\n').encode('utf-8'))
                
                # Return connection to pool
                self._return_connection(conn)
                
                logger.debug(f"Sent alert {alert.get('alert_id')} to syslog")
                return True
            
            except Exception as e:
                logger.warning(
                    f"Syslog send attempt {attempt + 1}/{self.max_retries} failed: {e}"
                )
                
                # Close bad connection
                if conn:
                    self._close_connection(conn)
                
                # Retry with delay
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        
        logger.error(f"Failed to send alert {alert.get('alert_id')} to syslog after {self.max_retries} attempts")
        return False
    
    def close(self):
        """Close all connections in pool."""
        logger.info("Closing syslog client connections")
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except:
                pass
