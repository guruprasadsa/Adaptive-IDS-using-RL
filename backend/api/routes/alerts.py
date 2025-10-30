"""
Alert Management API Endpoints
Comprehensive REST API for alert operations with RBAC and validation.
"""
import json
import logging
import csv
import io
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request, Response, stream_with_context
from psycopg2.extras import RealDictCursor
import psycopg2

# Import security components
try:
    from security.rbac import Permission, get_rbac_manager
    from security.audit import get_audit_logger, AuditEvent
    from api.auth import require_auth, get_db_cursor
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False
    # Fallback decorator if security not available
    def require_auth(f):
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs, user_id=1)
        return wrapper

logger = logging.getLogger(__name__)

# Create blueprint
alerts_bp = Blueprint('alerts', __name__, url_prefix='/api/alerts')

# ============================================================================
# Helper Functions
# ============================================================================

def check_permission(user_id: int, permission: str) -> bool:
    """Check if user has permission."""
    if not SECURITY_AVAILABLE:
        return True
    
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if row:
                rbac_manager = get_rbac_manager()
                return rbac_manager.has_permission(row['role'], getattr(Permission, permission))
    except Exception as e:
        logger.error(f"Permission check failed: {e}")
        return False
    return False

def log_audit_event(event_type: str, action: str, resource_type: str, resource_id: str,
                   user_id: int, status: str = 'success', changes: Dict = None):
    """Log audit event."""
    if not SECURITY_AVAILABLE:
        return
    
    try:
        audit_logger = get_audit_logger()
        if audit_logger:
            event = AuditEvent(
                event_type=event_type,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                user_id=user_id,
                status=status,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')[:500],
                changes=changes or {}
            )
            audit_logger.log(event)
    except Exception as e:
        logger.error(f"Audit logging failed: {e}")

def get_db_connection():
    """Get database connection."""
    import os
    dsn = os.getenv(
        'PG_DSN',
        'host=localhost port=55432 dbname=adaptive_ids user=adaptive_ids password=adaptive_ids_password'
    )
    return psycopg2.connect(dsn)

# ============================================================================
# Alert CRUD Endpoints
# ============================================================================

