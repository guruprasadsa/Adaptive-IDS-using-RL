"""
Incidents API Routes
Manage security incidents, status updates, and alert correlation
"""

import math
import uuid
import json
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from functools import wraps

# Import database models
try:
    from backend.db.models import db, Incident, Alert
    DB_AVAILABLE = True
except ImportError:
    try:
        from db.models import db, Incident, Alert
        DB_AVAILABLE = True
    except ImportError:
        DB_AVAILABLE = False

# Import auth decorators
try:
    from api.auth import require_auth
    SECURITY_AVAILABLE = True
except ImportError:
    try:
        from backend.api.auth import require_auth
        SECURITY_AVAILABLE = True
    except ImportError:
        SECURITY_AVAILABLE = False
        def require_auth(f):
            return f

# Define require_permission decorator
def require_permission(permission: str):
    """Decorator to check user permissions"""
    def decorator(f):
        if not SECURITY_AVAILABLE:
            return f
        # For now, just pass through (permissions check can be added later)
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get user_id from kwargs (set by require_auth)
            user_id = kwargs.get('user_id')
            if user_id:
                # Store user info in request for access in route
                request.user_id = user_id
                # Fetch user details if needed
                try:
                    with get_db_cursor() as cur:
                        cur.execute(
                            "SELECT id, username, email, role FROM users WHERE id = %s",
                            (user_id,)
                        )
                        user_row = cur.fetchone()
                        if user_row:
                            request.current_user = dict(user_row)
                except Exception:
                    request.current_user = {'id': user_id, 'username': 'Unknown'}
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Import database cursor utility
try:
    from api.auth import get_db_cursor
except ImportError:
    try:
        from backend.api.auth import get_db_cursor
    except ImportError:
        from contextlib import contextmanager
        import psycopg2
        from psycopg2.extras import RealDictCursor
        import os
        
        @contextmanager
        def get_db_cursor():
            """Context manager for database connections"""
            connection = psycopg2.connect(
                host=os.getenv('POSTGRES_HOST', 'localhost'),
                port=int(os.getenv('POSTGRES_PORT', '55432')),
                dbname=os.getenv('POSTGRES_DB', 'adaptive_ids'),
                user=os.getenv('POSTGRES_USER', 'adaptive_ids'),
                password=os.getenv('POSTGRES_PASSWORD', 'adaptive@ids.1234'),
            )
            try:
                with connection.cursor(cursor_factory=RealDictCursor) as cur:
                    yield cur
                    connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

incidents_bp = Blueprint('incidents', __name__, url_prefix='/api/incidents')


