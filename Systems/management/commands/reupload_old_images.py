import os
from cloudinary.uploader import upload
from Systems.models import Product
from django.conf import settings
from django.core.management.base import BaseCommand

CLOUD_NAME = settings.CLOUDINARY_STORAGE['CLOUD_NAME']
FOLDER = 'products'

class Command(BaseCommand):
    help = "Reupload old images to Cloudinary and convert old IDs to URLs"

    def handle(self, *args, **kwargs):
        products = Product.objects.all()

        for product in products:
            self.stdout.write(f"Processing image for: {product.name}")

            if not product.image:
                self.stdout.write(f"No image for {product.name}, skipping.")
                continue

            image_field = str(product.image)

            try:
                # If it's a local file, upload
                if os.path.isfile(image_field):
                    result = upload(
                        image_field, 
                        folder=FOLDER, 
                        public_id=os.path.splitext(os.path.basename(image_field))[0]
                    )
                    product.image = result['public_id']
                    product.save()
                    self.stdout.write(f"Uploaded {product.name} successfully.")
                else:
                    # Assume old image is a Cloudinary public ID or URL fragment
                    if image_field.startswith('http://') or image_field.startswith('https://'):
                        # Already a URL — keep as is
                        self.stdout.write(f"{product.name} already has a URL, skipping upload.")
                    else:
                        # Construct Cloudinary URL from public ID
                        product.image = f"https://res.cloudinary.com/{CLOUD_NAME}/image/upload/{FOLDER}/{image_field}"
                        product.save()
                        self.stdout.write(f"{product.name} old image ID converted to Cloudinary URL.")
            except Exception as e:
                self.stdout.write(f"Failed for {product.name}: {e}")

        self.stdout.write("Done processing images.")
