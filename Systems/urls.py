from rest_framework_nested import routers
from .views import (
    BlogViewSet, CategoryViewSet, SubcategoryViewSet, ProductViewSet,
    RegisterView, CustomTokenObtainPairView, UserProfileView,
    me_view, register_view, login_view, logout_view, current_user_view,
    CategoryAdminDetailView, SubcategoryAdminDetailView, ProductAdminDetailView,
    ProductDetailView, ProductsBySubcategoryView, ProductRelatedView,
    CustomGoogleOAuth2CallbackView, popular_products, hero_banners, HeroBannerViewSet # ✅ Added hero_banners
)
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView

# Main router
router = routers.DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'subcategories', SubcategoryViewSet, basename='subcategory')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'blogs', BlogViewSet, basename='blog')
router.register(r'hero-banners', HeroBannerViewSet, basename='hero-banners')

# Nested routers
categories_router = routers.NestedDefaultRouter(router, r'categories', lookup='category')
categories_router.register(r'subcategories', SubcategoryViewSet, basename='category-subcategories')

subcategories_router = routers.NestedDefaultRouter(router, r'subcategories', lookup='subcategory')
subcategories_router.register(r'products', ProductViewSet, basename='subcategory-products')

urlpatterns = [
    # -------------------------
    # Authentication endpoints (JWT + Legacy)
    # -------------------------
    path('register/', RegisterView.as_view(), name='register'),
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', UserProfileView.as_view(), name='user_profile'),

    path('auth/register/', register_view, name='legacy_register'),
    path('auth/login/', login_view, name='legacy_login'),
    path('auth/logout/', logout_view, name='legacy_logout'),
    path('auth/user/', current_user_view, name='current_user'),
    
    # ✅ Hero Banners & Popular Products
    path('hero-banners/', hero_banners, name='hero-banners'),
    path('products/popular/', popular_products, name='popular-products'),
    
    # -------------------------
    # Google OAuth override
    # -------------------------
    path(
        'accounts/google/login/callback/',
        CustomGoogleOAuth2CallbackView,
        name='google_oauth2_callback'
    ),

    # -------------------------
    # Routers
    # -------------------------
    path('', include(router.urls)),
    path('', include(categories_router.urls)),
    path('', include(subcategories_router.urls)),

    # -------------------------
    # Slug-based endpoints for public browsing
    # -------------------------
    path(
        'categories/<slug:category_slug>/subcategories/',
        SubcategoryViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='subcategory-by-category-slug'
    ),

    path(
        'categories/<slug:category_slug>/subcategories/<slug:slug>/',
        SubcategoryViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy'
        }),
        name='subcategory-detail-by-slug'
    ),

    # -------------------------
    # Product endpoints
    # -------------------------
    path(
        'subcategories/<slug:subcategory_slug>/products/',
        ProductsBySubcategoryView.as_view(),
        name='products-by-subcategory'
    ),

    path(
        'products/<slug:product_slug>/',
        ProductDetailView.as_view(),
        name='product-detail-contract'
    ),

    path(
        'products/<slug:product_slug>/related/',
        ProductRelatedView.as_view(),
        name='product-related'
    ),

    path(
        'subcategories/<slug:subcategory_slug>/products/create/',
        ProductViewSet.as_view({'post': 'create'}),
        name='product-create-by-subcategory'
    ),

    path('categories/<int:pk>/', CategoryAdminDetailView.as_view(), name='category-admin-detail'),
    path('categories/<slug:category_slug>/subcategories/<int:pk>/', SubcategoryAdminDetailView.as_view(), name='subcategory-admin-detail'),
    path('products/<int:pk>/', ProductAdminDetailView.as_view(), name='product-admin-detail'),
]