@incidents_bp.route('', methods=['GET'])
@require_auth
@require_permission('view_incidents')
def get_incidents(user_id=None):
    """
    Get paginated list of incidents with optional filters
    
    Query Parameters:
        page: int - Page number (default: 1)
        per_page: int - Items per page (default: 10)
        severity: str - Filter by severity (critical, high, medium, low)
        status: str - Filter by status (open, investigating, contained, resolved)
        search: str - Search in title and description
        sort_by: str - Sort column (default: last_updated_at)
        sort_order: str - Sort order (asc, desc, default: desc)
    
    Returns:
        200: Paginated incidents list
        500: Server error
    """
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        per_page = min(per_page, 100)  # Max 100 items per page
        
        # Get filter parameters
        severity_filter = request.args.get('severity', '')
        status_filter = request.args.get('status', '')
        search = request.args.get('search', '').strip()
        
        # Get sort parameters
        sort_by = request.args.get('sort_by', 'last_updated_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Validate sort column
        allowed_sort_columns = ['incident_id', 'title', 'severity', 'status', 'created_at', 'last_updated_at']
        if sort_by not in allowed_sort_columns:
            sort_by = 'last_updated_at'
        
        # Build WHERE clauses
        where_clauses = []
        params = []
        
        if severity_filter and severity_filter.lower() in ['critical', 'high', 'medium', 'low']:
            where_clauses.append("severity = %s")
            params.append(severity_filter.lower())
        
        if status_filter and status_filter.lower() in ['open', 'investigating', 'contained', 'resolved']:
            where_clauses.append("status = %s")
            params.append(status_filter.lower())
        
        if search:
            where_clauses.append("(LOWER(title) LIKE %s OR LOWER(description) LIKE %s OR LOWER(incident_id) LIKE %s)")
            search_pattern = f'%{search.lower()}%'
            params.extend([search_pattern, search_pattern, search_pattern])
        
        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # Get total count and rows using DB cursor context manager
        with get_db_cursor() as cursor:
            count_query = f"SELECT COUNT(*) AS count FROM incidents{where_sql}"
            cursor.execute(count_query, params)
            total = cursor.fetchone()['count']
            
            # Build main query with sorting and pagination
            offset = (page - 1) * per_page
            sort_sql = f"ORDER BY {sort_by} {'ASC' if sort_order == 'asc' else 'DESC'}"
            
            main_query = f"""
                SELECT incident_id, title, description, severity, status, assigned_to, 
                       created_at, last_updated_at, summary, affected_systems, alerts_count, related_alerts
                FROM incidents
                {where_sql}
                {sort_sql}
                LIMIT %s OFFSET %s
            """
            
            query_params = params + [per_page, offset]
            cursor.execute(main_query, query_params)
            rows = cursor.fetchall()
        
        # Format incidents
        incidents = []
        for row in rows:
            incidents.append({
                'id': row['incident_id'],
                'title': row['title'],
                'description': row['description'] or '',
                'summary': row.get('summary', ''),
                'severity': row['severity'] or 'medium',
                'status': row['status'] or 'open',
                'assignedTo': row['assigned_to'] or 'Unassigned',
                'createdAt': row['created_at'].isoformat() if row['created_at'] else None,
                'lastUpdatedAt': row['last_updated_at'].isoformat() if row['last_updated_at'] else None,
                'relatedAlerts': row['related_alerts'] or [],
                'affectedSystems': row.get('affected_systems', 0) or 0,
                'alertsCount': row.get('alerts_count', 0) or 0
            })
        
        return jsonify({
            'incidents': incidents,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': math.ceil(total / per_page) if per_page > 0 else 0
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@incidents_bp.route('', methods=['POST'])
@require_auth
@require_permission('create_incidents')
def create_incident(user_id=None):
    """
    Create a new security incident using direct DB insert (psycopg2)
    to avoid reliance on uninitialized SQLAlchemy app context.

    Request Body:
        title: str - Incident title
        description: str - Detailed description
        severity: str - critical, high, medium, low
        alert_ids: list[str] - Related alert IDs (optional)
        assigned_to: str - Username/email (optional)

    Returns:
        201: Created incident
        400: Validation error
        500: Server error
    """
    try:
        data = request.get_json(force=True, silent=True) or {}

        # Validate required fields
        title = (data.get('title') or '').strip()
        description = (data.get('description') or '').strip()
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        if not description:
            return jsonify({'error': 'Description is required'}), 400

        severity = (data.get('severity') or 'medium').lower()
        if severity not in ['critical', 'high', 'medium', 'low']:
            return jsonify({'error': 'Invalid severity level'}), 400

        # Generate incident ID
        incident_id = f"INC-{uuid.uuid4().hex[:12].upper()}"

        # Determine assignee (default to current user if available)
        current_user = getattr(request, 'current_user', None)
        if current_user and isinstance(current_user, dict):
            assigned_to = data.get('assigned_to') or current_user.get('username') or 'Unassigned'
        else:
            assigned_to = data.get('assigned_to') or 'Unassigned'

        # Related alerts handling: accept provided IDs; verify existence best-effort
        alert_ids = data.get('alert_ids') or []
        valid_alert_ids = []
        if isinstance(alert_ids, list) and alert_ids:
            try:
                with get_db_cursor() as cur:
                    cur.execute(
                        "SELECT alert_id FROM alerts WHERE alert_id = ANY(%s)",
                        (alert_ids,)
                    )
                    rows = cur.fetchall() or []
                    valid_alert_ids = [row['alert_id'] for row in rows]
            except Exception:
                # Non-fatal; fall back to using provided IDs
                valid_alert_ids = [a for a in alert_ids if isinstance(a, str)]
        alerts_count = len(valid_alert_ids)

        # Insert incident (store lowercase status/severity for consistency with other endpoints)
        summary = data.get('summary') or f"Security incident: {title}"
        affected_systems = int(data.get('affected_systems') or 0)

        with get_db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO incidents (
                    incident_id, title, status, severity, assigned_to,
                    created_at, last_updated_at, summary, description,
                    affected_systems, alerts_count, related_alerts
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    NOW(), NOW(), %s, %s,
                    %s, %s, %s::jsonb
                )
                RETURNING incident_id, title, status, severity, assigned_to, created_at, last_updated_at, alerts_count
                """,
                (
                    incident_id,
                    title,
                    'open',
                    severity,
                    assigned_to,
                    summary,
                    description,
                    affected_systems,
                    alerts_count,
                    json.dumps(valid_alert_ids)
                ),
            )
            row = cur.fetchone()

        return jsonify({
            'id': row['incident_id'],
            'title': row['title'],
            'status': row['status'],
            'severity': row['severity'],
            'assigned_to': row['assigned_to'],
            'created_at': row['created_at'].isoformat() if row['created_at'] else None,
            'updated_at': row['last_updated_at'].isoformat() if row['last_updated_at'] else None,
            'alerts_count': row['alerts_count'],
            'message': 'Incident created successfully'
        }), 201

    except Exception as e:
        import traceback, json as _json
        try:
            # Ensure any open transaction is rolled back if using SQLAlchemy context elsewhere
            if DB_AVAILABLE:
                db.session.rollback()
        except Exception:
            pass
        print(f"Error creating incident: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'Failed to create incident: {str(e)}'}), 500


@incidents_bp.route('/<incident_id>', methods=['GET'])
@require_auth
@require_permission('view_incidents')
def get_incident(incident_id: str, user_id=None):
    """
    Get a specific incident by ID
    
    Returns:
        200: Incident details
        404: Incident not found
    """
    try:
        incident = Incident.query.filter_by(incident_id=incident_id).first()
        
        if not incident:
            return jsonify({'error': 'Incident not found'}), 404
        
        # Get related alerts details
        related_alerts = []
        if incident.related_alerts and isinstance(incident.related_alerts, list):
            alerts = Alert.query.filter(Alert.alert_id.in_(incident.related_alerts)).all()
            related_alerts = [{
                'id': alert.alert_id,
                'type': alert.class_name,
                'severity': alert.severity,
                'timestamp': alert.timestamp.isoformat(),
                'srcIp': alert.src_ip,
                'dstIp': alert.dst_ip,
                'description': f"{alert.class_name} - {alert.src_ip} -> {alert.dst_ip}"
            } for alert in alerts]
        
        return jsonify({
            'id': incident.incident_id,
            'title': incident.title,
            'description': incident.description,
            'summary': incident.summary,
            'severity': incident.severity.lower(),
            'status': incident.status.lower(),
            'assignedTo': incident.assigned_to,
            'createdAt': incident.created_at.isoformat(),
            'lastUpdatedAt': incident.last_updated_at.isoformat(),
            'relatedAlertIds': incident.related_alerts if isinstance(incident.related_alerts, list) else [],
            'relatedAlerts': related_alerts,
            'alertsCount': incident.alerts_count,
            'affectedSystems': incident.affected_systems or 0
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@incidents_bp.route('/<incident_id>/status', methods=['PATCH'])
@require_auth
@require_permission('update_incidents')
def update_incident_status(incident_id: str, user_id=None):
    """
    Update incident status
    
    Request Body:
        status: str - open, investigating, contained, resolved
        notes: str - Optional status update notes
    
    Returns:
        200: Updated incident
        404: Incident not found
        400: Invalid status
    """
    try:
        incident = Incident.query.filter_by(incident_id=incident_id).first()
        
        if not incident:
            return jsonify({'error': 'Incident not found'}), 404
        
        data = request.json
        new_status = data.get('status', '').upper()
        
        valid_statuses = ['OPEN', 'INVESTIGATING', 'CONTAINED', 'RESOLVED']
        if new_status not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        
        incident.status = new_status
        incident.last_updated_at = datetime.now(timezone.utc)
        
        # Optional: Add notes/comments (would require comments table)
        notes = data.get('notes')
        if notes:
            # For now, append to description or implement comments table
            incident.description += f"\n\n[{datetime.now(timezone.utc).isoformat()}] Status updated to {new_status}: {notes}"
        
        db.session.commit()
        
        return jsonify({
            'id': incident.incident_id,
            'status': incident.status,
            'last_updated_at': incident.last_updated_at.isoformat(),
            'message': 'Incident status updated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@incidents_bp.route('/<incident_id>/assign', methods=['PATCH'])
@require_auth
@require_permission('update_incidents')
def assign_incident(incident_id: str, user_id=None):
    """
    Assign incident to a user
    
    Request Body:
        assigned_to: str - Username or email
    
    Returns:
        200: Updated incident
        404: Incident not found
    """
    try:
        incident = Incident.query.filter_by(incident_id=incident_id).first()
        
        if not incident:
            return jsonify({'error': 'Incident not found'}), 404
        
        data = request.json
        assigned_to = data.get('assigned_to')
        
        if not assigned_to:
            return jsonify({'error': 'assigned_to is required'}), 400
        
        incident.assigned_to = assigned_to
        incident.last_updated_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        return jsonify({
            'id': incident.incident_id,
            'assigned_to': incident.assigned_to,
            'last_updated_at': incident.last_updated_at.isoformat(),
            'message': f'Incident assigned to {assigned_to}'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@incidents_bp.route('/<incident_id>/alerts', methods=['POST'])
@require_auth
@require_permission('update_incidents')
def link_alerts_to_incident(incident_id: str, user_id=None):
    """
    Link alerts to an incident
    
    Request Body:
        alert_ids: list[str] - Alert IDs to link
    
    Returns:
        200: Updated incident
        404: Incident not found
    """
    try:
        incident = Incident.query.filter_by(incident_id=incident_id).first()
        
        if not incident:
            return jsonify({'error': 'Incident not found'}), 404
        
        data = request.json
        alert_ids = data.get('alert_ids', [])
        
        if not alert_ids:
            return jsonify({'error': 'alert_ids array is required'}), 400
        
        # Verify alerts exist
        alerts = Alert.query.filter(Alert.alert_id.in_(alert_ids)).all()
        valid_alert_ids = [alert.alert_id for alert in alerts]
        
        # Get current related alerts
        current_alerts = incident.related_alerts if isinstance(incident.related_alerts, list) else []
        
        # Add new alerts (avoid duplicates)
        updated_alerts = list(set(current_alerts + valid_alert_ids))
        
        incident.related_alerts = updated_alerts
        incident.alerts_count = len(updated_alerts)
        incident.last_updated_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        return jsonify({
            'id': incident.incident_id,
            'related_alerts': incident.related_alerts,
            'alerts_count': incident.alerts_count,
            'message': f'{len(valid_alert_ids)} alerts linked to incident'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@incidents_bp.route('/<incident_id>/alerts/<alert_id>', methods=['DELETE'])
@require_auth
@require_permission('update_incidents')
def unlink_alert_from_incident(incident_id: str, alert_id: str, user_id=None):
    """
    Unlink an alert from an incident
    
    Returns:
        200: Alert unlinked
        404: Incident not found
    """
    try:
        incident = Incident.query.filter_by(incident_id=incident_id).first()
        
        if not incident:
            return jsonify({'error': 'Incident not found'}), 404
        
        # Remove alert from related_alerts
        current_alerts = incident.related_alerts if isinstance(incident.related_alerts, list) else []
        
        if alert_id in current_alerts:
            current_alerts.remove(alert_id)
            incident.related_alerts = current_alerts
            incident.alerts_count = len(current_alerts)
            incident.last_updated_at = datetime.now(timezone.utc)
            
            db.session.commit()
            
            return jsonify({
                'id': incident.incident_id,
                'message': f'Alert {alert_id} unlinked from incident'
            }), 200
        else:
            return jsonify({'error': 'Alert not linked to this incident'}), 404
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
