from django.contrib import admin
from django.utils.safestring import mark_safe
from import_export.admin import ImportExportModelAdmin
from django.utils.html import format_html
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from .models import Category, Subcategory, Product, SpecificationTable, SpecificationRow, Blog, HeroBanner
from allauth.socialaccount.models import SocialApp
from django.core.cache import cache

admin.site.unregister(SocialApp)

# Register your custom admin
@admin.register(SocialApp)
class CustomSocialAppAdmin(admin.ModelAdmin):
    list_display = ('provider', 'name', 'client_id')
    filter_horizontal = ('sites',)

# Inlines for nested specifications
class SpecificationRowInline(admin.TabularInline):
    model = SpecificationRow
    extra = 1

class SpecificationTableInline(admin.StackedInline):
    model = SpecificationTable
    extra = 1
    show_change_link = True
    inlines = [SpecificationRowInline]

class SubcategoryInline(admin.TabularInline):
    model = Subcategory
    extra = 1

class ProductInline(admin.TabularInline):
    model = Product
    extra = 1

# Category Admin
class CategoryAdmin(admin.ModelAdmin):
    inlines = [SubcategoryInline]
    list_display = ('name', 'type', 'slug')
    readonly_fields = ('slug',)

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('slug',)
        return self.readonly_fields

# Subcategory Admin
class SubcategoryAdmin(admin.ModelAdmin):
    inlines = [ProductInline]
    list_display = ('name', 'category', 'slug')
    list_filter = ('category',)
    readonly_fields = ('slug',)

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('slug',)
        return self.readonly_fields

# Import-export resource for products
class ProductResource(resources.ModelResource):
    category = fields.Field(column_name='category')
    subcategory = fields.Field(column_name='subcategory')

    class Meta:
        model = Product
        import_id_fields = ['slug']
        fields = (
            'name', 'brand', 'sku', 'price', 'price_visibility', 'description', 'documentation', 'documentation_label',
            'status', 'stock', 'image', 'slug', 'subcategory', 'category',
            'meta_title', 'meta_description'
        )
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        category_name = row.get('category')
        subcategory_name = row.get('subcategory')

        try:
            category = Category.objects.get(name=category_name)
            subcategory = Subcategory.objects.get(name=subcategory_name, category=category)
            row['subcategory'] = subcategory.pk
        except Category.DoesNotExist:
            raise Exception(f"Category '{category_name}' does not exist.")
        except Subcategory.DoesNotExist:
            raise Exception(f"Subcategory '{subcategory_name}' under '{category_name}' not found.")