@alerts_bp.route('/<alert_id>/comment', methods=['POST'])
@require_auth
def add_comment(alert_id: str, user_id: int = None) -> Any:
    """Add comment to alert."""
    payload = request.get_json(force=True, silent=True) or {}
    comment_text = payload.get('comment', '').strip()
    
    if not comment_text:
        return jsonify({'error': 'Comment text is required'}), 400
    
    # Check permission
    if not check_permission(user_id, 'ACK_ALERTS'):
        return jsonify({'error': 'Insufficient permissions'}), 403
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verify alert exists
        cur.execute("SELECT alert_id FROM alerts WHERE alert_id = %s AND deleted_at IS NULL", (alert_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error': 'Alert not found'}), 404
        
        # Insert comment
        cur.execute("""
            INSERT INTO alert_comments (alert_id, user_id, comment)
            VALUES (%s, %s, %s)
            RETURNING id, alert_id, user_id, comment, created_at, updated_at
        """, (alert_id, user_id, comment_text))
        
        comment = dict(cur.fetchone())
        conn.commit()
        
        cur.close()
        conn.close()
        
        # Log audit event
        log_audit_event('data_modification', 'add_comment', 'alert', alert_id, user_id,
                       changes={'comment': comment_text})
        
        return jsonify({
            'success': True,
            'comment': comment,
            'message': 'Comment added successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Failed to add comment: {e}")
        return jsonify({'error': 'Database error'}), 500

@alerts_bp.route('/<alert_id>/comments', methods=['GET'])
@require_auth
def get_comments(alert_id: str, user_id: int = None) -> Any:
    """Get all comments for an alert."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                ac.id,
                ac.alert_id,
                ac.user_id,
                u.username,
                ac.comment,
                ac.created_at,
                ac.updated_at
            FROM alert_comments ac
            LEFT JOIN users u ON ac.user_id = u.id
            WHERE ac.alert_id = %s
            ORDER BY ac.created_at DESC
        """, (alert_id,))
        
        comments = [dict(row) for row in cur.fetchall()]
        
        cur.close()
        conn.close()
        
        return jsonify({
            'alert_id': alert_id,
            'comments': comments,
            'count': len(comments)
        })
        
    except Exception as e:
        logger.error(f"Failed to get comments: {e}")
        return jsonify({'error': 'Database error'}), 500

@alerts_bp.route('/<alert_id>/history', methods=['GET'])
@require_auth
def get_history(alert_id: str, user_id: int = None) -> Any:
    """Get status change history for an alert."""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                ah.id,
                ah.alert_id,
                ah.user_id,
                u.username,
                ah.from_status,
                ah.to_status,
                ah.notes,
                ah.created_at
            FROM alert_history ah
            LEFT JOIN users u ON ah.user_id = u.id
            WHERE ah.alert_id = %s
            ORDER BY ah.created_at DESC
        """, (alert_id,))
        
        history = [dict(row) for row in cur.fetchall()]
        
        cur.close()
        conn.close()
        
        return jsonify({
            'alert_id': alert_id,
            'history': history,
            'count': len(history)
        })
        
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        return jsonify({'error': 'Database error'}), 500

@alerts_bp.route('/<alert_id>', methods=['DELETE'])
@require_auth
def soft_delete_alert(alert_id: str, user_id: int = None) -> Any:
    """Soft delete an alert."""
    # Check permission
    if not check_permission(user_id, 'DELETE_ALERTS'):
        return jsonify({'error': 'Insufficient permissions'}), 403
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Soft delete
        cur.execute("""
            UPDATE alerts
            SET deleted_at = NOW(), deleted_by = %s
            WHERE alert_id = %s AND deleted_at IS NULL
            RETURNING alert_id
        """, (user_id, alert_id))
        
        result = cur.fetchone()
        conn.commit()
        
        cur.close()
        conn.close()
        
        if not result:
            return jsonify({'error': 'Alert not found or already deleted'}), 404
        
        # Log audit event
        log_audit_event('data_deletion', 'soft_delete', 'alert', alert_id, user_id)
        
        return jsonify({
            'success': True,
            'message': 'Alert deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Failed to delete alert: {e}")
        return jsonify({'error': 'Database error'}), 500

# ============================================================================
# Bulk Operations
# ============================================================================

@alerts_bp.route('/bulk-acknowledge', methods=['POST'])
@require_auth
def bulk_acknowledge(user_id: int = None) -> Any:
    """Acknowledge multiple alerts at once."""
    # Check permission
    if not check_permission(user_id, 'ACK_ALERTS'):
        return jsonify({'error': 'Insufficient permissions'}), 403
    
    payload = request.get_json(force=True, silent=True) or {}
    alert_ids = payload.get('alert_ids', [])
    notes = payload.get('notes', 'Bulk acknowledged')
    
    if not alert_ids or not isinstance(alert_ids, list):
        return jsonify({'error': 'alert_ids must be a non-empty array'}), 400
    
    if len(alert_ids) > 1000:
        return jsonify({'error': 'Maximum 1000 alerts can be acknowledged at once'}), 400
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Update alerts
        cur.execute("""
            UPDATE alerts
            SET status = 'ACKNOWLEDGED',
                assigned_to = %s,
                notes = %s,
                updated_at = NOW()
            WHERE alert_id = ANY(%s)
            AND status = 'NEW'
            AND deleted_at IS NULL
            RETURNING alert_id
        """, (str(user_id), notes, alert_ids))
        
        updated = [dict(row) for row in cur.fetchall()]
        conn.commit()
        
        cur.close()
        conn.close()
        
        # Log audit event
        log_audit_event('data_modification', 'bulk_acknowledge', 'alerts', 
                       f"{len(updated)} alerts", user_id,
                       changes={'count': len(updated), 'notes': notes})
        
        return jsonify({
            'success': True,
            'acknowledged_count': len(updated),
            'message': f'Successfully acknowledged {len(updated)} alert(s)'
        })
        
    except Exception as e:
        logger.error(f"Bulk acknowledge failed: {e}")
        return jsonify({'error': 'Database error'}), 500

@alerts_bp.route('/bulk-delete', methods=['POST'])
@require_auth
def bulk_delete(user_id: int = None) -> Any:
    """Soft delete multiple alerts at once."""
    # Check permission
    if not check_permission(user_id, 'DELETE_ALERTS'):
        return jsonify({'error': 'Insufficient permissions'}), 403
    
    payload = request.get_json(force=True, silent=True) or {}
    alert_ids = payload.get('alert_ids', [])
    
    if not alert_ids or not isinstance(alert_ids, list):
        return jsonify({'error': 'alert_ids must be a non-empty array'}), 400
    
    if len(alert_ids) > 1000:
        return jsonify({'error': 'Maximum 1000 alerts can be deleted at once'}), 400
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            UPDATE alerts
            SET deleted_at = NOW(), deleted_by = %s
            WHERE alert_id = ANY(%s) AND deleted_at IS NULL
            RETURNING alert_id
        """, (user_id, alert_ids))
        
        deleted = [dict(row) for row in cur.fetchall()]
        conn.commit()
        
        cur.close()
        conn.close()
        
        # Log audit event
        log_audit_event('data_deletion', 'bulk_delete', 'alerts',
                       f"{len(deleted)} alerts", user_id,
                       changes={'count': len(deleted)})
        
        return jsonify({
            'success': True,
            'deleted_count': len(deleted),
            'message': f'Successfully deleted {len(deleted)} alert(s)'
        })
        
    except Exception as e:
        logger.error(f"Bulk delete failed: {e}")
        return jsonify({'error': 'Database error'}), 500

# ============================================================================
# Export & Statistics
# ============================================================================

@alerts_bp.route('/export', methods=['GET'])
@require_auth
def export_alerts(user_id: int = None) -> Any:
    """Export alerts to CSV."""
    # Get filter parameters (same as list_alerts)
    priority = request.args.get('priority')
    status = request.args.get('status')
    severity = request.args.get('severity')
    class_name = request.args.get('class_name')
    src_ip = request.args.get('src_ip')
    dst_ip = request.args.get('dst_ip')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Build query
        query = """
            SELECT 
                alert_id,
                flow_id,
                timestamp,
                class_name,
                confidence,
                severity,
                src_ip,
                dst_ip,
                src_port,
                dst_port,
                protocol,
                status,
                priority,
                model_version,
                feature_version,
                created_at
            FROM alerts
            WHERE deleted_at IS NULL
        """
        params = []
        
        # Add filters
        if priority and priority != 'all':
            query += " AND priority = %s"
            params.append(priority)
        
        if status and status != 'all':
            query += " AND status = %s"
            params.append(status.upper())
        
        if severity:
            query += " AND severity = %s"
            params.append(severity.upper())
        
        if class_name:
            query += " AND LOWER(class_name) LIKE LOWER(%s)"
            params.append(f"%{class_name}%")
        
        if src_ip:
            query += " AND src_ip = %s"
            params.append(src_ip)
        
        if dst_ip:
            query += " AND dst_ip = %s"
            params.append(dst_ip)
        
        if start_time:
            query += " AND timestamp >= %s::timestamptz"
            params.append(start_time)
        
        if end_time:
            query += " AND timestamp <= %s::timestamptz"
            params.append(end_time)
        
        query += " ORDER BY timestamp DESC LIMIT 10000"  # Limit exports to 10k rows
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Generate CSV
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))
        
        csv_data = output.getvalue()
        output.close()
        
        # Log audit event
        log_audit_event('data_access', 'export_alerts', 'alerts',
                       f"{len(rows)} alerts", user_id,
                       changes={'row_count': len(rows)})
        
        # Return CSV
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=alerts_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
        )
        
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return jsonify({'error': 'Export failed'}), 500

