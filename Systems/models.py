from django.db import models
from django.utils.text import slugify
import cloudinary
import cloudinary.uploader
from cloudinary.models import CloudinaryField

class Category(models.Model):
    FIRE_SAFETY = 'fire_safety'
    ICT = 'ict'
    SOLAR = 'solar'
    CATEGORY_TYPES = [
        (FIRE_SAFETY, 'Fire Safety'),
        (ICT, 'ICT'),
        (SOLAR, 'Solar')
    ]

    name = models.CharField(max_length=255)
    type = models.CharField(max_length=50, choices=[('fire_safety', 'Fire Safety'), ('ict', 'ICT'), ('solar', 'Solar')], default='fire_safety')
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"

class Subcategory(models.Model):
    category = models.ForeignKey(Category, related_name='subcategories', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Subcategory.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.category.name})"

class Product(models.Model):
    # Price visibility choices
    PUBLIC = 'public'
    LOGIN_REQUIRED = 'login_required'
    PRICE_VISIBILITY_CHOICES = [
        (PUBLIC, 'Public'),
        (LOGIN_REQUIRED, 'Login Required'),
    ]

    # Stock status choices - simplified to only two values
    IN_STOCK = 'in_stock'
    OUT_OF_STOCK = 'out_of_stock'
    STOCK_STATUS_CHOICES = [
        (IN_STOCK, 'In Stock'),
        (OUT_OF_STOCK, 'Out of Stock'),
    ]

    subcategory = models.ForeignKey(Subcategory, related_name='products', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    
    # Brand and SKU fields for better product identification
    brand = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Product brand (e.g., Eaton, Apollo, Giganet)"
    )
    sku = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Stock Keeping Unit / Model Number (e.g., EFCP-123)"
    )

    # ✅ FIXED: Single is_popular field (removed duplicate)
    is_popular = models.BooleanField(
        default=False,
        help_text="Mark this product as popular to feature it on the homepage carousel"
    )
    
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_visibility = models.CharField(
        max_length=20, 
        choices=PRICE_VISIBILITY_CHOICES, 
        default=PUBLIC,
        help_text="Choose who can see the price of this product"
    )
    description = models.TextField(blank=True)
    features = models.TextField(blank=True)
    
    # Use CloudinaryField for proper Cloudinary integration
    image = CloudinaryField('image', null=True, blank=True, folder='products')
    
    slug = models.SlugField(unique=True, blank=True)
    documentation = models.URLField(blank=True, null=True, help_text="Enter the URL for the product datasheet")
    documentation_label = models.CharField(max_length=255, blank=True, help_text="Display text for the documentation link (e.g., 'View Datasheet', 'Technical Specs')")
    
    # Updated status field with proper choices and default
    status = models.CharField(
        max_length=20, 
        choices=STOCK_STATUS_CHOICES, 
        default=IN_STOCK,
        help_text="Stock availability status"
    )
    stock = models.PositiveIntegerField(default=0, help_text="Number of items in stock")

    # SEO FIELDS (optional overrides)
    meta_title = models.CharField(
        max_length=60, 
        blank=True, 
        null=True,
        help_text="Custom SEO title (max 60 chars). Leave blank for auto-generated title."
    )
    meta_description = models.CharField(
        max_length=155, 
        blank=True, 
        null=True,
        help_text="Custom SEO description (max 155 chars). Leave blank for auto-generated description."
    )

    def save(self, *args, **kwargs):
        # Auto-generate slug from name if not provided
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        # Auto-set stock status based on stock quantity
        if self.stock > 0:
            self.status = self.IN_STOCK
        else:
            self.status = self.OUT_OF_STOCK
            
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def is_in_stock(self):
        """Helper property to check if product is in stock"""
        return self.status == self.IN_STOCK and self.stock > 0

class SpecificationTable(models.Model):
    """
    Each product can have multiple specification tables.
    Each table can have multiple rows.
    """
    product = models.ForeignKey(Product, related_name='spec_tables', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.title or 'Untitled Table'} - {self.product.name}"

class SpecificationRow(models.Model):
    """
    Each row belongs to one SpecificationTable.
    Rows are stored as key/value pairs.
    Example:
    key="Model", value="Eaton Addressable fire detector"
    """
    table = models.ForeignKey(SpecificationTable, related_name='rows', on_delete=models.CASCADE)
    key = models.CharField(max_length=255, blank=True, null=True)
    value = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.key}: {self.value}"
    