# Product Admin with Brand and SKU
class ProductAdmin(ImportExportModelAdmin):
    resource_class = ProductResource
    inlines = [SpecificationTableInline]
    
    # ✅ Updated list_display with brand and sku
    list_display = ('name', 'brand', 'sku', 'subcategory', 'get_category', 'price', 'price_visibility', 'status', 'stock','is_popular', 'image_preview', 'documentation_preview', 'has_seo')
    
    # ✅ Updated list_filter to include brand
    list_filter = ('price_visibility', 'status', 'brand','is_popular', 'subcategory__category')
    
    # ✅ Updated search_fields to include brand and sku
    search_fields = ('name', 'brand', 'sku', 'description')
    
    readonly_fields = ('get_category', 'image_preview', 'slug')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'brand', 'sku', 'subcategory'),
            'description': 'Product identification: name, brand (e.g., Eaton, Apollo), and SKU/model number'
        }),
        ('Inventory', {
            'fields': ('stock', 'status'),
            'description': 'Stock quantity and availability status. Status is auto-updated based on stock.'
        }),
        ('Pricing', {
            'fields': ('price', 'price_visibility'),
            'description': 'Set the price and choose who can see it.'
        }),
        ('Content', {
            'fields': ('description', 'features', 'image')
        }),
        ('Documentation', {
            'fields': ('documentation', 'documentation_label'),
            'description': 'Enter the URL for the product datasheet and the text to display for the link.'
        }),
        ('SEO (Search Engine Optimization)', {
            'fields': ('meta_title', 'meta_description'),
            'description': 'Optional: Override auto-generated SEO tags. Leave blank to use automatic generation.',
            'classes': ('collapse',)
        }),

        ('Featured Products', {
            'fields': ('is_popular',),
            'description': 'Mark this product to display in the homepage popular products carousel',
            'classes': ('collapse',)
        })
    )

    def get_category(self, obj):
        return obj.subcategory.category if obj.subcategory else None
    get_category.short_description = 'Category'

    def has_seo(self, obj):
        """Show if product has custom SEO set"""
        if obj.meta_title or obj.meta_description:
            return mark_safe('<span style="color: green;">✓ Custom</span>')
        return mark_safe('<span style="color: gray;">Auto</span>')
    has_seo.short_description = 'SEO'

    def image_preview(self, obj):
        if obj.image:
            try:
                # Use the CloudinaryField's URL method
                if hasattr(obj.image, 'url'):
                    image_url = obj.image.url
                elif hasattr(obj.image, 'build_url'):
                    image_url = obj.image.build_url()
                else:
                    # Fallback for string representations
                    image_str = str(obj.image)
                    if image_str.startswith('http'):
                        image_url = image_str
                    else:
                        image_url = f'https://res.cloudinary.com/ddwpy1x3v/{image_str}'
                
                return mark_safe(f'<img src="{image_url}" style="width: 50px; height: 50px; object-fit: cover;" />')
            except Exception as e:
                return f"Image Error: {str(e)}"
        return "No Image"
    image_preview.short_description = 'Image Preview'

    def documentation_preview(self, obj):
        if obj.documentation:
            label = obj.documentation_label or 'View Documentation'
            return mark_safe(f'<a href="{obj.documentation}" target="_blank">{label}</a>')
        return "No Documentation"
    documentation_preview.short_description = 'Documentation'

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('slug',)
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        """Override save to ensure slug is generated and status is properly set"""
        # The model's save method will handle slug generation and status updates
        super().save_model(request, obj, form, change)

# Register models
admin.site.register(Category, CategoryAdmin)
admin.site.register(Subcategory, SubcategoryAdmin)
admin.site.register(Product, ProductAdmin)

# Register SpecificationTable and SpecificationRow with basic admin
@admin.register(SpecificationTable)
class SpecificationTableAdmin(admin.ModelAdmin):
    inlines = [SpecificationRowInline]
    list_display = ('title', 'product')
    list_filter = ('product__subcategory__category',)

@admin.register(SpecificationRow)
class SpecificationRowAdmin(admin.ModelAdmin):
    list_display = ('table', 'key', 'value')
    list_filter = ('table__product__subcategory__category',)

