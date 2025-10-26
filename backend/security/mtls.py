"""
Mutual TLS (mTLS) Support for Adaptive IDS
Provides certificate management and verification for service-to-service communication
"""

import logging
import ssl
from pathlib import Path
from typing import Optional

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from flask import Request, jsonify, request
from functools import wraps

logger = logging.getLogger(__name__)


class MTLSManager:
    """Manages mTLS certificates and verification"""
    
    def __init__(
        self,
        ca_cert_path: str,
        server_cert_path: Optional[str] = None,
        server_key_path: Optional[str] = None,
        client_cert_path: Optional[str] = None,
        client_key_path: Optional[str] = None
    ):
        """
        Initialize mTLS manager
        
        Args:
            ca_cert_path: Path to CA certificate
            server_cert_path: Path to server certificate
            server_key_path: Path to server private key
            client_cert_path: Path to client certificate
            client_key_path: Path to client private key
        """
        self.ca_cert_path = Path(ca_cert_path)
        self.server_cert_path = Path(server_cert_path) if server_cert_path else None
        self.server_key_path = Path(server_key_path) if server_key_path else None
        self.client_cert_path = Path(client_cert_path) if client_cert_path else None
        self.client_key_path = Path(client_key_path) if client_key_path else None
        
        # Load CA certificate
        self.ca_cert = self._load_ca_cert()
        
        logger.info("mTLS Manager initialized")
    
    def _load_ca_cert(self) -> x509.Certificate:
        """Load CA certificate"""
        try:
            with open(self.ca_cert_path, 'rb') as f:
                ca_cert_data = f.read()
            
            ca_cert = x509.load_pem_x509_certificate(ca_cert_data, default_backend())
            logger.info(f"Loaded CA certificate: {ca_cert.subject}")
            return ca_cert
        
        except Exception as e:
            logger.error(f"Failed to load CA certificate: {e}")
            raise
    
    def create_ssl_context(
        self,
        purpose: ssl.Purpose = ssl.Purpose.SERVER_AUTH,
        verify_mode: ssl.VerifyMode = ssl.CERT_REQUIRED
    ) -> ssl.SSLContext:
        """
        Create SSL context for mTLS
        
        Args:
            purpose: SSL purpose (SERVER_AUTH or CLIENT_AUTH)
            verify_mode: Certificate verification mode
        
        Returns:
            Configured SSL context
        """
        context = ssl.create_default_context(purpose=purpose)
        context.verify_mode = verify_mode
        
        # Load CA certificate
        context.load_verify_locations(cafile=str(self.ca_cert_path))
        
        # Load client certificate if configured
        if self.client_cert_path and self.client_key_path:
            context.load_cert_chain(
                certfile=str(self.client_cert_path),
                keyfile=str(self.client_key_path)
            )
            logger.debug("Loaded client certificate for mTLS")
        
        # Load server certificate if configured
        if self.server_cert_path and self.server_key_path:
            context.load_cert_chain(
                certfile=str(self.server_cert_path),
                keyfile=str(self.server_key_path)
            )
            logger.debug("Loaded server certificate for mTLS")
        
        return context
    
    def verify_client_certificate(self, cert_pem: str) -> bool:
        """
        Verify a client certificate against CA
        
        Args:
            cert_pem: PEM-encoded client certificate
        
        Returns:
            True if valid, False otherwise
        """
        try:
            client_cert = x509.load_pem_x509_certificate(
                cert_pem.encode(),
                default_backend()
            )
            
            # Verify issuer
            if client_cert.issuer != self.ca_cert.subject:
                logger.warning("Client certificate issuer mismatch")
                return False
            
            # TODO: Add more comprehensive validation
            # - Check expiration
            # - Verify signature
            # - Check revocation status
            
            logger.info(f"Client certificate verified: {client_cert.subject}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to verify client certificate: {e}")
            return False


# Global mTLS manager instance
_mtls_manager: Optional[MTLSManager] = None


def init_mtls_manager(
    ca_cert_path: str,
    server_cert_path: Optional[str] = None,
    server_key_path: Optional[str] = None,
    client_cert_path: Optional[str] = None,
    client_key_path: Optional[str] = None
):
    """Initialize the global mTLS manager"""
    global _mtls_manager
    _mtls_manager = MTLSManager(
        ca_cert_path,
        server_cert_path,
        server_key_path,
        client_cert_path,
        client_key_path
    )


def get_mtls_manager() -> Optional[MTLSManager]:
    """Get the global mTLS manager instance"""
    return _mtls_manager


def verify_client_cert(f):
    """
    Decorator to verify client certificate for a route
    
    Usage:
        @app.route('/api/internal/endpoint')
        @verify_client_cert
        def endpoint():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        manager = get_mtls_manager()
        
        if not manager:
            # mTLS not configured, allow through
            logger.warning("mTLS not configured but verify_client_cert decorator used")
            return f(*args, **kwargs)
        
        # Get client certificate from request
        # Note: This requires nginx/uwsgi to pass the certificate
        client_cert_pem = request.headers.get('X-SSL-Client-Cert')
        
        if not client_cert_pem:
            return jsonify({
                'error': 'unauthorized',
                'message': 'Client certificate required'
            }), 401
        
        # Verify certificate
        if not manager.verify_client_certificate(client_cert_pem):
            return jsonify({
                'error': 'unauthorized',
                'message': 'Invalid client certificate'
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated_function
