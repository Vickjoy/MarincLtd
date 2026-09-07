from django.db import migrations

def set_category_types(apps, schema_editor):
    Category = apps.get_model('Systems', 'Category')
    for cat in Category.objects.all():
        if 'fire' in cat.name.lower():
            cat.type = 'fire'
        else:
            cat.type = 'ict'
        cat.save()

class Migration(migrations.Migration):
    dependencies = [
        ('Systems', '0003_product_slug_subcategory_slug'),
    ]
    operations = [
        migrations.RunPython(set_category_types),
    ] 