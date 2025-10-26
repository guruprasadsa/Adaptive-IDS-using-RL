"""
Audit Logging for Adaptive IDS
Provides comprehensive audit trail for security and compliance
"""

import hashlib
import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, Optional

import psycopg2
from flask import g, request
from psycopg2.extras import execute_batch

logger = logging.getLogger(__name__)


class AuditEvent:
    """Represents an audit event"""
    
    def __init__(
        self,
        event_type: str,
        action: str,
        resource_type: str,
        resource_id: str,
        user_id: Optional[int] = None,
        service_name: Optional[str] = None,
        status: str = 'success',
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        changes: Optional[Dict[str, Any]] = None
    ):
        self.event_id = self._generate_event_id()
        self.timestamp = datetime.now(timezone.utc)
        self.event_type = event_type
        self.action = action
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.user_id = user_id
        self.service_name = service_name
        self.status = status
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.details = details or {}
        self.changes = changes or {}
    
    def _generate_event_id(self) -> str:
        """Generate a unique event ID"""
        timestamp_ns = time.time_ns()
        random_part = os.urandom(8).hex()
        return f"audit_{timestamp_ns}_{random_part}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'user_id': self.user_id,
            'service_name': self.service_name,
            'status': self.status,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'details': self.details,
            'changes': self.changes,
        }


