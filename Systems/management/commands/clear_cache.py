"""
Django management command for cache operations.
Place this in: Systems/management/commands/clear_cache.py

Usage:
    python manage.py clear_cache --all
    python manage.py clear_cache --products
    python manage.py clear_cache --check
    python manage.py clear_cache --warm
"""

from django.core.management.base import BaseCommand
from django.core.cache import cache
from Systems.models import Product, Category, Subcategory
from Systems.serializers import ProductSerializer, CategorySerializer, SubcategorySerializer
import time


class Command(BaseCommand):
    help = 'Manage Django cache system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Clear all caches',
        )
        parser.add_argument(
            '--products',
            action='store_true',
            help='Clear product-related caches only',
        )
        parser.add_argument(
            '--check',
            action='store_true',
            help='Check cache health',
        )
        parser.add_argument(
            '--warm',
            action='store_true',
            help='Warm up caches with fresh data',
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show cache statistics',
        )

    def handle(self, *args, **options):
        if options['all']:
            self.clear_all_cache()
        elif options['products']:
            self.clear_product_cache()
        elif options['check']:
            self.check_cache()
        elif options['warm']:
            self.warm_caches()
        elif options['stats']:
            self.show_stats()
        else:
            self.stdout.write(
                self.style.WARNING('Please specify an option. Use --help for details.')
            )

    def clear_all_cache(self):
        """Clear entire cache."""
        self.stdout.write('Clearing all caches...')
        start = time.time()
        cache.clear()
        elapsed = time.time() - start
        self.stdout.write(
            self.style.SUCCESS(f'✓ All caches cleared in {elapsed:.3f}s')
        )

    def clear_product_cache(self):
        """Clear product-related caches."""
        self.stdout.write('Clearing product caches...')
        start = time.time()
        
        # List of product-related cache keys
        keys_to_clear = [
            'products:all',
            'categories:all',
            'subcategories:all',
        ]
        
        deleted = cache.delete_many(keys_to_clear)
        elapsed = time.time() - start
        
        self.stdout.write(
            self.style.SUCCESS(f'✓ Cleared {deleted} product cache keys in {elapsed:.3f}s')
        )

    def check_cache(self):
        """Check if cache is working."""
        self.stdout.write('Checking cache health...')
        
        test_key = 'cache_health_check'
        test_value = 'working'
        
        try:
            # Test write
            cache.set(test_key, test_value, 60)
            self.stdout.write('  ✓ Write test passed')
            
            # Test read
            cached_value = cache.get(test_key)
            if cached_value == test_value:
                self.stdout.write('  ✓ Read test passed')
            else:
                self.stdout.write(
                    self.style.ERROR('  ✗ Read test failed')
                )
                return
            
            # Test delete
            cache.delete(test_key)
            self.stdout.write('  ✓ Delete test passed')
            
            self.stdout.write(
                self.style.SUCCESS('\n✓ Cache is healthy!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Cache check failed: {e}')
            )

    def warm_caches(self):
        """Pre-populate caches with fresh data."""
        self.stdout.write('Warming up caches...')
        start = time.time()
        
        # Warm up categories
        self.stdout.write('  Loading categories...')
        categories = Category.objects.all().order_by('id')
        cache.set('categories:all', list(categories), 900)
        self.stdout.write(f'    ✓ Cached {categories.count()} categories')
        
        # Warm up subcategories
        self.stdout.write('  Loading subcategories...')
        subcategories = Subcategory.objects.all().order_by('id')
        cache.set('subcategories:all', list(subcategories), 900)
        self.stdout.write(f'    ✓ Cached {subcategories.count()} subcategories')
        
        # Warm up products (first 100)
        self.stdout.write('  Loading products...')
        products = Product.objects.all().order_by('-id')[:100]
        cache.set('products:recent', list(products), 900)
        self.stdout.write(f'    ✓ Cached {products.count()} recent products')
        
        elapsed = time.time() - start
        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Caches warmed in {elapsed:.3f}s')
        )

    def show_stats(self):
        """Show cache statistics."""
        from django.conf import settings
        
        self.stdout.write('\nCache Configuration:')
        self.stdout.write('-' * 50)
        
        cache_config = settings.CACHES['default']
        self.stdout.write(f"Backend: {cache_config['BACKEND']}")
        self.stdout.write(f"Location: {cache_config.get('LOCATION', 'N/A')}")
        self.stdout.write(f"Timeout: {cache_config.get('TIMEOUT', 'N/A')}s")
        
        if 'OPTIONS' in cache_config:
            self.stdout.write('\nOptions:')
            for key, value in cache_config['OPTIONS'].items():
                self.stdout.write(f"  {key}: {value}")
        
        self.stdout.write('\nCache Keys:')
        self.stdout.write('-' * 50)
        if hasattr(settings, 'CACHE_KEYS'):
            for key, pattern in settings.CACHE_KEYS.items():
                self.stdout.write(f"  {key}: {pattern}")
        
        self.stdout.write('\nDatabase Stats:')
        self.stdout.write('-' * 50)
        self.stdout.write(f"Total Products: {Product.objects.count()}")
        self.stdout.write(f"Total Categories: {Category.objects.count()}")
        self.stdout.write(f"Total Subcategories: {Subcategory.objects.count()}")