from django.http import Http404, HttpResponseRedirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.views.decorators.vary import vary_on_headers
from rest_framework import viewsets, status, serializers, generics, permissions
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, IsAdminUser, AllowAny
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.views import OAuth2CallbackView
import logging
from django.core.cache import cache
from django.conf import settings

from .models import Category, Subcategory, Product, Blog, HeroBanner
from .serializers import (
    CategorySerializer, SubcategorySerializer, ProductSerializer,
    UserRegistrationSerializer, UserProfileSerializer, CustomTokenObtainPairSerializer, BlogSerializer, HeroBannerSerializer
)
from rest_framework.pagination import PageNumberPagination

logger = logging.getLogger(__name__)

# ===============================
# Cache Utility Functions
# ===============================

def invalidate_product_caches(product=None, subcategory=None):
    """
    Invalidate all product-related caches when data changes.
    """
    cache_keys_to_clear = [
        settings.CACHE_KEYS.get('all_products', 'all_products'),
        settings.CACHE_KEYS.get('all_categories', 'all_categories'),
        settings.CACHE_KEYS.get('all_subcategories', 'all_subcategories'),
        'popular_products_list',  # Popular products cache
    ]
    
    if product:
        product_detail_key = settings.CACHE_KEYS.get('product_detail', 'product_detail_{}')
        related_key = settings.CACHE_KEYS.get('related_products', 'related_products_{}')
        subcat_key = settings.CACHE_KEYS.get('products_by_subcategory', 'products_by_subcategory_{}')
        
        cache_keys_to_clear.extend([
            product_detail_key.format(product.slug) if '{}' in product_detail_key else f'product_detail_{product.slug}',
            related_key.format(product.slug) if '{}' in related_key else f'related_products_{product.slug}',
            subcat_key.format(product.subcategory.slug) if '{}' in subcat_key else f'products_by_subcategory_{product.subcategory.slug}',
        ])
    
    if subcategory:
        subcat_key = settings.CACHE_KEYS.get('products_by_subcategory', 'products_by_subcategory_{}')
        cache_keys_to_clear.append(
            subcat_key.format(subcategory.slug) if '{}' in subcat_key else f'products_by_subcategory_{subcategory.slug}'
        )
    
    cache.delete_many(cache_keys_to_clear)
    logger.info(f"Cleared {len(cache_keys_to_clear)} cache keys")


def get_cached_queryset(cache_key, queryset_func, timeout=900):
    """
    Generic function to cache querysets.
    """
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        logger.debug(f"Cache hit for key: {cache_key}")
        return cached_data
    
    data = queryset_func()
    cache.set(cache_key, data, timeout)
    logger.debug(f"Cache miss - stored key: {cache_key}")
    return data


# -------------------------
# Authentication Views
# -------------------------

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            access = refresh.access_token
            return Response({
                'message': 'User created successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                },
                'access': str(access),
                'refresh': str(refresh)
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        
        tokens = serializer.validated_data
        user = serializer.user
        return Response({
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser
            },
            "access": tokens['access'],
            "refresh": tokens['refresh']
        })


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user


# -------------------------
# Social Login Callback
# -------------------------

class CustomGoogleOAuth2CallbackView(OAuth2CallbackView):
    adapter_class = GoogleOAuth2Adapter
    
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated:
            next_url = request.session.get('socialaccount_next_url', '/')
            frontend_url = f"http://localhost:5173{next_url}"
            logger.debug(f"OAuth success, redirecting to: {frontend_url}")
            return HttpResponseRedirect(frontend_url)
        
        logger.debug("OAuth failed, redirecting to login")
        return HttpResponseRedirect("http://localhost:5173/user-login")


# -------------------------
# Popular Products Endpoint
# -------------------------
@api_view(['GET'])
@permission_classes([AllowAny])
def popular_products(request):
    """Returns up to 10 popular products with caching (regardless of stock status)"""
    cache_key = 'popular_products_list'
    
    # Try to get from cache
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        logger.debug(f"Cache hit for popular products")
        return Response(cached_data)
    
    # Fetch from database - NO STATUS FILTER
    try:
        products = Product.objects.filter(
            is_popular=True
            # ✅ Removed status=Product.IN_STOCK filter
        ).select_related('subcategory', 'subcategory__category').order_by('-id')[:10]
        
        serializer = ProductSerializer(
            products, 
            many=True, 
            context={'request': request}
        )
        
        # Cache for 15 minutes
        cache.set(cache_key, serializer.data, 60 * 15)
        logger.debug(f"Cache miss - stored popular products")
        
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"Error fetching popular products: {str(e)}")
        return Response(
            {"error": "Failed to fetch popular products"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# -------------------------
# Category ViewSet
# -------------------------

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('id')
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'
    pagination_class = None

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAdminUser()]

    def perform_create(self, serializer):
        obj = serializer.save()
        invalidate_product_caches()
        return obj

    def perform_update(self, serializer):
        obj = serializer.save()
        invalidate_product_caches()
        return obj

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_product_caches()

    @method_decorator(cache_page(60 * 15))
    @method_decorator(vary_on_headers('Authorization'))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(60 * 15))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        try:
            obj = get_object_or_404(queryset, **{self.lookup_field: self.kwargs[lookup_url_kwarg]})
            self.check_object_permissions(self.request, obj)
            return obj
        except Http404:
            raise serializers.ValidationError({"detail": "Category not found."})