@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ('title', 'source_name', 'is_published', 'created_at')
    list_filter = ('is_published', 'created_at')
    search_fields = ('title', 'content', 'source_name')
    readonly_fields = ('created_at', 'updated_at', 'slug')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'excerpt', 'is_published')
        }),
        ('Content', {
            'fields': ('content', 'image')
        }),
        ('Source Attribution', {
            'fields': ('source_name', 'source_url'),
            'description': 'Credit external sources if applicable'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('slug',)
        return self.readonly_fields

@admin.register(HeroBanner)
class HeroBannerAdmin(admin.ModelAdmin):
    list_display = (
        'campaign_name',
        'display_mode',
        'status_display',
        'display_order',
        'image_preview',
        'date_range',
        'updated_at'
    )
    list_filter = ('is_active', 'display_mode', 'created_at')
    search_fields = ('campaign_name', 'title', 'subtitle')
    list_editable = ('display_order',)
    readonly_fields = ('created_at', 'updated_at', 'image_preview')
    
    fieldsets = (
        ('Campaign Information', {
            'fields': ('campaign_name', 'display_mode', 'is_active', 'display_order'),
            'description': 'Basic campaign settings and activation status'
        }),
        ('Schedule (Optional)', {
            'fields': ('start_date', 'end_date'),
            'description': 'Leave BLANK to always show when active. Only fill if you want automatic scheduling.',
            'classes': ('collapse',)
        }),
        ('Poster Mode Settings', {
            'fields': ('poster_image', 'poster_link'),
            'description': 'Used when Display Mode = "Poster Only"',
            'classes': ('collapse',)
        }),
        ('Standard Mode Content', {
            'fields': ('title', 'subtitle', 'description', 'button_text', 'button_link'),
            'description': 'Used when Display Mode = "Standard Hero Slide"',
            'classes': ('collapse',)
        }),
        ('Standard Mode Images', {
            'fields': ('image_1', 'image_2', 'image_3', 'layout'),
            'description': 'Product images for Standard mode',
            'classes': ('collapse',)
        }),
        ('Styling', {
            'fields': ('background_class',),
            'description': 'CSS styling options',
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_display(self, obj):
        """Show colored status indicator"""
        if obj.is_active:
            return format_html(
                '<span style="color: white; background-color: #28a745; padding: 3px 10px; border-radius: 3px; font-weight: bold;">● LIVE</span>'
            )
        return format_html(
            '<span style="color: white; background-color: #dc3545; padding: 3px 10px; border-radius: 3px;">○ INACTIVE</span>'
        )
    status_display.short_description = 'Status'
    
    def image_preview(self, obj):
        """Show thumbnail of poster_image or image_1"""
        image = None
        
        if obj.display_mode == 'poster' and obj.poster_image:
            image = obj.poster_image
        elif obj.display_mode == 'standard' and obj.image_1:
            image = obj.image_1
        
        if image:
            try:
                if hasattr(image, 'url'):
                    image_url = image.url
                elif hasattr(image, 'build_url'):
                    image_url = image.build_url()
                else:
                    image_str = str(image)
                    if image_str.startswith('http'):
                        image_url = image_str
                    else:
                        image_url = f'https://res.cloudinary.com/ddwpy1x3v/{image_str}'
                
                return mark_safe(
                    f'<img src="{image_url}" style="width: 80px; height: 80px; object-fit: cover; border-radius: 4px;" />'
                )
            except Exception as e:
                return f"Image Error: {str(e)}"
        return mark_safe('<span style="color: #999;">No Image</span>')
    image_preview.short_description = 'Preview'
    
    def date_range(self, obj):
        """Show start and end dates if set"""
        if obj.start_date or obj.end_date:
            start = obj.start_date.strftime('%Y-%m-%d') if obj.start_date else 'N/A'
            end = obj.end_date.strftime('%Y-%m-%d') if obj.end_date else 'N/A'
            return f"{start} → {end}"
        return mark_safe('<span style="color: #999;">No schedule</span>')
    date_range.short_description = 'Schedule'
    
    actions = ['activate_banners', 'deactivate_banners']
    
    def activate_banners(self, request, queryset):
        """Bulk action to activate selected banners"""
        count = queryset.update(is_active=True)
        cache.delete('active_hero_banners')
        self.message_user(request, f'{count} banner(s) successfully activated and are now LIVE. Cache cleared!')
    activate_banners.short_description = 'Activate selected banners'
    
    def deactivate_banners(self, request, queryset):
        """Bulk action to deactivate selected banners"""
        count = queryset.update(is_active=False)
        cache.delete('active_hero_banners')
        self.message_user(request, f'{count} banner(s) successfully deactivated. Cache cleared!')
    deactivate_banners.short_description = 'Deactivate selected banners'
    
    def save_model(self, request, obj, form, change):
        """Clear hero banner cache when saving and show helpful message"""
        super().save_model(request, obj, form, change)
        
        # ✅ CLEAR CACHE IMMEDIATELY AFTER SAVING
        cache.delete('active_hero_banners')
        
        if obj.is_active:
            self.message_user(
                request,
                f'✅ Banner "{obj.campaign_name}" is now LIVE! Cache cleared - refresh your website to see it immediately.',
                level='success'
            )
        else:
            self.message_user(
                request,
                f'Banner "{obj.campaign_name}" is INACTIVE and will not appear on the website.',
                level='warning'
            )
    
    def delete_model(self, request, obj):
        """Clear cache when deleting a banner"""
        super().delete_model(request, obj)
        cache.delete('active_hero_banners')
        self.message_user(request, 'Banner deleted and cache cleared.')