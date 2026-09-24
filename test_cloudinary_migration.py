import requests
import cloudinary
import cloudinary.uploader
import cloudinary.api


# ============================================================
# MARINC CLOUDINARY
# ============================================================

MARINC_CLOUD_NAME = "latmjnhz"
MARINC_API_KEY = "428563213683129"
MARINC_API_SECRET = "62gvUeH8sacU3pvibUNXxur1ipM"


# ============================================================
# TEST ASSET
# ============================================================

PUBLIC_ID = "products/ot3gxeoeuyeqkmhlg8lo"

EDGE_URL = (
    "https://res.cloudinary.com/ddwpy1x3v/"
    f"image/upload/{PUBLIC_ID}"
)


# ============================================================
# STEP 1 — DOWNLOAD FROM EDGE
# ============================================================

print("Downloading image from Edge...")

response = requests.get(EDGE_URL, timeout=30)

print("Edge response:", response.status_code)

if response.status_code != 200:
    raise Exception(
        f"Could not download Edge image. "
        f"HTTP status: {response.status_code}"
    )

image_data = response.content

print("Image downloaded successfully.")
print("Image size:", len(image_data), "bytes")


# ============================================================
# STEP 2 — CONFIGURE MARINC
# ============================================================

cloudinary.config(
    cloud_name=MARINC_CLOUD_NAME,
    api_key=MARINC_API_KEY,
    api_secret=MARINC_API_SECRET,
    secure=True,
)


# ============================================================
# STEP 3 — UPLOAD TO MARINC
# ============================================================

print("\nUploading image to Marinc...")

result = cloudinary.uploader.upload(
    image_data,
    public_id=PUBLIC_ID,
    overwrite=False,
    resource_type="image",
)

print("\nMigration successful!")

print("Public ID:", result["public_id"])
print("Secure URL:", result["secure_url"])


# ============================================================
# STEP 4 — VERIFY MARINC ASSET
# ============================================================

print("\nVerifying Marinc asset...")

verified = cloudinary.api.resource(
    PUBLIC_ID,
    resource_type="image",
)

print("Destination verified!")
print("Public ID:", verified["public_id"])
print("Secure URL:", verified["secure_url"])