# -------------------------
# Subcategory ViewSet
# -------------------------

class SubcategoryViewSet(viewsets.ModelViewSet):
    queryset = Subcategory.objects.all().order_by('id')
    serializer_class = SubcategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'
    pagination_class = None

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAdminUser()]

    def perform_create(self, serializer):
        category_slug = self.kwargs.get('category_slug')
        category_id = self.kwargs.get('category_pk')
        if category_slug:
            category = get_object_or_404(Category, slug=category_slug)
        elif category_id:
            if str(category_id).isdigit():
                category = get_object_or_404(Category, id=category_id)
            else:
                category = get_object_or_404(Category, slug=category_id)
        else:
            raise serializers.ValidationError({"detail": "Category not specified."})
        obj = serializer.save(category=category)
        invalidate_product_caches()
        return obj

    def perform_update(self, serializer):
        obj = serializer.save()
        invalidate_product_caches()
        return obj

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_product_caches()

    @method_decorator(cache_page(60 * 15))
    @method_decorator(vary_on_headers('Authorization'))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(60 * 15))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        category_slug = self.kwargs.get('category_slug')
        if category_slug:
            category = get_object_or_404(Category, slug=category_slug)
            return queryset.filter(category=category).order_by('id')
        return queryset

    def get_object(self):
        try:
            return super().get_object()
        except Http404:
            raise serializers.ValidationError({"detail": "Subcategory not found."})


# -------------------------
# Product ViewSet
# -------------------------

