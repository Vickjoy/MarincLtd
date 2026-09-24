import os
import requests
import django
import cloudinary
import cloudinary.uploader

# --------------------------------------------------
# Django setup
# --------------------------------------------------

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Marinc.settings")
django.setup()

# --------------------------------------------------
# Import Product model
# --------------------------------------------------

from django.apps import apps

Product = None

for model in apps.get_models():
    if model.__name__ == "Product":
        Product = model
        break

if Product is None:
    raise RuntimeError(
        "Could not find the Product model in the installed Django apps."
    )

print(f"Product model found: {Product._meta.label}")
# --------------------------------------------------
# Configuration
# --------------------------------------------------

EDGE_CLOUD_NAME = "ddwpy1x3v"
MARINC_CLOUD_NAME = "latmjnhz"

START_ID = 365

PROGRESS_FILE = "cloudinary_migration_progress.txt"
FAILURE_FILE = "cloudinary_migration_failures.txt"

# --------------------------------------------------
# Cloudinary configuration
# Uses Marinc's existing Django Cloudinary settings
# --------------------------------------------------

cloudinary.config()

if cloudinary.config().cloud_name != MARINC_CLOUD_NAME:
    raise RuntimeError(
        f"Wrong Cloudinary configuration detected.\n"
        f"Expected: {MARINC_CLOUD_NAME}\n"
        f"Found: {cloudinary.config().cloud_name}"
    )

# --------------------------------------------------
# Load previously completed migrations
# --------------------------------------------------

completed = set()

if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        completed = {
            line.strip()
            for line in f
            if line.strip()
        }

print("=" * 60)
print("MARINC CLOUDINARY IMAGE MIGRATION")
print("=" * 60)
print(f"Starting from Product ID: {START_ID}")
print(f"Already completed: {len(completed)}")
print(f"Progress file: {PROGRESS_FILE}")
print("=" * 60)

# --------------------------------------------------
# Get products
# --------------------------------------------------

products = (
    Product.objects
    .filter(id__gte=START_ID)
    .exclude(image__isnull=True)
    .order_by("id")
)

total = products.count()

print(f"Products with images from ID {START_ID}: {total}")
print()

migrated = 0
already_exists = 0
failed = 0

# --------------------------------------------------
# Migration
# --------------------------------------------------

for index, product in enumerate(products, start=1):

    try:
        public_id = product.image.public_id

        if not public_id:
            print(f"[{product.id}] {product.name} - No public ID")
            continue

        # Skip anything already successfully processed
        if public_id in completed:
            print(
                f"[{product.id}] {product.name} "
                f"- Already processed, skipping"
            )
            continue

        print(
            f"[{product.id}] {product.name}"
        )
        print(f"    Public ID: {public_id}")

        # --------------------------------------------------
        # Source image from Edge Cloudinary
        # --------------------------------------------------

        source_url = (
            f"https://res.cloudinary.com/"
            f"{EDGE_CLOUD_NAME}/image/upload/"
            f"{public_id}"
        )

        print("    Downloading from Edge...")

        response = requests.get(
            source_url,
            timeout=60
        )

        if response.status_code != 200:
            raise Exception(
                f"Edge download failed: HTTP {response.status_code}"
            )

        print(
            f"    Downloaded: {len(response.content):,} bytes"
        )

        # --------------------------------------------------
        # Upload to Marinc
        # --------------------------------------------------

        print("    Uploading to Marinc...")

        result = cloudinary.uploader.upload(
            response.content,
            public_id=public_id,
            overwrite=False,
            resource_type="image"
        )

        # --------------------------------------------------
        # Success
        # --------------------------------------------------

        completed.add(public_id)

        with open(
            PROGRESS_FILE,
            "a",
            encoding="utf-8"
        ) as f:
            f.write(public_id + "\n")

        migrated += 1

        print(
            f"    SUCCESS"
        )
        print(
            f"    Marinc URL: {result.get('secure_url')}"
        )

    except Exception as e:

        error_text = str(e)
        error_lower = error_text.lower()

        # --------------------------------------------------
        # Rate limit detected
        # Stop immediately instead of wasting requests
        # --------------------------------------------------

        if (
            "rate limit" in error_lower
            or "420" in error_lower
            or "api operations" in error_lower
            or "too many requests" in error_lower
        ):
            print()
            print("=" * 60)
            print("CLOUDINARY RATE LIMIT REACHED")
            print("=" * 60)
            print(
                "The migration has stopped safely."
            )
            print(
                "Wait for the Cloudinary limit to reset, "
                "then run this same script again."
            )
            print(
                f"Progress has been saved to: {PROGRESS_FILE}"
            )
            print("=" * 60)

            break

        # --------------------------------------------------
        # Existing asset
        # --------------------------------------------------

        if (
            "already exists" in error_lower
            or "already exist" in error_lower
            or "resource already" in error_lower
        ):

            completed.add(public_id)

            with open(
                PROGRESS_FILE,
                "a",
                encoding="utf-8"
            ) as f:
                f.write(public_id + "\n")

            already_exists += 1

            print(
                "    Already exists in Marinc - skipped"
            )

            continue

        # --------------------------------------------------
        # Other failure
        # --------------------------------------------------

        failed += 1

        print(
            f"    FAILED: {error_text}"
        )

        with open(
            FAILURE_FILE,
            "a",
            encoding="utf-8"
        ) as f:
            f.write(
                f"Product ID: {product.id}\n"
                f"Product: {product.name}\n"
                f"Public ID: {public_id}\n"
                f"Error: {error_text}\n"
                f"{'-' * 60}\n"
            )

    print()

# --------------------------------------------------
# Summary
# --------------------------------------------------

print()
print("=" * 60)
print("MIGRATION SUMMARY")
print("=" * 60)

print(f"Migrated successfully : {migrated}")
print(f"Already existed       : {already_exists}")
print(f"Failed                : {failed}")
print(f"Progress file         : {PROGRESS_FILE}")
print(f"Failure file          : {FAILURE_FILE}")

print("=" * 60)
print("Migration run finished.")
print("=" * 60)