import cloudinary
import cloudinary.uploader
import cloudinary.utils
from app.config import settings

# Configure Cloudinary securely
if settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret:
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True
    )

def upload_image_to_cloudinary(file_bytes_or_path, folder_name):
    """
    Uploads an image (either file path or file bytes) to Cloudinary in the specified folder.
    Returns a dict containing 'secure_url' and 'public_id'.
    """
    if not (settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret):
        raise ValueError("Cloudinary credentials are not configured.")
        
    try:
        response = cloudinary.uploader.upload(
            file_bytes_or_path,
            folder=folder_name
        )
        return {
            "secure_url": response.get("secure_url"),
            "public_id": response.get("public_id")
        }
    except Exception as e:
        print(f"Cloudinary upload failed for folder {folder_name}: {e}")
        raise e

def delete_cloudinary_asset(public_id):
    """
    Deletes an asset from Cloudinary by its public ID.
    Returns True if successful, False otherwise.
    """
    if not public_id:
        return False
    if not (settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret):
        print("Cloudinary is not configured. Skipping delete.")
        return False
        
    try:
        response = cloudinary.uploader.destroy(public_id)
        return response.get("result") == "ok"
    except Exception as e:
        print(f"Cloudinary delete failed for asset {public_id}: {e}")
        return False

def get_cloudinary_asset_url(public_id):
    """
    Generates a secure HTTPS URL for a given Cloudinary public ID.
    """
    if not public_id:
        return None
    try:
        url, _ = cloudinary.utils.cloudinary_url(public_id, secure=True)
        return url
    except Exception as e:
        print(f"Cloudinary URL generation failed for public ID {public_id}: {e}")
        return None