class DefaultPagination(PageNumberPagination):
    page_size = 40
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('-id')
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]
    lookup_field = 'slug'
    pagination_class = DefaultPagination
    
    def get_permissions(self):
        if self.request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return [IsAdminUser()]
        if self.action == 'list' and self.request.query_params.get('subcategory') is not None:
            return [IsAdminUser()]
        return [AllowAny()]

    def perform_create(self, serializer):
        subcategory_slug = self.kwargs.get('subcategory_slug')
        subcategory_pk = self.kwargs.get('subcategory_pk')
        if subcategory_slug:
            subcategory = get_object_or_404(Subcategory, slug=subcategory_slug)
        elif subcategory_pk:
            if str(subcategory_pk).isdigit():
                subcategory = get_object_or_404(Subcategory, id=subcategory_pk)
            else:
                subcategory = get_object_or_404(Subcategory, slug=subcategory_pk)
        else:
            raise serializers.ValidationError({"detail": "Subcategory not specified."})
        validated_data = serializer.validated_data
        if 'stock' not in validated_data:
            validated_data['stock'] = 1
        if 'status' not in validated_data:
            validated_data['status'] = Product.IN_STOCK
        product = serializer.save(subcategory=subcategory)
        invalidate_product_caches(product=product, subcategory=subcategory)

    def perform_update(self, serializer):
        product = serializer.save()
        invalidate_product_caches(product=product, subcategory=product.subcategory)
        return product

    def perform_destroy(self, instance):
        subcategory = instance.subcategory
        super().perform_destroy(instance)
        invalidate_product_caches(subcategory=subcategory)

    def get_queryset(self):
        queryset = super().get_queryset()
        subcategory_slug = self.kwargs.get('subcategory_slug')
        subcategory_pk = self.kwargs.get('subcategory_pk')
        qp_subcat = self.request.query_params.get('subcategory')
        
        if subcategory_slug:
            subcategory = get_object_or_404(Subcategory, slug=subcategory_slug)
            return queryset.filter(subcategory=subcategory).order_by('-id')
        if subcategory_pk:
            if str(subcategory_pk).isdigit():
                subcategory = get_object_or_404(Subcategory, id=subcategory_pk)
            else:
                subcategory = get_object_or_404(Subcategory, slug=subcategory_pk)
            return queryset.filter(subcategory=subcategory).order_by('-id')
        if qp_subcat:
            if str(qp_subcat).isdigit():
                return queryset.filter(subcategory__id=qp_subcat).order_by('-id')
            return queryset.filter(subcategory__slug=qp_subcat).order_by('-id')
        return queryset

    @method_decorator(cache_page(60 * 15))
    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except Http404:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @action(detail=False, methods=['get'])
    @method_decorator(cache_page(60 * 15))
    def all_categories(self, request):
        """Cached list of all categories"""
        cache_key = settings.CACHE_KEYS.get('all_categories', 'all_categories')
        
        def fetch_categories():
            categories = Category.objects.all().order_by('id')
            serializer = CategorySerializer(categories, many=True, context={'request': request})
            return serializer.data
        
        data = get_cached_queryset(cache_key, fetch_categories)
        return Response(data)

    @action(detail=False, methods=['get'])
    @method_decorator(cache_page(60 * 15))
    def all_subcategories(self, request):
        """Cached list of all subcategories"""
        cache_key = settings.CACHE_KEYS.get('all_subcategories', 'all_subcategories')
        
        def fetch_subcategories():
            subcategories = Subcategory.objects.all().order_by('id')
            serializer = SubcategorySerializer(subcategories, many=True, context={'request': request})
            return serializer.data
        
        data = get_cached_queryset(cache_key, fetch_subcategories)
        return Response(data)

    @action(detail=True, methods=['get'], url_path='related', permission_classes=[AllowAny])
    @method_decorator(cache_page(60 * 15))
    def related(self, request, slug=None):
        """
        Returns cached related products from the same subcategory.
        """
        try:
            product = self.get_object()
            related_key = settings.CACHE_KEYS.get('related_products', 'related_products_{}')
            cache_key = related_key.format(slug) if '{}' in related_key else f'related_products_{slug}'
            
            def fetch_related():
                related_products = Product.objects.filter(
                    subcategory=product.subcategory
                ).exclude(
                    id=product.id
                ).order_by('-id')[:8]
                serializer = self.get_serializer(related_products, many=True)
                return serializer.data
            
            data = get_cached_queryset(cache_key, fetch_related)
            return Response(data)
        except Http404:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)


# -------------------------
# Admin-only PK-based views
# -------------------------

class CategoryAdminDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'pk'
    
    def perform_update(self, serializer):
        obj = serializer.save()
        invalidate_product_caches()
        return obj
    
    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_product_caches()


class SubcategoryAdminDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SubcategorySerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'pk'

    def get_queryset(self):
        category_slug = self.kwargs.get('category_slug')
        category = get_object_or_404(Category, slug=category_slug)
        return Subcategory.objects.filter(category=category).order_by('id')
    
    def perform_update(self, serializer):
        obj = serializer.save()
        invalidate_product_caches()
        return obj
    
    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_product_caches()


class ProductAdminDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx
    
    def perform_update(self, serializer):
        product = serializer.save()
        invalidate_product_caches(product=product, subcategory=product.subcategory)
        return product
    
    def perform_destroy(self, instance):
        subcategory = instance.subcategory
        super().perform_destroy(instance)
        invalidate_product_caches(subcategory=subcategory)


