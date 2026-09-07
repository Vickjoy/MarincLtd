"""
Cache utility functions for Django backend.
Place this file in your Systems app directory.
"""

from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def get_cache_key(key_template, *args):
    """
    Generate cache key from template.
    
    Example:
        get_cache_key('product:detail:{}', 'laptop-stand')
        # Returns: 'product:detail:laptop-stand'
    """
    try:
        return key_template.format(*args) if args else key_template
    except (KeyError, IndexError) as e:
        logger.error(f"Error generating cache key: {e}")
        return None


def invalidate_all_product_caches():
    """
    Clear all product-related caches.
    Use this when making bulk changes.
    """
    try:
        cache.clear()
        logger.info("All caches cleared successfully")
        return True
    except Exception as e:
        logger.error(f"Error clearing all caches: {e}")
        return False


def invalidate_specific_caches(cache_keys):
    """
    Clear specific cache keys.
    
    Args:
        cache_keys: List of cache keys to invalidate
    
    Example:
        invalidate_specific_caches([
            'products:all',
            'product:detail:laptop-stand'
        ])
    """
    try:
        deleted = cache.delete_many(cache_keys)
        logger.info(f"Cleared {deleted} cache keys")
        return deleted
    except Exception as e:
        logger.error(f"Error clearing specific caches: {e}")
        return 0


def warm_cache(cache_key, data_func, timeout=900):
    """
    Pre-populate cache with data.
    
    Args:
        cache_key: Key to store data under
        data_func: Function that returns data to cache
        timeout: Cache timeout in seconds (default 15 minutes)
    
    Example:
        def get_all_products():
            return Product.objects.all()
        
        warm_cache('products:all', get_all_products)
    """
    try:
        data = data_func()
        cache.set(cache_key, data, timeout)
        logger.info(f"Cache warmed for key: {cache_key}")
        return True
    except Exception as e:
        logger.error(f"Error warming cache for {cache_key}: {e}")
        return False


def get_or_set_cache(cache_key, data_func, timeout=900):
    """
    Get data from cache or set it if not present.
    
    Args:
        cache_key: Key to look up
        data_func: Function to call if cache miss
        timeout: Cache timeout in seconds
    
    Returns:
        Cached or freshly generated data
    """
    data = cache.get(cache_key)
    
    if data is not None:
        logger.debug(f"Cache hit: {cache_key}")
        return data
    
    logger.debug(f"Cache miss: {cache_key}")
    data = data_func()
    cache.set(cache_key, data, timeout)
    return data


def check_cache_health():
    """
    Check if cache system is working.
    Returns dict with status information.
    """
    test_key = 'cache_health_check'
    test_value = 'working'
    
    try:
        # Test write
        cache.set(test_key, test_value, 60)
        
        # Test read
        cached_value = cache.get(test_key)
        
        # Test delete
        cache.delete(test_key)
        
        is_working = cached_value == test_value
        
        return {
            'status': 'healthy' if is_working else 'unhealthy',
            'backend': settings.CACHES['default']['BACKEND'],
            'working': is_working
        }
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'working': False
        }


def get_cache_stats():
    """
    Get basic cache statistics (if supported by backend).
    Note: LocMemCache has limited stats support.
    """
    try:
        # This works with some cache backends
        return {
            'backend': settings.CACHES['default']['BACKEND'],
            'location': settings.CACHES['default'].get('LOCATION', 'N/A'),
            'timeout': settings.CACHES['default'].get('TIMEOUT', 'N/A'),
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {'error': str(e)}


# Django management command helpers

def clear_product_cache_by_slug(product_slug):
    """Clear all caches related to a specific product."""
    keys_to_clear = [
        settings.CACHE_KEYS['product_detail'].format(product_slug),
        settings.CACHE_KEYS['related_products'].format(product_slug),
    ]
    return invalidate_specific_caches(keys_to_clear)


def clear_subcategory_cache_by_slug(subcategory_slug):
    """Clear all caches related to a specific subcategory."""
    keys_to_clear = [
        settings.CACHE_KEYS['products_by_subcategory'].format(subcategory_slug),
    ]
    return invalidate_specific_caches(keys_to_clear)