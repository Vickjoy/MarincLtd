from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from django.conf import settings
from .models import Category, Subcategory, Product, SpecificationTable, SpecificationRow, Blog, HeroBanner
import os


# -----------------------------
# USER AUTHENTICATION SERIALIZERS
# -----------------------------
class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'first_name', 'last_name')

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser', 'date_joined')
        read_only_fields = ('id', 'is_staff', 'is_superuser', 'date_joined')


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'username'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'] = serializers.CharField()
        self.fields['password'] = serializers.CharField()

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        user = None
        if '@' in username:
            try:
                user_obj = User.objects.get(email=username)
                username = user_obj.username
            except User.DoesNotExist:
                pass

        attrs['username'] = username
        return super().validate(attrs)


# -----------------------------
# CATEGORY/SUBCATEGORY SERIALIZERS
# -----------------------------
class SubcategoryMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subcategory
        fields = ['id', 'name', 'slug']


class CategorySerializer(serializers.ModelSerializer):
    subcategories = SubcategoryMiniSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'type', 'slug', 'subcategories']


class CategoryMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']


class SubcategorySerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Subcategory
        fields = ['id', 'name', 'slug', 'category']


# -----------------------------
# SPECIFICATION SERIALIZERS
# -----------------------------
class SpecificationRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecificationRow
        fields = ['key', 'value']


class SpecificationTableSerializer(serializers.ModelSerializer):
    rows = SpecificationRowSerializer(many=True, read_only=True)

    class Meta:
        model = SpecificationTable
        fields = ['title', 'rows']


# -----------------------------
# PRODUCT SERIALIZER (with SEO fields + Brand + SKU)
# -----------------------------
class ProductSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    price_requires_login = serializers.SerializerMethodField()
    subcategory = serializers.PrimaryKeyRelatedField(
        queryset=Subcategory.objects.all(),
        required=True,
        write_only=True
    )
    subcategory_detail = SubcategoryMiniSerializer(source='subcategory', read_only=True)
    category = serializers.SerializerMethodField(read_only=True)
    spec_tables = SpecificationTableSerializer(many=True, read_only=True)
    subcategory_slug = serializers.SerializerMethodField()
    category_slug = serializers.SerializerMethodField()
    documentation_url = serializers.SerializerMethodField()
    documentation_label = serializers.SerializerMethodField()
    features = serializers.CharField(required=False, allow_blank=True)
    status = serializers.SerializerMethodField()
    
    # ✅ NEW: Brand and SKU fields
    brand = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    sku = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    # SEO fields
    meta_title = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    meta_description = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'price', 'price_visibility', 'price_requires_login',
            'description', 'features', 'image',
            'spec_tables', 'documentation', 'documentation_url', 'documentation_label',
            'status', 'stock', 'subcategory', 'subcategory_detail',
            'category', 'slug', 'subcategory_slug', 'category_slug',
            'brand', 'sku', 'is_popular',
            'meta_title', 'meta_description'
        ]

    # -----------------------------
    # PRICE VISIBILITY LOGIC
    # -----------------------------
    def get_price(self, obj):
        request = self.context.get('request')
        user_is_auth = bool(request and getattr(request, 'user', None) and request.user.is_authenticated)
        if obj.price_visibility == Product.LOGIN_REQUIRED and not user_is_auth:
            return None
        return float(obj.price) if obj.price is not None else 0.00

    def get_price_requires_login(self, obj):
        request = self.context.get('request')
        user_is_auth = bool(request and getattr(request, 'user', None) and request.user.is_authenticated)
        if obj.price_visibility == Product.LOGIN_REQUIRED and not user_is_auth:
            return True
        return False

    # -----------------------------
    # IMAGE URL HANDLING (CLOUDINARY)
    # -----------------------------
    def get_image(self, obj):
        if not obj.image:
            return None

        CLOUD_NAME = getattr(settings, 'CLOUDINARY_STORAGE', {}).get('CLOUD_NAME', '')
        FOLDER = getattr(settings, 'CLOUDINARY_STORAGE', {}).get('FOLDER', 'products')

        try:
            if hasattr(obj.image, 'url'):
                return obj.image.url
            if hasattr(obj.image, 'build_url'):
                return obj.image.build_url()

            image_str = str(obj.image)
            if image_str.startswith('http://') or image_str.startswith('https://'):
                return image_str

            # Old images (public_id only)
            return f"https://res.cloudinary.com/{CLOUD_NAME}/image/upload/{FOLDER}/{image_str}"

        except Exception as e:
            print(f"Error getting image URL for {obj.name}: {e}")
            return None

    # -----------------------------
    # SLUG AND CATEGORY HELPERS
    # -----------------------------
    def get_subcategory_slug(self, obj):
        return obj.subcategory.slug if obj.subcategory else None

    def get_category_slug(self, obj):
        return obj.subcategory.category.slug if obj.subcategory and obj.subcategory.category else None

    def get_documentation_url(self, obj):
        return obj.documentation if obj.documentation else None

    def get_documentation_label(self, obj):
        if obj.documentation:
            if obj.documentation_label:
                return obj.documentation_label
            else:
                from urllib.parse import urlparse
                try:
                    parsed_url = urlparse(obj.documentation)
                    filename = os.path.basename(parsed_url.path)
                    filename_without_ext = os.path.splitext(filename)[0]
                    return filename_without_ext if filename_without_ext.strip() else "View Documentation"
                except:
                    return "View Documentation"
        return None

    def get_category(self, obj):
        if obj.subcategory and obj.subcategory.category:
            return CategoryMiniSerializer(obj.subcategory.category).data
        return None

    def get_status(self, obj):
        return obj.status

class BlogSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    
    class Meta:
        model = Blog
        fields = ['id', 'title', 'slug', 'image', 'content', 'excerpt', 
                  'source_name', 'source_url', 'created_at', 'updated_at', 'is_published']
        read_only_fields = ['slug', 'created_at', 'updated_at']

    def get_image(self, obj):
        if not obj.image:
            return None
        
        CLOUD_NAME = getattr(settings, 'CLOUDINARY_STORAGE', {}).get('CLOUD_NAME', '')
        
        try:
            if hasattr(obj.image, 'url'):
                return obj.image.url
            if hasattr(obj.image, 'build_url'):
                return obj.image.build_url()
            
            image_str = str(obj.image)
            if image_str.startswith('http://') or image_str.startswith('https://'):
                return image_str
            
            return f"https://res.cloudinary.com/{CLOUD_NAME}/image/upload/blogs/{image_str}"
        except Exception as e:
            print(f"Error getting blog image URL: {e}")
            return None

class HeroBannerSerializer(serializers.ModelSerializer):
    """
    Serializer for Hero Banners with Cloudinary URL handling
    """
    poster_image = serializers.SerializerMethodField()
    image_1 = serializers.SerializerMethodField()
    image_2 = serializers.SerializerMethodField()
    image_3 = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    
    class Meta:
        model = HeroBanner
        fields = [
            'id',
            'display_mode',
            'campaign_name',
            'title',
            'subtitle',
            'description',
            'button_text',
            'button_link',
            'poster_image',
            'poster_link',
            'image_1',
            'image_2',
            'image_3',
            'images',
            'layout',
            'background_class',
        ]
    
    def _get_cloudinary_url(self, cloudinary_field):
        """
        Helper method to safely extract Cloudinary URL from CloudinaryField
        """
        if not cloudinary_field:
            return None
        
        CLOUD_NAME = getattr(settings, 'CLOUDINARY_STORAGE', {}).get('CLOUD_NAME', '')
        
        try:
            # Try URL attribute first
            if hasattr(cloudinary_field, 'url'):
                return cloudinary_field.url
            
            # Try build_url method
            if hasattr(cloudinary_field, 'build_url'):
                return cloudinary_field.build_url()
            
            # Handle string representation
            image_str = str(cloudinary_field)
            if image_str.startswith('http://') or image_str.startswith('https://'):
                return image_str
            
            # Construct Cloudinary URL manually
            return f"https://res.cloudinary.com/{CLOUD_NAME}/image/upload/{image_str}"
            
        except Exception as e:
            print(f"Error getting Cloudinary URL: {e}")
            return None
    
    def get_poster_image(self, obj):
        """Get poster image URL"""
        return self._get_cloudinary_url(obj.poster_image)
    
    def get_image_1(self, obj):
        """Get first image URL"""
        return self._get_cloudinary_url(obj.image_1)
    
    def get_image_2(self, obj):
        """Get second image URL"""
        return self._get_cloudinary_url(obj.image_2)
    
    def get_image_3(self, obj):
        """Get third image URL"""
        return self._get_cloudinary_url(obj.image_3)
    
    def get_images(self, obj):
        """
        Return array of image URLs based on display mode
        - Poster mode: returns [poster_image]
        - Standard mode: returns [image_1, image_2, image_3] (non-null only)
        """
        if obj.display_mode == 'poster':
            poster_url = self._get_cloudinary_url(obj.poster_image)
            return [poster_url] if poster_url else []
        
        # Standard mode - return all non-null images
        images = []
        for img_field in [obj.image_1, obj.image_2, obj.image_3]:
            url = self._get_cloudinary_url(img_field)
            if url:
                images.append(url)
        
        return images