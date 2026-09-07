from django.contrib.sitemaps import Sitemap
from .models import Product, Blog


class ProductSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9
    
    def items(self):
        return Product.objects.all()
    
    def lastmod(self, obj):
        return obj.updated_at


class BlogSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7
    
    def items(self):
        return Blog.objects.filter(is_published=True)
    
    def lastmod(self, obj):
        return obj.updated_at