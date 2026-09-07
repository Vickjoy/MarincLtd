from django.core.management.base import BaseCommand
from Systems.models import Subcategory

class Command(BaseCommand):
    help = 'Clean up subcategories with no associated category and print a summary.'

    def handle(self, *args, **options):
        # Delete subcategories with no category
        orphaned = Subcategory.objects.filter(category__isnull=True)
        count = orphaned.count()
        if count > 0:
            self.stdout.write(f'Deleting {count} orphaned subcategories...')
            orphaned.delete()
        else:
            self.stdout.write('No orphaned subcategories found.')

        # Print summary of all subcategories and their categories
        self.stdout.write('Current subcategories:')
        for sub in Subcategory.objects.all():
            self.stdout.write(f'- {sub.name} (Category: {sub.category})')
        self.stdout.write('Cleanup complete.') 