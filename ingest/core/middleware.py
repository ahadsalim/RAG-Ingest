"""
Performance monitoring and optimization middleware.
Middleware برای مانیتورینگ و بهینه‌سازی عملکرد
"""

import time
import logging
import json
from django.core.cache import cache
from django.db import connection, reset_queries
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger(__name__)


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """
    Middleware برای مانیتورینگ عملکرد درخواست‌ها
    """
    
    def process_request(self, request):
        """شروع تایمر و ذخیره اطلاعات اولیه"""
        request._start_time = time.time()
        request._start_queries = len(connection.queries)
        
        # Reset queries for this request
        if settings.DEBUG:
            reset_queries()
    
    def process_response(self, request, response):
        """محاسبه و لاگ کردن متریک‌های عملکرد"""
        if not hasattr(request, '_start_time'):
            return response
        
        # Calculate metrics
        duration = time.time() - request._start_time
        query_count = len(connection.queries) - getattr(request, '_start_queries', 0)
        
        # Log slow requests
        if duration > 1.0 or query_count > 50:
            logger.warning(
                f"Slow request: {request.method} {request.path} "
                f"took {duration:.2f}s with {query_count} queries"
            )
            
            if settings.DEBUG and query_count > 50:
                # Log slowest queries
                slow_queries = sorted(
                    connection.queries,
                    key=lambda x: float(x.get('time', 0)),
                    reverse=True
                )[:5]
                
                for i, query in enumerate(slow_queries, 1):
                    logger.debug(
                        f"Slow Query {i}: {query.get('time')}s - "
                        f"{query.get('sql', '')[:200]}"
                    )
        
        # Add performance headers in DEBUG mode
        if settings.DEBUG:
            response['X-DB-Query-Count'] = str(query_count)
            response['X-Response-Time'] = f"{duration:.3f}"
        
        # Update cache statistics
        self._update_stats(duration, query_count)
        
        return response
    
    def _update_stats(self, duration, query_count):
        """به‌روزرسانی آمار عملکرد در cache"""
        try:
            stats_key = 'performance_stats'
            stats = cache.get(stats_key, {
                'total_requests': 0,
                'total_time': 0,
                'total_queries': 0,
                'slow_requests': 0,
            })
            
            stats['total_requests'] += 1
            stats['total_time'] += duration
            stats['total_queries'] += query_count
            
            if duration > 1.0:
                stats['slow_requests'] += 1
            
            cache.set(stats_key, stats, 3600)  # Keep stats for 1 hour
        except Exception as e:
            logger.error(f"Failed to update performance stats: {e}")


class QueryOptimizationMiddleware(MiddlewareMixin):
    """
    Middleware برای بهینه‌سازی خودکار Query ها
    """
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """بهینه‌سازی Query ها قبل از اجرای view"""
        
        # Enable select_related/prefetch_related hints for admin
        if request.path.startswith('/admin/'):
            # This will be picked up by our optimized admin classes
            request.optimize_queries = True
        
        return None


class CacheControlMiddleware(MiddlewareMixin):
    """
    Middleware برای مدیریت cache headers
    """
    
    # Cache durations for different content types
    CACHE_DURATIONS = {
        'api': 60,           # 1 minute for API responses
        'static': 86400,     # 1 day for static files
        'media': 3600,       # 1 hour for media files
        'admin': 0,          # No cache for admin
        'default': 300,      # 5 minutes default
    }
    
    def process_response(self, request, response):
        """اضافه کردن cache headers مناسب"""
        
        # Don't cache if user is authenticated (personalized content)
        if request.user.is_authenticated:
            response['Cache-Control'] = 'private, no-cache'
            return response
        
        # Determine content type
        path = request.path.lower()
        
        if path.startswith('/api/'):
            duration = self.CACHE_DURATIONS['api']
        elif path.startswith('/static/'):
            duration = self.CACHE_DURATIONS['static']
        elif path.startswith('/media/'):
            duration = self.CACHE_DURATIONS['media']
        elif path.startswith('/admin/'):
            duration = self.CACHE_DURATIONS['admin']
        else:
            duration = self.CACHE_DURATIONS['default']
        
        # Set cache headers
        if duration > 0:
            response['Cache-Control'] = f'public, max-age={duration}'
            
            # Add ETag for conditional requests
            import hashlib
            if hasattr(response, 'content'):
                etag = hashlib.md5(response.content).hexdigest()
                response['ETag'] = f'"{etag}"'
        else:
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        
        return response


class DatabaseConnectionPoolMiddleware(MiddlewareMixin):
    """
    Middleware برای مدیریت بهتر connection pool دیتابیس
    """
    
    def process_request(self, request):
        """بررسی سلامت connection"""
        from django.db import connections
        
        for conn in connections.all():
            # Check if connection is usable
            if not conn.is_usable():
                conn.close()
                logger.warning(f"Closed unusable database connection: {conn.alias}")
    
    def process_response(self, request, response):
        """بستن connection های غیرضروری"""
        from django.db import connections
        
        # Close connections that had too many queries
        for conn in connections.all():
            if len(conn.queries) > 100:
                conn.close()
                logger.debug(f"Closed connection {conn.alias} after {len(conn.queries)} queries")
        
        return response


class RateLimitMiddleware(MiddlewareMixin):
    """
    Simple rate limiting middleware
    """
    
    def process_request(self, request):
        """Check rate limits"""
        if not settings.DEBUG:
            # Get client IP
            ip = self.get_client_ip(request)
            
            # Rate limit key
            key = f'rate_limit:{ip}'
            
            # Get current count
            count = cache.get(key, 0)
            
            # Check limit (100 requests per minute)
            if count >= 100:
                return JsonResponse({
                    'error': 'Rate limit exceeded. Please try again later.'
                }, status=429)
            
            # Increment counter
            cache.set(key, count + 1, 60)  # Reset after 1 minute
        
        return None
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class CompressionMiddleware(MiddlewareMixin):
    """
    Middleware برای فشرده‌سازی response های بزرگ
    """
    
    MIN_SIZE = 1024  # Only compress responses larger than 1KB
    
    def process_response(self, request, response):
        """Compress large responses"""
        
        # Check if we should compress
        if not self.should_compress(request, response):
            return response
        
        # Check if client accepts gzip
        ae = request.META.get('HTTP_ACCEPT_ENCODING', '')
        if 'gzip' not in ae.lower():
            return response
        
        # Compress content
        import gzip
        
        if hasattr(response, 'content'):
            compressed_content = gzip.compress(response.content)
            
            # Only use compressed version if it's smaller
            if len(compressed_content) < len(response.content):
                response.content = compressed_content
                response['Content-Encoding'] = 'gzip'
                response['Content-Length'] = str(len(compressed_content))
        
        return response
    
    def should_compress(self, request, response):
        """Determine if response should be compressed"""
        
        # Don't compress if already encoded
        if response.has_header('Content-Encoding'):
            return False
        
        # Check content type
        ct = response.get('Content-Type', '').lower()
        compressible_types = [
            'text/', 'application/json', 'application/javascript',
            'application/xml', 'application/xhtml+xml'
        ]
        
        if not any(t in ct for t in compressible_types):
            return False
        
        # Check size
        if hasattr(response, 'content'):
            if len(response.content) < self.MIN_SIZE:
                return False
        
        return True


# Export middleware classes
__all__ = [
    'PerformanceMonitoringMiddleware',
    'QueryOptimizationMiddleware',
    'CacheControlMiddleware',
    'DatabaseConnectionPoolMiddleware',
    'RateLimitMiddleware',
    'CompressionMiddleware',
]
