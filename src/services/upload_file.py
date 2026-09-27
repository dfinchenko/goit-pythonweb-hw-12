"""Avatar upload to Cloudinary."""

import cloudinary
import cloudinary.uploader


class UploadFileService:
    """Uploads images to Cloudinary.

    Args:
        cloud_name: Cloudinary cloud name.
        api_key: Cloudinary API key.
        api_secret: Cloudinary API secret.
    """

    def __init__(self, cloud_name: str, api_key: str, api_secret: str):
        cloudinary.config(
            cloud_name=cloud_name, api_key=api_key, api_secret=api_secret, secure=True
        )

    @staticmethod
    def upload_file(file, username: str) -> str:
        """Upload an avatar and return a 250x250 cropped image URL.

        Args:
            file: ``UploadFile`` received by FastAPI.
            username: Used to build a stable ``public_id`` (re-upload overwrites).

        Returns:
            str: URL of the uploaded image.
        """
        public_id = f"ContactsApp/{username}"
        result = cloudinary.uploader.upload(
            file.file, public_id=public_id, overwrite=True
        )
        return cloudinary.CloudinaryImage(public_id).build_url(
            width=250, height=250, crop="fill", version=result.get("version")
        )