class AuditLogger:
    """Manages audit logging to database and files"""
    
    def __init__(
        self,
        pg_dsn: str,
        log_file_path: Optional[str] = None,
        buffer_size: int = 50,
        flush_interval: float = 5.0
    ):
        """
        Initialize audit logger
        
        Args:
            pg_dsn: PostgreSQL connection string
            log_file_path: Optional file path for audit logs
            buffer_size: Number of events to buffer before flushing
            flush_interval: Flush interval in seconds
        """
        self.pg_dsn = pg_dsn
        self.log_file_path = log_file_path
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        
        # Event buffer
        self.buffer = []
        self.last_flush = time.time()
        
        # Initialize database
        self._init_database()
        
        logger.info(f"Audit Logger initialized: buffer_size={buffer_size}")
    
    def _init_database(self):
        """Initialize audit log table"""
        try:
            conn = psycopg2.connect(self.pg_dsn)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id SERIAL PRIMARY KEY,
                    event_id VARCHAR(128) UNIQUE NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL,
                    event_type VARCHAR(64) NOT NULL,
                    action VARCHAR(64) NOT NULL,
                    resource_type VARCHAR(64) NOT NULL,
                    resource_id VARCHAR(256) NOT NULL,
                    user_id INTEGER,
                    service_name VARCHAR(128),
                    status VARCHAR(32) NOT NULL,
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    details JSONB DEFAULT '{}'::jsonb,
                    changes JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS audit_logs_timestamp_idx 
                ON audit_logs (timestamp DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS audit_logs_user_id_idx 
                ON audit_logs (user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS audit_logs_resource_idx 
                ON audit_logs (resource_type, resource_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS audit_logs_event_type_idx 
                ON audit_logs (event_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS audit_logs_action_idx 
                ON audit_logs (action)
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info("Audit log database initialized")
        
        except Exception as e:
            logger.error(f"Failed to initialize audit log database: {e}")
            raise
    
    def log(self, event: AuditEvent):
        """
        Log an audit event
        
        Args:
            event: AuditEvent to log
        """
        # Add to buffer
        self.buffer.append(event)
        
        # Also log to file if configured
        if self.log_file_path:
            self._log_to_file(event)
        
        # Flush if needed
        if (len(self.buffer) >= self.buffer_size or
            time.time() - self.last_flush >= self.flush_interval):
            self.flush()
    
    def _log_to_file(self, event: AuditEvent):
        """Write event to log file"""
        try:
            with open(self.log_file_path, 'a') as f:
                f.write(json.dumps(event.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Failed to write audit log to file: {e}")
    
    def flush(self):
        """Flush buffered events to database"""
        if not self.buffer:
            return
        
        try:
            conn = psycopg2.connect(self.pg_dsn)
            cursor = conn.cursor()
            
            # Prepare batch insert
            query = """
                INSERT INTO audit_logs (
                    event_id, timestamp, event_type, action,
                    resource_type, resource_id, user_id, service_name,
                    status, ip_address, user_agent, details, changes
                ) VALUES (
                    %(event_id)s, %(timestamp)s, %(event_type)s, %(action)s,
                    %(resource_type)s, %(resource_id)s, %(user_id)s, %(service_name)s,
                    %(status)s, %(ip_address)s, %(user_agent)s, 
                    %(details)s::jsonb, %(changes)s::jsonb
                )
            """
            
            # Convert events to records
            records = []
            for event in self.buffer:
                record = {
                    'event_id': event.event_id,
                    'timestamp': event.timestamp,
                    'event_type': event.event_type,
                    'action': event.action,
                    'resource_type': event.resource_type,
                    'resource_id': event.resource_id,
                    'user_id': event.user_id,
                    'service_name': event.service_name,
                    'status': event.status,
                    'ip_address': event.ip_address,
                    'user_agent': event.user_agent,
                    'details': json.dumps(event.details),
                    'changes': json.dumps(event.changes),
                }
                records.append(record)
            
            # Execute batch
            execute_batch(cursor, query, records)
            conn.commit()
            
            logger.info(f"Flushed {len(self.buffer)} audit events to database")
            
            cursor.close()
            conn.close()
            
            # Clear buffer
            self.buffer = []
            self.last_flush = time.time()
        
        except Exception as e:
            logger.error(f"Failed to flush audit events: {e}")
    
    def close(self):
        """Flush and close logger"""
        self.flush()


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def init_audit_logger(pg_dsn: str, log_file_path: Optional[str] = None):
    """Initialize the global audit logger"""
    global _audit_logger
    _audit_logger = AuditLogger(pg_dsn, log_file_path)


def get_audit_logger() -> Optional[AuditLogger]:
    """Get the global audit logger instance"""
    return _audit_logger


def audit_log(
    action: str,
    resource_type: str,
    resource_id: str = '',
    event_type: str = 'data_access',
    include_changes: bool = False
):
    """
    Decorator to automatically audit log an action
    
    Args:
        action: Action being performed (e.g., 'create', 'update', 'delete', 'view')
        resource_type: Type of resource (e.g., 'alert', 'incident', 'user')
        resource_id: ID of resource (can be extracted from route params)
        event_type: Type of event (e.g., 'data_access', 'authentication', 'configuration')
        include_changes: Whether to capture request body as changes
    
    Usage:
        @app.route('/api/alerts/<alert_id>/ack', methods=['POST'])
        @require_auth
        @audit_log(action='acknowledge', resource_type='alert')
        def ack_alert(user_id: int, alert_id: str):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            logger_instance = get_audit_logger()
            
            if not logger_instance:
                # Audit logging not initialized, just execute function
                return f(*args, **kwargs)
            
            # Extract context
            user_id = kwargs.get('user_id')
            service_name = None
            
            # Try to get service name from API key
            api_key = kwargs.get('api_key')
            if api_key:
                service_name = api_key.service_name
            
            # Get resource ID from route params or kwargs
            actual_resource_id = resource_id
            if not actual_resource_id:
                # Try common parameter names
                for param in ['alert_id', 'incident_id', 'user_id', 'id']:
                    if param in kwargs:
                        actual_resource_id = str(kwargs[param])
                        break
            
            # Capture request details
            ip_address = request.remote_addr
            user_agent = request.headers.get('User-Agent', '')[:500]  # Limit length
            
            # Capture changes if requested
            changes = {}
            if include_changes and request.method in ['POST', 'PUT', 'PATCH']:
                try:
                    changes = request.get_json(silent=True) or {}
                except:
                    pass
            
            # Execute function and capture result
            start_time = time.time()
            status = 'success'
            error_message = None
            
            try:
                result = f(*args, **kwargs)
                
                # Check if result indicates error
                if isinstance(result, tuple):
                    response, status_code = result[0], result[1]
                    if status_code >= 400:
                        status = 'failure'
                        if hasattr(response, 'get_json'):
                            error_data = response.get_json()
                            if error_data and 'message' in error_data:
                                error_message = error_data['message']
                
                return result
            
            except Exception as e:
                status = 'error'
                error_message = str(e)
                raise
            
            finally:
                # Create audit event
                duration_ms = int((time.time() - start_time) * 1000)
                
                details = {
                    'method': request.method,
                    'path': request.path,
                    'duration_ms': duration_ms,
                }
                
                if error_message:
                    details['error'] = error_message
                
                event = AuditEvent(
                    event_type=event_type,
                    action=action,
                    resource_type=resource_type,
                    resource_id=actual_resource_id or 'unknown',
                    user_id=user_id,
                    service_name=service_name,
                    status=status,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details=details,
                    changes=changes
                )
                
                logger_instance.log(event)
        
        return decorated_function
    return decorator


@contextmanager
def audit_context(
    action: str,
    resource_type: str,
    resource_id: str,
    user_id: Optional[int] = None,
    service_name: Optional[str] = None
):
    """
    Context manager for audit logging
    
    Usage:
        with audit_context('rotate', 'api_key', key_id, user_id=user_id):
            # Perform action
            new_key = rotate_key(key_id)
    """
    logger_instance = get_audit_logger()
    
    if not logger_instance:
        yield
        return
    
    start_time = time.time()
    status = 'success'
    error_message = None
    
    try:
        yield
    except Exception as e:
        status = 'error'
        error_message = str(e)
        raise
    finally:
        duration_ms = int((time.time() - start_time) * 1000)
        
        details = {
            'duration_ms': duration_ms,
        }
        
        if error_message:
            details['error'] = error_message
        
        event = AuditEvent(
            event_type='system_operation',
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            service_name=service_name,
            status=status,
            details=details
        )
        
        logger_instance.log(event)
