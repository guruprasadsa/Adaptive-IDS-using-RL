"""
Email Notification Client
Sends alert notifications via email with rate limiting and templating.
"""
import smtplib
import logging
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional
from collections import deque
from datetime import datetime, timedelta
from threading import Lock

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter for email notifications.
    Implements sliding window rate limiting.
    """
    
    def __init__(
        self,
        max_per_minute: int = 5,
        max_per_hour: int = 20,
        max_per_day: int = 100
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_per_minute: Maximum emails per minute
            max_per_hour: Maximum emails per hour
            max_per_day: Maximum emails per day
        """
        self.max_per_minute = max_per_minute
        self.max_per_hour = max_per_hour
        self.max_per_day = max_per_day
        
        # Sliding windows
        self.minute_window: deque = deque()
        self.hour_window: deque = deque()
        self.day_window: deque = deque()
        
        self._lock = Lock()
    
    def _clean_window(self, window: deque, max_age_seconds: int):
        """Remove old entries from window."""
        cutoff = time.time() - max_age_seconds
        while window and window[0] < cutoff:
            window.popleft()
    
    def can_send(self) -> bool:
        """
        Check if email can be sent based on rate limits.
        
        Returns:
            True if allowed, False if rate limited
        """
        with self._lock:
            now = time.time()
            
            # Clean windows
            self._clean_window(self.minute_window, 60)
            self._clean_window(self.hour_window, 3600)
            self._clean_window(self.day_window, 86400)
            
            # Check limits
            if len(self.minute_window) >= self.max_per_minute:
                logger.warning("Rate limit exceeded: max_per_minute")
                return False
            
            if len(self.hour_window) >= self.max_per_hour:
                logger.warning("Rate limit exceeded: max_per_hour")
                return False
            
            if len(self.day_window) >= self.max_per_day:
                logger.warning("Rate limit exceeded: max_per_day")
                return False
            
            return True
    
    def record_send(self):
        """Record that an email was sent."""
        with self._lock:
            now = time.time()
            self.minute_window.append(now)
            self.hour_window.append(now)
            self.day_window.append(now)
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get current rate limit statistics.
        
        Returns:
            Dict with counts for each window
        """
        with self._lock:
            now = time.time()
            self._clean_window(self.minute_window, 60)
            self._clean_window(self.hour_window, 3600)
            self._clean_window(self.day_window, 86400)
            
            return {
                'last_minute': len(self.minute_window),
                'last_hour': len(self.hour_window),
                'last_day': len(self.day_window),
            }


class EmailClient:
    """
    Email notification client with rate limiting and templating.
    """
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        smtp_tls: bool = True,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_address: str = 'ids-alerts@example.com',
        to_addresses: str = 'security-team@example.com',
        cc_addresses: Optional[str] = None,
        subject_template: str = "[{severity}] IDS Alert: {class_name} detected from {src_ip}",
        max_per_minute: int = 5,
        max_per_hour: int = 20,
        max_per_day: int = 100
    ):
        """
        Initialize email client.
        
        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            smtp_tls: Use TLS encryption
            smtp_user: SMTP username
            smtp_password: SMTP password
            from_address: Sender email address
            to_addresses: Recipient email addresses (comma-separated)
            cc_addresses: CC email addresses (comma-separated)
            subject_template: Email subject template
            max_per_minute: Rate limit (emails per minute)
            max_per_hour: Rate limit (emails per hour)
            max_per_day: Rate limit (emails per day)
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_tls = smtp_tls
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_address = from_address
        self.to_addresses = [addr.strip() for addr in to_addresses.split(',')]
        self.cc_addresses = [addr.strip() for addr in cc_addresses.split(',')] if cc_addresses else []
        self.subject_template = subject_template
        
        # Rate limiter
        self.rate_limiter = RateLimiter(max_per_minute, max_per_hour, max_per_day)
        
        cc_info = f", cc={self.cc_addresses}" if self.cc_addresses else ""
        logger.info(
            f"Email client initialized: {smtp_host}:{smtp_port}, "
            f"to={self.to_addresses}{cc_info}"
        )
    
    def _render_subject(self, alert: Dict[str, Any]) -> str:
        """
        Render email subject from template.
        
        Args:
            alert: Alert dictionary
        
        Returns:
            Rendered subject line
        """
        try:
            return self.subject_template.format(**alert)
        except Exception as e:
            logger.warning(f"Failed to render subject template: {e}")
            return f"[{alert.get('severity', 'UNKNOWN')}] IDS Alert"
    
    def _render_body_text(self, alert: Dict[str, Any]) -> str:
        """
        Render plain text email body.
        
        Args:
            alert: Alert dictionary
        
        Returns:
            Plain text body
        """
        body = f"""
Adaptive IDS Security Alert
============================

Alert Details:
--------------
Alert ID:       {alert.get('alert_id', 'N/A')}
Flow ID:        {alert.get('flow_id', 'N/A')}
Timestamp:      {datetime.fromtimestamp(alert.get('timestamp', 0) / 1000.0).strftime('%Y-%m-%d %H:%M:%S UTC')}
Severity:       {alert.get('severity', 'UNKNOWN')}

Attack Classification:
----------------------
Class:          {alert.get('class_name', 'Unknown')}
Confidence:     {alert.get('confidence', 0.0):.2%}

Network Context:
----------------
Source:         {alert.get('src_ip', 'unknown')}:{alert.get('src_port', 0)}
Destination:    {alert.get('dst_ip', 'unknown')}:{alert.get('dst_port', 0)}
Protocol:       {alert.get('protocol', 'unknown')}

Model Information:
------------------
Model Version:  {alert.get('model_version', 'N/A')}
Feature Ver:    {alert.get('feature_version', 'N/A')}

Status:         {alert.get('status', 'NEW')}
"""
        
        # Add enrichment if available
        if alert.get('src_geo') or alert.get('dst_geo'):
            body += f"\nGeolocation:\n"
            body += f"Source GEO:     {alert.get('src_geo', 'N/A')}\n"
            body += f"Dest GEO:       {alert.get('dst_geo', 'N/A')}\n"
        
        if alert.get('tags'):
            body += f"\nTags: {', '.join(alert.get('tags', []))}\n"
        
        body += f"""
---
This is an automated alert from Adaptive IDS.
Please investigate and take appropriate action.

Dashboard: https://ids-dashboard.example.com/alerts/{alert.get('alert_id', '')}
"""
        
        return body
    
    def _render_body_html(self, alert: Dict[str, Any]) -> str:
        """
        Render HTML email body.
        
        Args:
            alert: Alert dictionary
        
        Returns:
            HTML body
        """
        # Severity color coding
        severity_colors = {
            'CRITICAL': '#d32f2f',
            'HIGH': '#f57c00',
            'MEDIUM': '#fbc02d',
            'LOW': '#0288d1',
            'INFO': '#757575',
        }
        severity_color = severity_colors.get(alert.get('severity', 'MEDIUM'), '#757575')
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: {severity_color}; color: white; padding: 20px; border-radius: 5px 5px 0 0; }}
        .content {{ background-color: #f5f5f5; padding: 20px; border-radius: 0 0 5px 5px; }}
        .section {{ background-color: white; margin: 10px 0; padding: 15px; border-radius: 3px; }}
        .label {{ font-weight: bold; color: #555; }}
        .value {{ color: #333; }}
        .footer {{ margin-top: 20px; padding: 10px; text-align: center; color: #777; font-size: 12px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        td {{ padding: 8px; }}
        .confidence {{ font-size: 24px; font-weight: bold; color: {severity_color}; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚨 Security Alert: {alert.get('class_name', 'Unknown Threat')}</h1>
            <p>Severity: {alert.get('severity', 'UNKNOWN')} | Confidence: {alert.get('confidence', 0.0):.1%}</p>
        </div>
        
        <div class="content">
            <div class="section">
                <h2>Alert Details</h2>
                <table>
                    <tr>
                        <td class="label">Alert ID:</td>
                        <td class="value">{alert.get('alert_id', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td class="label">Flow ID:</td>
                        <td class="value">{alert.get('flow_id', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td class="label">Timestamp:</td>
                        <td class="value">{datetime.fromtimestamp(alert.get('timestamp', 0) / 1000.0).strftime('%Y-%m-%d %H:%M:%S UTC')}</td>
                    </tr>
                    <tr>
                        <td class="label">Confidence:</td>
                        <td class="confidence">{alert.get('confidence', 0.0):.2%}</td>
                    </tr>
                </table>
            </div>
            
            <div class="section">
                <h2>Network Context</h2>
                <table>
                    <tr>
                        <td class="label">Source:</td>
                        <td class="value">{alert.get('src_ip', 'unknown')}:{alert.get('src_port', 0)}</td>
                    </tr>
                    <tr>
                        <td class="label">Destination:</td>
                        <td class="value">{alert.get('dst_ip', 'unknown')}:{alert.get('dst_port', 0)}</td>
                    </tr>
                    <tr>
                        <td class="label">Protocol:</td>
                        <td class="value">{alert.get('protocol', 'unknown')}</td>
                    </tr>
                </table>
            </div>
            
            <div class="section">
                <h2>Model Information</h2>
                <table>
                    <tr>
                        <td class="label">Model Version:</td>
                        <td class="value">{alert.get('model_version', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td class="label">Feature Version:</td>
                        <td class="value">{alert.get('feature_version', 'N/A')}</td>
                    </tr>
                </table>
            </div>
        </div>
        
        <div class="footer">
            <p>This is an automated alert from Adaptive IDS.</p>
            <p>View in Dashboard: <a href="https://ids-dashboard.example.com/alerts/{alert.get('alert_id', '')}">Open Alert</a></p>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def send(self, alert: Dict[str, Any]) -> bool:
        """
        Send email notification for alert.
        
        Args:
            alert: Alert dictionary
        
        Returns:
            True if sent successfully, False otherwise
        """
        # Check rate limit
        if not self.rate_limiter.can_send():
            logger.warning(
                f"Rate limit exceeded, skipping email for alert {alert.get('alert_id')}"
            )
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_address
            msg['To'] = ', '.join(self.to_addresses)
            if self.cc_addresses:
                msg['Cc'] = ', '.join(self.cc_addresses)
            msg['Subject'] = self._render_subject(alert)
            
            # Attach plain text and HTML versions
            text_part = MIMEText(self._render_body_text(alert), 'plain')
            html_part = MIMEText(self._render_body_html(alert), 'html')
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Connect and send
            if self.smtp_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            
            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)
            
            recipients = self.to_addresses + self.cc_addresses
            server.sendmail(self.from_address, recipients, msg.as_string())
            server.quit()
            
            # Record send for rate limiting
            self.rate_limiter.record_send()
            
            logger.info(f"Sent email notification for alert {alert.get('alert_id')}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False
    
    def get_rate_limit_stats(self) -> Dict[str, int]:
        """
        Get rate limit statistics.
        
        Returns:
            Dict with current counts
        """
        return self.rate_limiter.get_stats()