# -------------------------
# Legacy function-based views
# -------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    user = request.user
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')

    if not username or not password:
        return Response({"error": "Username and password are required"}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)

    if email and User.objects.filter(email=email).exists():
        return Response({"error": "Email already exists"}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, email=email or '', password=password)
    refresh = RefreshToken.for_user(user)
    access = refresh.access_token

    return Response({
        "access": str(access),
        "refresh": str(refresh)
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response({"error": "Username and password are required"}, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(username=username, password=password)
    if user is None:
        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

    refresh = RefreshToken.for_user(user)
    access = refresh.access_token

    return Response({
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser
        },
        "access": str(access),
        "refresh": str(refresh)
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    return Response({"message": "Logout successful"})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user_view(request):
    user = request.user
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'date_joined': user.date_joined,
        'last_login': user.last_login,
    })


@login_required
def social_login_success(request):
    return redirect('http://localhost:5173/')


# -------------------------
# Public product endpoints
# -------------------------

class ContractPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100


@method_decorator(cache_page(60 * 15), name='dispatch')
@method_decorator(vary_on_headers('Authorization'), name='dispatch')
class ProductsBySubcategoryView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = ContractPagination

    def get_queryset(self):
        subcategory_slug = self.kwargs.get('subcategory_slug')
        subcat_key = settings.CACHE_KEYS.get('products_by_subcategory', 'products_by_subcategory_{}')
        cache_key = subcat_key.format(subcategory_slug) if '{}' in subcat_key else f'products_by_subcategory_{subcategory_slug}'
        
        def fetch_products():
            return list(Product.objects.filter(
                subcategory__slug=subcategory_slug
            ).order_by('-id'))
        
        return get_cached_queryset(cache_key, fetch_products, timeout=900)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


@method_decorator(cache_page(60 * 15), name='dispatch')
class ProductDetailView(generics.RetrieveAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'
    lookup_url_kwarg = 'product_slug'
    queryset = Product.objects.all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


@method_decorator(cache_page(60 * 15), name='dispatch')
class ProductRelatedView(generics.ListAPIView):
    """
    Returns cached related products from the same subcategory.
    """
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        product_slug = self.kwargs.get('product_slug')
        product = get_object_or_404(Product, slug=product_slug)
        
        related_key = settings.CACHE_KEYS.get('related_products', 'related_products_{}')
        cache_key = related_key.format(product_slug) if '{}' in related_key else f'related_products_{product_slug}'
        
        def fetch_related():
            return list(Product.objects.filter(
                subcategory=product.subcategory
            ).exclude(
                id=product.id
            ).order_by('-id')[:8])
        
        return get_cached_queryset(cache_key, fetch_related, timeout=900)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class BlogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public read-only access to published blogs with caching.
    Now returns ALL published blogs, not just 3.
    """
    queryset = Blog.objects.filter(is_published=True).order_by('-created_at')
    serializer_class = BlogSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    pagination_class = None  # No pagination for blogs

    @method_decorator(cache_page(60 * 15))
    def list(self, request, *args, **kwargs):
        """Returns ALL published blogs"""
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(60 * 15))
    def retrieve(self, request, *args, **kwargs):
        """Returns a single blog by slug"""
        return super().retrieve(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'], url_path='footer')
    @method_decorator(cache_page(60 * 15))
    def footer_blogs(self, request):
        """
        Returns cached latest blogs for footer display.
        Changed from 3 to 10 blogs to allow frontend to control display.
        """
        blogs = self.get_queryset()[:10]  # Get 10 latest blogs instead of 3
        serializer = self.get_serializer(blogs, many=True)
        return Response(serializer.data)

@api_view(['GET'])
@permission_classes([AllowAny])
def hero_banners(request):
    """
    Returns active hero banners with caching.
    Only returns banners where is_active=True, ordered by display_order and creation date.
    Cache timeout: 5 minutes (300 seconds)
    """
    cache_key = 'active_hero_banners'
    
    # Try to get from cache
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        logger.debug(f"Cache hit for hero banners")
        return Response(cached_data)
    
    # Fetch from database
    try:
        banners = HeroBanner.objects.filter(
            is_active=True
        ).order_by('display_order', '-created_at')
        
        serializer = HeroBannerSerializer(
            banners,
            many=True,
            context={'request': request}
        )
        
        # Cache for 5 minutes
        cache.set(cache_key, serializer.data, 60 * 5)
        logger.debug(f"Cache miss - stored hero banners")
        
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(f"Error fetching hero banners: {str(e)}")
        # Return empty array on failure (frontend will use hardcoded slides)
        return Response([], status=status.HTTP_200_OK)

class HeroBannerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HeroBanner.objects.filter(is_active=True)
    serializer_class = HeroBannerSerializer
    permission_classes = [AllowAny]