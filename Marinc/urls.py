from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from django.contrib.sitemaps.views import sitemap
from Systems.sitemaps import ProductSitemap, BlogSitemap

# Sitemap configuration
sitemaps = {
    'products': ProductSitemap,
    'blogs': BlogSitemap,
}

auth_urlpatterns = [
    # Django REST Framework browsable API auth (login/logout buttons in DRF UI)
    path('api/auth/', include('rest_framework.urls')),

    # Built-in Django auth views (session-based, HTML forms)
    path('api/login/', auth_views.LoginView.as_view(), name='drf_api_login'),   # renamed
    path('api/logout/', auth_views.LogoutView.as_view(), name='drf_api_logout'), # renamed

    # Web login/logout/register pages
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        redirect_field_name='next'
    ), name='web_login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='web_logout'),
    path('register/', TemplateView.as_view(template_name='registration/register.html'), name='web_register'),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('Systems.urls')),  # include your app's API urls
    path('', include(auth_urlpatterns)),    # include auth urls
    path('accounts/', include('allauth.urls')),
    
    # Sitemap at root level
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django-sitemap'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)