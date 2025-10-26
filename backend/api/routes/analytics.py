"""
Analytics API Routes
Provides network traffic analytics, attack trends, and statistical insights
"""

from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from sqlalchemy import func, desc
from backend.db.models import Alert, db
from backend.api.middleware.auth_middleware import require_auth, require_permission

analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')


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
        
        # Total alerts in time range
        total_alerts = db.session.query(func.count(Alert.id)).filter(
            Alert.timestamp >= start_time
        ).scalar() or 0
        
        # Critical alerts (HIGH severity)
        critical_alerts = db.session.query(func.count(Alert.id)).filter(
            Alert.timestamp >= start_time,
            Alert.priority == 'HIGH'
        ).scalar() or 0
        
        # Unique attack types (distinct predictions)
        attack_types = db.session.query(func.count(func.distinct(Alert.prediction))).filter(
            Alert.timestamp >= start_time
        ).scalar() or 0
        
        # Unique source IPs
        unique_ips = db.session.query(func.count(func.distinct(Alert.source))).filter(
            Alert.timestamp >= start_time
        ).scalar() or 0
        
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
        
        # Get total count for percentage calculation
        total = db.session.query(func.count(Alert.id)).filter(
            Alert.timestamp >= start_time
        ).scalar() or 1  # Avoid division by zero
        
        # Query attack types with counts
        results = db.session.query(
            Alert.prediction,
            func.count(Alert.id).label('count')
        ).filter(
            Alert.timestamp >= start_time
        ).group_by(
            Alert.prediction
        ).order_by(
            desc('count')
        ).limit(limit).all()
        
        # Format response
        top_attacks = [
            {
                'name': result[0] or 'Unknown',
                'count': result[1],
                'percentage': round((result[1] / total) * 100, 1)
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
        
        # Query source IPs with counts and max severity
        results = db.session.query(
            Alert.source,
            func.count(Alert.id).label('count'),
            func.max(Alert.priority).label('max_severity')
        ).filter(
            Alert.timestamp >= start_time
        ).group_by(
            Alert.source
        ).order_by(
            desc('count')
        ).limit(limit).all()
        
        # Format response
        top_source_ips = [
            {
                'ip': result[0] or 'Unknown',
                'count': result[1],
                'severity': result[2] or 'LOW'
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
        
        # Query destination IPs with counts
        # Note: Protocol info might be in metadata or description
        results = db.session.query(
            Alert.destination,
            func.count(Alert.id).label('count')
        ).filter(
            Alert.timestamp >= start_time
        ).group_by(
            Alert.destination
        ).order_by(
            desc('count')
        ).limit(limit).all()
        
        # Format response (protocol detection would need metadata parsing)
        top_dest_ips = [
            {
                'ip': result[0] or 'Unknown',
                'count': result[1],
                'protocol': 'TCP'  # Default, could be enhanced with metadata parsing
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
        
        # Get total count for percentage calculation
        total = db.session.query(func.count(Alert.id)).filter(
            Alert.timestamp >= start_time
        ).scalar() or 1  # Avoid division by zero
        
        # Query severity distribution
        results = db.session.query(
            Alert.priority,
            func.count(Alert.id).label('count')
        ).filter(
            Alert.timestamp >= start_time
        ).group_by(
            Alert.priority
        ).all()
        
        # Format response with predefined order
        severity_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
        severity_map = {result[0]: result[1] for result in results}
        
        distribution = [
            {
                'severity': severity,
                'count': severity_map.get(severity, 0),
                'percentage': round((severity_map.get(severity, 0) / total) * 100, 1)
            }
            for severity in severity_order
            if severity_map.get(severity, 0) > 0  # Only include severities with data
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
        
        # Determine interval based on time range
        interval = request.args.get('interval')
        if not interval:
            if time_range in ['1h', '6h']:
                interval = '15m'
            elif time_range == '24h':
                interval = '1h'
            else:
                interval = '6h'
        
        # Convert interval to minutes for SQL
        interval_minutes = {
            '5m': 5,
            '15m': 15,
            '1h': 60,
            '6h': 360,
            '1d': 1440
        }.get(interval, 60)
        
        # Query alerts grouped by time intervals
        # Using PostgreSQL's date_trunc for time bucketing
        results = db.session.query(
            func.date_trunc('hour', Alert.timestamp).label('time_bucket'),
            func.count(Alert.id).label('count')
        ).filter(
            Alert.timestamp >= start_time
        ).group_by(
            'time_bucket'
        ).order_by(
            'time_bucket'
        ).all()
        
        # Format response
        trends = [
            {
                'time': result[0].isoformat() if result[0] else None,
                'count': result[1]
            }
            for result in results
        ]
        
        return jsonify(trends), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
