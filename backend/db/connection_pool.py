"""
backend/db/connection_pool.py
Optimized database connection pooling and query optimization
"""

import os
import logging
from contextlib import contextmanager
from typing import Dict, Any, Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from psycopg2.pool import ThreadedConnectionPool
import threading
import time

logger = logging.getLogger(__name__)

class DatabasePool:
    """Optimized database connection pool with query caching and performance monitoring"""
    
    def __init__(self):
        self.pool = None
        self.query_cache = {}
        self.cache_lock = threading.Lock()
        self.stats = {
            'total_queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_query_time': 0,
            'connection_errors': 0
        }
        self.stats_lock = threading.Lock()
        
    def initialize(self, config: Dict[str, Any]):
        """Initialize connection pool with optimized settings"""
        try:
            # Connection pool configuration
            min_connections = int(os.getenv('DB_POOL_MIN', '5'))
            max_connections = int(os.getenv('DB_POOL_MAX', '20'))
            
            # Connection parameters
            conn_params = {
                'host': config['host'],
                'port': config['port'],
                'dbname': config['dbname'],
                'user': config['user'],
                'password': config['password'],
                # Performance optimizations
                'application_name': 'adaptive_ids_api',
                'tcp_keepalives_idle': 600,
                'tcp_keepalives_interval': 30,
                'tcp_keepalives_count': 3,
                # Connection timeout
                'connect_timeout': 10,
                # Statement timeout (30 seconds)
                'options': '-c statement_timeout=30000',
                # Enable prepared statements
                'prepared_statement_cache_queries': 100,
            }
            
            self.pool = ThreadedConnectionPool(
                min_connections,
                max_connections,
                **conn_params
            )
            
            logger.info(f"Database pool initialized: {min_connections}-{max_connections} connections")
            
            # Test connection
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    logger.info("Database connection test successful")
                    
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Get connection from pool with automatic cleanup"""
        conn = None
        try:
            conn = self.pool.getconn()
            yield conn
        except Exception as e:
            with self.stats_lock:
                self.stats['connection_errors'] += 1
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                self.pool.putconn(conn)
    
    def execute_query(self, query: str, params: tuple = None, fetch: str = 'all', 
                     cache_ttl: int = 0) -> Any:
        """Execute query with caching and performance monitoring"""
        start_time = time.time()
        
        # Check cache if TTL > 0
        cache_key = None
        if cache_ttl > 0:
            cache_key = f"{query}:{params}:{fetch}"
            with self.cache_lock:
                if cache_key in self.query_cache:
                    cached_data, timestamp = self.query_cache[cache_key]
                    if time.time() - timestamp < cache_ttl:
                        with self.stats_lock:
                            self.stats['cache_hits'] += 1
                        logger.debug(f"Cache hit for query: {query[:50]}...")
                        return cached_data
                    else:
                        del self.query_cache[cache_key]
        
        # Execute query
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, params)
                    
                    if fetch == 'all':
                        result = cur.fetchall()
                    elif fetch == 'one':
                        result = cur.fetchone()
                    elif fetch == 'many':
                        result = cur.fetchmany()
                    else:
                        result = None
                    
                    # Cache result if TTL > 0
                    if cache_ttl > 0 and cache_key:
                        with self.cache_lock:
                            self.query_cache[cache_key] = (result, time.time())
                    
                    # Update stats
                    query_time = time.time() - start_time
                    with self.stats_lock:
                        self.stats['total_queries'] += 1
                        self.stats['cache_misses'] += 1
                        # Update rolling average
                        total = self.stats['total_queries']
                        self.stats['avg_query_time'] = (
                            (self.stats['avg_query_time'] * (total - 1) + query_time) / total
                        )
                    
                    logger.debug(f"Query executed in {query_time:.3f}s: {query[:50]}...")
                    return result
                    
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def execute_batch(self, query: str, params_list: List[tuple]) -> None:
        """Execute batch insert/update for better performance"""
        start_time = time.time()
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    execute_values(cur, query, params_list, page_size=1000)
                    
            query_time = time.time() - start_time
            logger.info(f"Batch query executed in {query_time:.3f}s: {len(params_list)} records")
            
        except Exception as e:
            logger.error(f"Batch query execution failed: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database pool statistics"""
        with self.stats_lock:
            stats = self.stats.copy()
        
        # Add cache info
        with self.cache_lock:
            stats['cache_size'] = len(self.query_cache)
        
        # Add pool info
        if self.pool:
            stats['pool_size'] = self.pool.maxconn
            stats['pool_used'] = self.pool.maxconn - len(self.pool._pool)
        
        return stats
    
    def clear_cache(self):
        """Clear query cache"""
        with self.cache_lock:
            self.query_cache.clear()
        logger.info("Query cache cleared")
    
    def close(self):
        """Close all connections in pool"""
        if self.pool:
            self.pool.closeall()
            logger.info("Database pool closed")

# Global pool instance
db_pool = DatabasePool()

def initialize_db_pool(config: Dict[str, Any]):
    """Initialize the global database pool"""
    db_pool.initialize(config)

def get_db_pool() -> DatabasePool:
    """Get the global database pool instance"""
    return db_pool

# Optimized query helpers
class QueryOptimizer:
    """Helper class for optimized database queries"""
    
    @staticmethod
    def build_alert_query(filters: Dict[str, Any], page: int = 1, per_page: int = 10) -> tuple:
        """Build optimized alert query with proper indexing"""
        where_clauses = []
        params = []
        
        # Use indexes for common filters
        if filters.get('priority'):
            where_clauses.append("priority = %s")
            params.append(filters['priority'])
        
        if filters.get('status'):
            where_clauses.append("status = %s")
            params.append(filters['status'])
        
        if filters.get('src_ip'):
            where_clauses.append("src_ip = %s")
            params.append(filters['src_ip'])
        
        if filters.get('dst_ip'):
            where_clauses.append("dst_ip = %s")
            params.append(filters['dst_ip'])
        
        if filters.get('start_time'):
            where_clauses.append("timestamp >= %s")
            params.append(filters['start_time'])
        
        if filters.get('end_time'):
            where_clauses.append("timestamp <= %s")
            params.append(filters['end_time'])
        
        # Build query with proper ordering and limits
        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # Use timestamp index for ordering
        query = f"""
            SELECT alert_id, priority, description, source, timestamp, status, 
                   alert_type, confidence, severity, class_name, class_idx, 
                   src_ip, dst_ip, src_port, dst_port, protocol, 
                   model_version, feature_version, assigned_to, notes
            FROM alerts{where_sql}
            ORDER BY timestamp DESC
            LIMIT %s OFFSET %s
        """
        
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        
        return query, tuple(params)
    
    @staticmethod
    def build_dashboard_stats_query() -> str:
        """Build optimized dashboard stats query"""
        return """
            SELECT 
                COUNT(*) as total_alerts,
                COUNT(*) FILTER (WHERE priority = 'critical') as critical_alerts,
                COUNT(*) FILTER (WHERE status IN ('open', 'investigating')) as open_incidents,
                (SELECT COUNT(*) FROM incidents) as total_incidents
            FROM alerts
        """