@alerts_bp.route('/stats', methods=['GET'])
@require_auth
def get_alert_stats(user_id: int = None) -> Any:
    """Get alert statistics."""
    # Time range parameter (default: last 24 hours)
    hours = int(request.args.get('hours', 24))
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Total counts by severity
        cur.execute("""
            SELECT 
                severity,
                COUNT(*) as count
            FROM alerts
            WHERE deleted_at IS NULL
            AND timestamp >= NOW() - INTERVAL '%s hours'
            GROUP BY severity
            ORDER BY 
                CASE severity
                    WHEN 'CRITICAL' THEN 1
                    WHEN 'HIGH' THEN 2
                    WHEN 'MEDIUM' THEN 3
                    WHEN 'LOW' THEN 4
                    WHEN 'INFO' THEN 5
                    ELSE 6
                END
        """, (hours,))
        by_severity = [dict(row) for row in cur.fetchall()]
        
        # Counts by status
        cur.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM alerts
            WHERE deleted_at IS NULL
            AND timestamp >= NOW() - INTERVAL '%s hours'
            GROUP BY status
        """, (hours,))
        by_status = [dict(row) for row in cur.fetchall()]
        
        # Top attack types
        cur.execute("""
            SELECT 
                class_name,
                COUNT(*) as count
            FROM alerts
            WHERE deleted_at IS NULL
            AND timestamp >= NOW() - INTERVAL '%s hours'
            GROUP BY class_name
            ORDER BY count DESC
            LIMIT 10
        """, (hours,))
        top_attacks = [dict(row) for row in cur.fetchall()]
        
        # Top source IPs
        cur.execute("""
            SELECT 
                src_ip,
                COUNT(*) as count,
                ARRAY_AGG(DISTINCT class_name) as attack_types
            FROM alerts
            WHERE deleted_at IS NULL
            AND timestamp >= NOW() - INTERVAL '%s hours'
            GROUP BY src_ip
            ORDER BY count DESC
            LIMIT 10
        """, (hours,))
        top_sources = [dict(row) for row in cur.fetchall()]
        
        # Alert trend (hourly buckets)
        cur.execute("""
            SELECT 
                DATE_TRUNC('hour', timestamp) as hour,
                severity,
                COUNT(*) as count
            FROM alerts
            WHERE deleted_at IS NULL
            AND timestamp >= NOW() - INTERVAL '%s hours'
            GROUP BY DATE_TRUNC('hour', timestamp), severity
            ORDER BY hour DESC
        """, (hours,))
        trend = [dict(row) for row in cur.fetchall()]
        
        # MTTA and MTTR
        cur.execute("""
            SELECT 
                AVG(EXTRACT(EPOCH FROM (ah.created_at - a.created_at))) / 60 as mtta_minutes
            FROM alerts a
            JOIN alert_history ah ON a.alert_id = ah.alert_id
            WHERE ah.to_status = 'ACKNOWLEDGED'
            AND a.timestamp >= NOW() - INTERVAL '%s hours'
        """, (hours,))
        mtta_row = cur.fetchone()
        mtta = float(mtta_row['mtta_minutes']) if mtta_row and mtta_row['mtta_minutes'] else None
        
        cur.execute("""
            SELECT 
                AVG(EXTRACT(EPOCH FROM (ah.created_at - a.created_at))) / 60 as mttr_minutes
            FROM alerts a
            JOIN alert_history ah ON a.alert_id = ah.alert_id
            WHERE ah.to_status = 'RESOLVED'
            AND a.timestamp >= NOW() - INTERVAL '%s hours'
        """, (hours,))
        mttr_row = cur.fetchone()
        mttr = float(mttr_row['mttr_minutes']) if mttr_row and mttr_row['mttr_minutes'] else None
        
        cur.close()
        conn.close()
        
        return jsonify({
            'time_range_hours': hours,
            'by_severity': by_severity,
            'by_status': by_status,
            'top_attack_types': top_attacks,
            'top_source_ips': top_sources,
            'trend': trend,
            'metrics': {
                'mtta_minutes': round(mtta, 2) if mtta else None,
                'mttr_minutes': round(mttr, 2) if mttr else None
            }
        })
        
    except Exception as e:
        logger.error(f"Stats query failed: {e}")
        return jsonify({'error': 'Database error'}), 500

# ============================================================================
# SSE Streaming Endpoint
# ============================================================================

@alerts_bp.route('/stream', methods=['GET'])
@require_auth
def stream_alerts(user_id: int = None) -> Any:
    """Server-Sent Events stream for real-time alerts."""
    def event_stream():
        """Generate SSE events."""
        # Import Kafka consumer
        from confluent_kafka import Consumer, KafkaError
        import os
        
        kafka_brokers = os.getenv('KAFKA_BROKERS', 'localhost:9092')
        alerts_topic = os.getenv('ALERTS_TOPIC', 'alerts')
        
        # Create consumer
        consumer = Consumer({
            'bootstrap.servers': kafka_brokers,
            'group.id': f'alerts-sse-{user_id}-{datetime.now().timestamp()}',
            'auto.offset.reset': 'latest',
            'enable.auto.commit': True
        })
        
        consumer.subscribe([alerts_topic])
        
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.now().isoformat()})}\n\n"
            
            # Stream alerts
            while True:
                msg = consumer.poll(timeout=1.0)
                
                if msg is None:
                    # Send heartbeat every second
                    yield f": heartbeat\n\n"
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Kafka error: {msg.error()}")
                        continue
                
                # Parse alert
                try:
                    alert = json.loads(msg.value().decode('utf-8'))
                    yield f"data: {json.dumps({'type': 'alert', 'data': alert})}\n\n"
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode alert: {e}")
                    continue
        
        finally:
            consumer.close()
    
    return Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )

# ============================================================================
# Register Blueprint
# ============================================================================
# This blueprint should be registered in backend/api/app.py:
# from api.routes.alerts import alerts_bp
# app.register_blueprint(alerts_bp)