class Blog(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    excerpt = models.TextField()
    content = models.TextField()
    image = models.ImageField(upload_to='blogs/', blank=True, null=True, default='blogs/default.jpeg')
    source_name = models.CharField(max_length=100, blank=True, null=True)
    source_url = models.URLField(blank=True, null=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Blog.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class HeroBanner(models.Model):
    """
    Hero Banner / Promotional Poster Model
    Supports both standard hero slides and full-width promotional posters
    """
    STANDARD = 'standard'
    POSTER = 'poster'
    DISPLAY_MODE_CHOICES = [
        (STANDARD, 'Standard Hero Slide'),
        (POSTER, 'Poster Only'),
    ]
    
    THREE_IMAGES = 'three_images'
    TWO_IMAGES = 'two_images'
    SINGLE_IMAGE = 'single_image'
    LAYOUT_CHOICES = [
        (THREE_IMAGES, 'Three Images'),
        (TWO_IMAGES, 'Two Images'),
        (SINGLE_IMAGE, 'Single Image'),
    ]
    
    # Campaign Information
    campaign_name = models.CharField(
        max_length=255,
        help_text="Internal name for this campaign (e.g., 'Black Friday 2024')"
    )
    display_mode = models.CharField(
        max_length=20,
        choices=DISPLAY_MODE_CHOICES,
        default=STANDARD,
        help_text="Choose between standard hero slide or promotional poster"
    )
    
    # Scheduling
    is_active = models.BooleanField(
        default=False,
        help_text="Toggle to show/hide this banner on the website"
    )
    display_order = models.IntegerField(
        default=0,
        help_text="Lower numbers appear first (e.g., 0 appears before 1)"
    )
    start_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Optional: Auto-activate banner on this date"
    )
    end_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Optional: Auto-deactivate banner after this date"
    )
    
    # Poster Mode Fields
    poster_image = CloudinaryField(
        'poster',
        null=True,
        blank=True,
        folder='hero_banners/posters',
        help_text="Full-width promotional poster image (for Poster mode)"
    )
    poster_link = models.URLField(
        blank=True,
        null=True,
        help_text="Optional clickable link for the poster (e.g., /category/fire-alarms)"
    )
    
    # Standard Mode Content
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Main heading (for Standard mode)"
    )
    subtitle = models.CharField(
        max_length=255,
        blank=True,
        help_text="Small text above title (for Standard mode)"
    )
    description = models.TextField(
        blank=True,
        help_text="Hero description text (for Standard mode)"
    )
    button_text = models.CharField(
        max_length=100,
        blank=True,
        default="Explore Products",
        help_text="CTA button text (for Standard mode)"
    )
    button_link = models.CharField(
        max_length=500,
        blank=True,
        help_text="CTA button link (for Standard mode)"
    )
    
    # Standard Mode Images
    image_1 = CloudinaryField(
        'image_1',
        null=True,
        blank=True,
        folder='hero_banners/standard',
        help_text="First product image (for Standard mode)"
    )
    image_2 = CloudinaryField(
        'image_2',
        null=True,
        blank=True,
        folder='hero_banners/standard',
        help_text="Second product image (for Standard mode)"
    )
    image_3 = CloudinaryField(
        'image_3',
        null=True,
        blank=True,
        folder='hero_banners/standard',
        help_text="Third product image (for Standard mode)"
    )
    
    # Layout and Styling
    layout = models.CharField(
        max_length=20,
        choices=LAYOUT_CHOICES,
        default=THREE_IMAGES,
        help_text="Image layout for Standard mode"
    )
    background_class = models.CharField(
        max_length=50,
        blank=True,
        default='heroSlide1',
        help_text="CSS class for background styling (e.g., heroSlide1, heroSlide2)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', '-created_at']
        verbose_name = 'Hero Banner / Promotional Poster'
        verbose_name_plural = 'Hero Banners / Promotional Posters'
    
    def clean(self):
        """Validate that required fields are present based on display mode"""
        if self.display_mode == self.POSTER:
            if not self.poster_image:
                raise ValidationError({
                    'poster_image': 'Poster image is required for Poster mode.'
                })
        elif self.display_mode == self.STANDARD:
            if not self.title:
                raise ValidationError({
                    'title': 'Title is required for Standard mode.'
                })
            if not self.image_1:
                raise ValidationError({
                    'image_1': 'At least one image is required for Standard mode.'
                })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        status = "LIVE" if self.is_active else "INACTIVE"
        return f"[{status}] {self.campaign_name} ({self.get_display_mode_display()})"