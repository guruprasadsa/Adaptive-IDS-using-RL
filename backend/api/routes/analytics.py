"""
Analytics API Routes
Provides network traffic analytics, attack trends, and statistical insights
"""

from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request

analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')

# Define a dummy decorator if auth not available
def require_auth(f):
    return f

def require_permission(permission):
    def decorator(f):
        return f
    return decorator

# Import DatabaseService from main app (container module path is api.app)
def get_db_service():
    """Get database service instance"""
    from api.app import DatabaseService
    return DatabaseService()


def parse_time_range(time_range: str) -> datetime:
    """Convert time range string to datetime"""
    now = datetime.utcnow()
    
    if time_range == '1h':
        return now - timedelta(hours=1)
    elif time_range == '6h':
        return now - timedelta(hours=6)
    elif time_range == '24h':
        return now - timedelta(hours=24)
    elif time_range == '7d':
        return now - timedelta(days=7)
    elif time_range == '30d':
        return now - timedelta(days=30)
    else:
        return now - timedelta(hours=24)  # Default to 24h


@analytics_bp.route('/summary', methods=['GET'])
@require_auth
@require_permission('view_alerts')
def get_analytics_summary():
    """
    Get analytics summary statistics
    
    Query Params:
        time_range: 1h, 6h, 24h, 7d, 30d (default: 24h)
    
    Returns:
        JSON with total_alerts, critical_alerts, attack_types, unique_ips
    """
    try:
        time_range = request.args.get('time_range', '24h')
        start_time = parse_time_range(time_range)
        
        db_service = get_db_service()
        with db_service.cursor() as cur:
            # Total alerts in time range
            cur.execute(
                "SELECT COUNT(*) AS count FROM alerts WHERE timestamp >= %s",
                (start_time,)
            )
            total_alerts = int(cur.fetchone()["count"]) or 0

            # Critical alerts (normalize severity/priority)
            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM alerts
                WHERE timestamp >= %s
                  AND UPPER(COALESCE(severity, priority, 'INFO')) = 'CRITICAL'
                """,
                (start_time,)
            )
            critical_alerts = int(cur.fetchone()["count"]) or 0

            # Unique attack types (distinct class_name)
            cur.execute(
                "SELECT COUNT(DISTINCT class_name) AS count FROM alerts WHERE timestamp >= %s",
                (start_time,)
            )
            attack_types = int(cur.fetchone()["count"]) or 0

            # Unique source IPs
            cur.execute(
                "SELECT COUNT(DISTINCT src_ip) AS count FROM alerts WHERE timestamp >= %s",
                (start_time,)
            )
            unique_ips = int(cur.fetchone()["count"]) or 0
        
        return jsonify({
            'total_alerts': total_alerts,
            'critical_alerts': critical_alerts,
            'attack_types': attack_types,
            'unique_ips': unique_ips
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/top-attacks', methods=['GET'])
@require_auth
@require_permission('view_alerts')
def get_top_attacks():
    """
    Get top attack types with counts and percentages
    
    Query Params:
        time_range: 1h, 6h, 24h, 7d, 30d (default: 24h)
        limit: number of results (default: 10)
    
    Returns:
        JSON array of {name, count, percentage}
    """
    try:
        time_range = request.args.get('time_range', '24h')
        limit = int(request.args.get('limit', 10))
        start_time = parse_time_range(time_range)
        
        db_service = get_db_service()
        with db_service.cursor() as cur:
            # Get total count for percentage calculation
            cur.execute(
                "SELECT COUNT(*) AS count FROM alerts WHERE timestamp >= %s",
                (start_time,)
            )
            total = int(cur.fetchone()["count"]) or 1

            # Query attack types with counts
            cur.execute(
                """
                SELECT COALESCE(NULLIF(class_name, ''), 'Unknown') AS class_name, COUNT(*) AS count
                FROM alerts
                WHERE timestamp >= %s
                GROUP BY COALESCE(NULLIF(class_name, ''), 'Unknown')
                ORDER BY count DESC
                LIMIT %s
                """,
                (start_time, limit)
            )
            results = cur.fetchall()
            
            # Format response
            top_attacks = [
                {
                    'name': result['class_name'] or 'Unknown',
                    'count': result['count'],
                    'percentage': round((result['count'] / total) * 100, 1)
                }
                for result in results
            ]
        
        return jsonify(top_attacks), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/top-source-ips', methods=['GET'])
@require_auth
@require_permission('view_alerts')
def get_top_source_ips():
    """
    Get top attacking source IPs with counts and max severity
    
    Query Params:
        time_range: 1h, 6h, 24h, 7d, 30d (default: 24h)
        limit: number of results (default: 10)
    
    Returns:
        JSON array of {ip, count, severity}
    """
    try:
        time_range = request.args.get('time_range', '24h')
        limit = int(request.args.get('limit', 10))
        start_time = parse_time_range(time_range)
        
        db_service = get_db_service()
        with db_service.cursor() as cur:
            # Query source IPs with counts and max severity normalized
            cur.execute(
                """
                SELECT src_ip,
                       COUNT(*) AS count,
                       MAX(UPPER(COALESCE(severity, priority, 'INFO'))) AS max_severity
                FROM alerts
                WHERE timestamp >= %s
                GROUP BY src_ip
                ORDER BY count DESC
                LIMIT %s
                """,
                (start_time, limit)
            )
            results = cur.fetchall()
            
            # Format response
            top_source_ips = [
                {
                    'ip': result['src_ip'] or 'Unknown',
                    'count': result['count'],
                    'severity': result['max_severity'] or 'LOW'
                }
                for result in results
            ]
        
        return jsonify(top_source_ips), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/top-dest-ips', methods=['GET'])
@require_auth
@require_permission('view_alerts')
def get_top_dest_ips():
    """
    Get most targeted destination IPs with counts and protocol
    
    Query Params:
        time_range: 1h, 6h, 24h, 7d, 30d (default: 24h)
        limit: number of results (default: 10)
    
    Returns:
        JSON array of {ip, count, protocol}
    """
    try:
        time_range = request.args.get('time_range', '24h')
        limit = int(request.args.get('limit', 10))
        start_time = parse_time_range(time_range)
        
        db_service = get_db_service()
        with db_service.cursor() as cur:
            # Query destination IPs with counts
            cur.execute(
                """
                SELECT dst_ip, COUNT(*) AS count, MAX(protocol) AS protocol
                FROM alerts
                WHERE timestamp >= %s
                GROUP BY dst_ip
                ORDER BY count DESC
                LIMIT %s
                """,
                (start_time, limit)
            )
            results = cur.fetchall()
            
            # Format response
            top_dest_ips = [
                {
                    'ip': result['dst_ip'] or 'Unknown',
                    'count': result['count'],
                    'protocol': result['protocol'] or 'TCP'
                }
                for result in results
            ]
        
        return jsonify(top_dest_ips), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/severity-distribution', methods=['GET'])
@require_auth
@require_permission('view_alerts')
def get_severity_distribution():
    """
    Get alert severity distribution with counts and percentages
    
    Query Params:
        time_range: 1h, 6h, 24h, 7d, 30d (default: 24h)
    
    Returns:
        JSON array of {severity, count, percentage}
    """
    try:
        time_range = request.args.get('time_range', '24h')
        start_time = parse_time_range(time_range)
        
        db_service = get_db_service()
        with db_service.cursor() as cur:
            # Get total count for percentage calculation
            cur.execute(
                "SELECT COUNT(*) AS count FROM alerts WHERE timestamp >= %s",
                (start_time,)
            )
            total = int(cur.fetchone()["count"]) or 1

            # Query severity distribution (normalize severity/priority)
            cur.execute(
                """
                SELECT UPPER(COALESCE(severity, priority, 'INFO')) AS sev, COUNT(*) AS count
                FROM alerts
                WHERE timestamp >= %s
                GROUP BY UPPER(COALESCE(severity, priority, 'INFO'))
                """,
                (start_time,)
            )
            results = cur.fetchall()

            # Create severity map
            severity_map = {result['sev']: result['count'] for result in results}

            # Format response with predefined order
            severity_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
            distribution = [
                {
                    'severity': severity.title(),
                    'count': severity_map.get(severity, 0),
                    'percentage': round((severity_map.get(severity, 0) / total) * 100, 1)
                }
                for severity in severity_order
                if severity_map.get(severity, 0) > 0
            ]
        
        return jsonify(distribution), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/trends', methods=['GET'])
@require_auth
@require_permission('view_alerts')
def get_alert_trends():
    """
    Get time-series alert trends
    
    Query Params:
        time_range: 1h, 6h, 24h, 7d, 30d (default: 24h)
        interval: 5m, 15m, 1h, 6h, 1d (default: based on time_range)
    
    Returns:
        JSON array of {time, count}
    """
    try:
        time_range = request.args.get('time_range', '24h')
        start_time = parse_time_range(time_range)
        
        db_service = get_db_service()
        with db_service.cursor() as cur:
            # Query alerts grouped by hour
            cur.execute(
                """
                SELECT DATE_TRUNC('hour', timestamp) AS time_bucket, COUNT(*) AS count
                FROM alerts
                WHERE timestamp >= %s
                GROUP BY time_bucket
                ORDER BY time_bucket
                """,
                (start_time,)
            )
            results = cur.fetchall()
            
            # Format response
            trends = [
                {
                    'time': result['time_bucket'].isoformat() if result['time_bucket'] else None,
                    'count': result['count']
                }
                for result in results
            ]
        
        return jsonify(trends), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
